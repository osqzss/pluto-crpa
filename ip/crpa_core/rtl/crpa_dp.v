// crpa_dp: two-element combiner and covariance integrator, on l_clk.
//
// Bit-true to model/crpa_model.py (combine, covariance); formats in docs/fixed_point.md.
//
//   input x      S12 from adc_data_*[11:0]; [15:12] are ignored (sign extension).
//   weight w     Q1.15 (S16) for each of re, im. Unity is 0x7FFF.
//   y = conj(w1) * x1 + conj(w2) * x2
//     si = w1i*x1i + w1q*x1q + w2i*x2i + w2q*x2q     products S28, sum S30
//     sq = w1i*x1q - w1q*x1i + w2i*x2q - w2q*x2i
//   shift        s = 0..15, gain 2^s: sh = 15 - s
//   rounding     round half up once: (sum + 2^(sh-1)) >>> sh, nothing added for sh = 0
//   saturation   to S12, separately for I and Q; sat = either saturated
//   R11 += x1i^2 + x1q^2, R22 += x2i^2 + x2q^2 (each term 0..2^23)
//   R21 += x2 * conj(x1): re += x2i*x1i + x2q*x1q, im += x2q*x1i - x2i*x1q
//   accumulators 48-bit signed, no rounding. INT_LEN 1..2^24-1 rules out overflow.
//
// Timing: one sample per adc_valid, at most one adc_valid per 2 cycles (2R2T,
// docs/interface.md). Every stage loads on the valid of the stage before it, so the
// outputs change once per sample and hold in between. Latency from the adc_valid cycle
// to y_valid is 5 cycles.
//
// Weights: w_upd (one cycle) makes w_new and shift_new apply from the next sample
// loaded, together. w_new and shift_new must hold until then. w_ack pulses when the set
// is applied. If w_upd comes in the adc_valid cycle, the set applies to that sample.
//
// Blocks: while cov_en is high, consecutive blocks of int_len samples run back to
// back, the first starting with the first sample that reaches the last stage. int_len
// is read at the start of each block; 0 is taken as 1. At the end of a block, res_*
// load and res_valid pulses; they hold until the next block ends. cov_en low stops
// and resets the block count and res_seq.
//
// rst (axi_ad9361 rst) resets everything, including the weights to [unity, 0], shift 0.
// clr (soft reset) resets the pipeline, blocks and flags, not the weights.

`timescale 1ns/100ps

module crpa_dp (
  input                 clk,
  input                 rst,
  input                 clr,

  input                 adc_valid,
  input       [15:0]    adc_data_i0,
  input       [15:0]    adc_data_q0,
  input       [15:0]    adc_data_i1,
  input       [15:0]    adc_data_q1,

  input                 w_upd,
  input       [63:0]    w_new,        // {w2q, w2i, w1q, w1i}
  input       [ 3:0]    shift_new,
  output reg            w_ack,

  input                 cov_en,
  input       [23:0]    int_len,

  output reg            y_valid,
  output reg  [11:0]    y_i,
  output reg  [11:0]    y_q,
  output reg            y_sat,
  output reg  [11:0]    y_x1i,        // x1 of the same sample, for the capture path
  output reg  [11:0]    y_x1q,

  output reg            res_valid,
  output reg  [47:0]    res_r11,
  output reg  [47:0]    res_r22,
  output reg  [47:0]    res_r21re,
  output reg  [47:0]    res_r21im,
  output reg  [23:0]    res_sat,      // samples with sat in the block
  output reg  [11:0]    res_peak1,    // max over the block of max(|x1i|, |x1q|), 0..2048
  output reg  [11:0]    res_peak2,
  output reg  [15:0]    res_seq,      // block number since cov_en went high

  output reg            frame_err     // adc_valid high in two consecutive cycles
);

  localparam [15:0] UNITY = 16'h7fff;

  // stage 0: input and active weights

  reg                   adc_valid_d = 1'b0;
  reg                   v0 = 1'b0;
  reg  signed [11:0]    x1i_0 = 0, x1q_0 = 0, x2i_0 = 0, x2q_0 = 0;
  reg  signed [15:0]    w1i = UNITY, w1q = 0, w2i = 0, w2q = 0;
  reg         [ 3:0]    shift_0 = 0;
  reg                   w_pend = 1'b0;

  wire                  w_load = w_upd | w_pend;

  always @(posedge clk) begin
    if (rst == 1'b1) begin
      w1i <= UNITY;
      w1q <= 16'd0;
      w2i <= 16'd0;
      w2q <= 16'd0;
      shift_0 <= 4'd0;
      w_pend <= 1'b0;
      w_ack <= 1'b0;
    end else begin
      w_ack <= 1'b0;
      if (adc_valid == 1'b1 && w_load == 1'b1) begin
        w1i <= w_new[15:0];
        w1q <= w_new[31:16];
        w2i <= w_new[47:32];
        w2q <= w_new[63:48];
        shift_0 <= shift_new;
        w_pend <= 1'b0;
        w_ack <= 1'b1;
      end else if (w_upd == 1'b1) begin
        w_pend <= 1'b1;
      end
    end
  end

  always @(posedge clk) begin
    if (rst == 1'b1 || clr == 1'b1) begin
      adc_valid_d <= 1'b0;
      v0 <= 1'b0;
      frame_err <= 1'b0;
    end else begin
      adc_valid_d <= adc_valid;
      v0 <= adc_valid;
      frame_err <= adc_valid & adc_valid_d;
    end
    if (adc_valid == 1'b1) begin
      x1i_0 <= adc_data_i0[11:0];
      x1q_0 <= adc_data_q0[11:0];
      x2i_0 <= adc_data_i1[11:0];
      x2q_0 <= adc_data_q1[11:0];
    end
  end

  // stage 1: products (S16 x S12 = S28 for the combiner, S12 x S12 = S24 for R)

  reg                   v1 = 1'b0;
  reg  signed [27:0]    p_a = 0, p_b = 0, p_c = 0, p_d = 0;   // yi terms
  reg  signed [27:0]    p_e = 0, p_f = 0, p_g = 0, p_h = 0;   // yq terms
  reg  signed [23:0]    c_11i = 0, c_11q = 0, c_22i = 0, c_22q = 0;
  reg  signed [23:0]    c_re1 = 0, c_re2 = 0, c_im1 = 0, c_im2 = 0;
  reg         [ 3:0]    shift_1 = 0;
  reg         [11:0]    pk1_1 = 0, pk2_1 = 0;
  reg  signed [11:0]    x1i_1 = 0, x1q_1 = 0;

  // |v| for S12, 0..2048 in 12 bits unsigned
  function [11:0] mag;
    input signed [11:0] v;
    reg   signed [12:0] e;
    begin
      e = v;
      mag = (e < 0) ? -e : e;
    end
  endfunction

  function [11:0] max2;
    input [11:0] a;
    input [11:0] b;
    begin
      max2 = (a > b) ? a : b;
    end
  endfunction

  always @(posedge clk) begin
    if (rst == 1'b1 || clr == 1'b1) begin
      v1 <= 1'b0;
    end else begin
      v1 <= v0;
    end
    if (v0 == 1'b1) begin
      p_a <= w1i * x1i_0;
      p_b <= w1q * x1q_0;
      p_c <= w2i * x2i_0;
      p_d <= w2q * x2q_0;
      p_e <= w1i * x1q_0;
      p_f <= w1q * x1i_0;
      p_g <= w2i * x2q_0;
      p_h <= w2q * x2i_0;
      c_11i <= x1i_0 * x1i_0;
      c_11q <= x1q_0 * x1q_0;
      c_22i <= x2i_0 * x2i_0;
      c_22q <= x2q_0 * x2q_0;
      c_re1 <= x2i_0 * x1i_0;
      c_re2 <= x2q_0 * x1q_0;
      c_im1 <= x2q_0 * x1i_0;
      c_im2 <= x2i_0 * x1q_0;
      shift_1 <= shift_0;
      pk1_1 <= max2(mag(x1i_0), mag(x1q_0));
      pk2_1 <= max2(mag(x2i_0), mag(x2q_0));
      x1i_1 <= x1i_0;
      x1q_1 <= x1q_0;
    end
  end

  // stage 2: sums. |si|, |sq| <= 2^28, held in 30 bits. Per-sample R terms in 25 bits.

  reg                   v2 = 1'b0;
  reg  signed [29:0]    si_2 = 0, sq_2 = 0;
  reg  signed [24:0]    t11_2 = 0, t22_2 = 0, tre_2 = 0, tim_2 = 0;
  reg         [ 3:0]    shift_2 = 0;
  reg         [11:0]    pk1_2 = 0, pk2_2 = 0;
  reg  signed [11:0]    x1i_2 = 0, x1q_2 = 0;

  always @(posedge clk) begin
    if (rst == 1'b1 || clr == 1'b1) begin
      v2 <= 1'b0;
    end else begin
      v2 <= v1;
    end
    if (v1 == 1'b1) begin
      si_2 <= p_a + p_b + p_c + p_d;
      sq_2 <= p_e - p_f + p_g - p_h;
      t11_2 <= c_11i + c_11q;
      t22_2 <= c_22i + c_22q;
      tre_2 <= c_re1 + c_re2;
      tim_2 <= c_im1 - c_im2;
      shift_2 <= shift_1;
      pk1_2 <= pk1_1;
      pk2_2 <= pk2_1;
      x1i_2 <= x1i_1;
      x1q_2 <= x1q_1;
    end
  end

  // stage 3: round half up and shift

  reg                   v3 = 1'b0;
  reg  signed [30:0]    ri_3 = 0, rq_3 = 0;
  reg  signed [24:0]    t11_3 = 0, t22_3 = 0, tre_3 = 0, tim_3 = 0;
  reg         [11:0]    pk1_3 = 0, pk2_3 = 0;
  reg  signed [11:0]    x1i_3 = 0, x1q_3 = 0;

  wire        [ 3:0]    sh_2 = 4'd15 - shift_2;
  wire signed [30:0]    rnd_2 = (sh_2 == 4'd0) ? 31'sd0 : (31'sd1 <<< (sh_2 - 4'd1));
  wire signed [30:0]    si_rnd_2 = si_2 + rnd_2;
  wire signed [30:0]    sq_rnd_2 = sq_2 + rnd_2;

  always @(posedge clk) begin
    if (rst == 1'b1 || clr == 1'b1) begin
      v3 <= 1'b0;
    end else begin
      v3 <= v2;
    end
    if (v2 == 1'b1) begin
      ri_3 <= si_rnd_2 >>> sh_2;
      rq_3 <= sq_rnd_2 >>> sh_2;
      t11_3 <= t11_2;
      t22_3 <= t22_2;
      tre_3 <= tre_2;
      tim_3 <= tim_2;
      pk1_3 <= pk1_2;
      pk2_3 <= pk2_2;
      x1i_3 <= x1i_2;
      x1q_3 <= x1q_2;
    end
  end

  // stage 4: saturate, outputs, block accumulation

  function [11:0] sat12;
    input signed [30:0] v;
    begin
      if (v > 31'sd2047) begin
        sat12 = 12'h7ff;
      end else if (v < -31'sd2048) begin
        sat12 = 12'h800;
      end else begin
        sat12 = v[11:0];
      end
    end
  endfunction

  wire                  sat_i_3 = (ri_3 > 31'sd2047) || (ri_3 < -31'sd2048);
  wire                  sat_q_3 = (rq_3 > 31'sd2047) || (rq_3 < -31'sd2048);
  wire                  sat_3 = sat_i_3 | sat_q_3;

  reg         [23:0]    blk_cnt = 0;
  reg         [23:0]    blk_len = 1;
  reg         [15:0]    blk_seq = 0;
  reg  signed [47:0]    acc11 = 0, acc22 = 0, accre = 0, accim = 0;
  reg         [23:0]    acc_sat = 0;
  reg         [11:0]    acc_pk1 = 0, acc_pk2 = 0;

  wire                  first = (blk_cnt == 24'd0);
  wire        [23:0]    len_in = (int_len == 24'd0) ? 24'd1 : int_len;
  wire        [23:0]    len_now = first ? len_in : blk_len;
  wire                  last = (blk_cnt == len_now - 24'd1);

  wire signed [47:0]    n11 = (first ? 48'sd0 : acc11) + t11_3;
  wire signed [47:0]    n22 = (first ? 48'sd0 : acc22) + t22_3;
  wire signed [47:0]    nre = (first ? 48'sd0 : accre) + tre_3;
  wire signed [47:0]    nim = (first ? 48'sd0 : accim) + tim_3;
  wire        [23:0]    nsat = (first ? 24'd0 : acc_sat) + sat_3;
  wire        [11:0]    npk1 = max2(first ? 12'd0 : acc_pk1, pk1_3);
  wire        [11:0]    npk2 = max2(first ? 12'd0 : acc_pk2, pk2_3);

  always @(posedge clk) begin
    if (rst == 1'b1 || clr == 1'b1) begin
      y_valid <= 1'b0;
      res_valid <= 1'b0;
      blk_cnt <= 24'd0;
      blk_seq <= 16'd0;
    end else begin
      y_valid <= v3;
      res_valid <= 1'b0;
      if (cov_en == 1'b0) begin
        blk_cnt <= 24'd0;
        blk_seq <= 16'd0;
      end else if (v3 == 1'b1) begin
        if (first == 1'b1) begin
          blk_len <= len_in;
        end
        if (last == 1'b1) begin
          res_valid <= 1'b1;
          res_seq <= blk_seq;
          blk_seq <= blk_seq + 16'd1;
          blk_cnt <= 24'd0;
        end else begin
          blk_cnt <= blk_cnt + 24'd1;
        end
      end
    end
  end

  always @(posedge clk) begin
    if (v3 == 1'b1) begin
      y_i <= sat12(ri_3);
      y_q <= sat12(rq_3);
      y_sat <= sat_3;
      y_x1i <= x1i_3;
      y_x1q <= x1q_3;
      acc11 <= n11;
      acc22 <= n22;
      accre <= nre;
      accim <= nim;
      acc_sat <= nsat;
      acc_pk1 <= npk1;
      acc_pk2 <= npk2;
      if (cov_en == 1'b1 && last == 1'b1) begin
        res_r11 <= n11;
        res_r22 <= n22;
        res_r21re <= nre;
        res_r21im <= nim;
        res_sat <= nsat;
        res_peak1 <= npk1;
        res_peak2 <= npk2;
      end
    end
  end

endmodule
