// crpa_core: two-element CRPA combiner for axi_ad9361 (2R2T, CMOS), Pluto.
//
// Datapath (crpa_dp) on l_clk; AXI-Lite registers on s_axi_aclk. Register map:
// docs/regmap.md. Interface facts: docs/interface.md, Section 8.
//
// Clock domain crossings:
//   up -> d: one up_xfer_cntrl word carries CTRL, INT_LEN, the committed weight set
//            and two toggles (weight update, flag clear). The word moves as a whole,
//            so W1, W2 and OUT_SHIFT always change together.
//   d -> up: up_xfer_status carries the sticky flags and the applied-update toggle. It
//            ORs its input over each transfer window, which suits flags but not
//            multi-bit values, so the block results use a 4-phase req/ack handshake:
//            d_res_* are loaded and then held until the up side acknowledges.
//
// Muxes (default after reset: normal Pluto operation):
//   DAC      CTRL.DAC_SEL 0: dma_dac_data_* (upack) pass through; 1: ch0/1 = y << 4,
//            ch2/3 = 0. Takes effect only with TX data_sel = 2 (set by the PS).
//   capture  CTRL.CAP_SEL 0: adc_valid and adc_data_* registered once; 1: ch0/1 = y,
//            ch2/3 = x1 of the same sample, all S12 sign-extended to 16 bits.

`timescale 1ns/100ps

module crpa_core #(
  parameter ID = 0
) (

  // l_clk domain (axi_ad9361 l_clk and rst)

  input                 clk,
  input                 rst,

  input                 adc_valid,
  input       [15:0]    adc_data_i0,
  input       [15:0]    adc_data_q0,
  input       [15:0]    adc_data_i1,
  input       [15:0]    adc_data_q1,

  output reg            cap_valid,
  output reg  [15:0]    cap_data_0,
  output reg  [15:0]    cap_data_1,
  output reg  [15:0]    cap_data_2,
  output reg  [15:0]    cap_data_3,

  input       [15:0]    dma_dac_data_i0,
  input       [15:0]    dma_dac_data_q0,
  input       [15:0]    dma_dac_data_i1,
  input       [15:0]    dma_dac_data_q1,
  output      [15:0]    dac_data_i0,
  output      [15:0]    dac_data_q0,
  output      [15:0]    dac_data_i1,
  output      [15:0]    dac_data_q1,

  // interrupt: level, high while STATUS.DONE is set

  output                irq,

  // AXI-Lite

  input                 s_axi_aclk,
  input                 s_axi_aresetn,
  input                 s_axi_awvalid,
  input       [15:0]    s_axi_awaddr,
  input       [ 2:0]    s_axi_awprot,
  output                s_axi_awready,
  input                 s_axi_wvalid,
  input       [31:0]    s_axi_wdata,
  input       [ 3:0]    s_axi_wstrb,
  output                s_axi_wready,
  output                s_axi_bvalid,
  output      [ 1:0]    s_axi_bresp,
  input                 s_axi_bready,
  input                 s_axi_arvalid,
  input       [15:0]    s_axi_araddr,
  input       [ 2:0]    s_axi_arprot,
  output                s_axi_arready,
  output                s_axi_rvalid,
  output      [ 1:0]    s_axi_rresp,
  output      [31:0]    s_axi_rdata,
  input                 s_axi_rready
);

  localparam [31:0] VERSION = 32'h0001_0000;    // 1.0
  localparam [23:0] INT_LEN_DEFAULT = 24'd10000;
  localparam [31:0] UNITY_W = 32'h0000_7fff;    // {q, i} = {0, 0x7FFF}

  // xfer word layout (up -> d)
  localparam XW = 99;
  //   [63:0]  committed {w2q, w2i, w1q, w1i}
  //   [67:64] committed OUT_SHIFT
  //   [91:68] INT_LEN
  //   [92]    CAP_SEL   [93] DAC_SEL   [94] COV_EN   [95] SOFT_RST
  //   [96]    update toggle   [97] flag clear toggle   [98] 1 (word valid)

  // ---------------------------------------------------------------------------
  // up (s_axi_aclk) side

  wire                  up_clk = s_axi_aclk;
  wire                  up_rstn = s_axi_aresetn;

  wire                  up_wreq;
  wire        [13:0]    up_waddr;
  wire        [31:0]    up_wdata;
  reg                   up_wack = 1'b0;
  wire                  up_rreq;
  wire        [13:0]    up_raddr;
  reg         [31:0]    up_rdata = 32'd0;
  reg                   up_rack = 1'b0;

  reg         [31:0]    up_scratch = 32'd0;
  reg                   up_soft_rst = 1'b0;
  reg                   up_cov_en = 1'b0;
  reg                   up_dac_sel = 1'b0;
  reg                   up_cap_sel = 1'b0;
  reg         [23:0]    up_int_len = INT_LEN_DEFAULT;
  reg         [31:0]    up_w1 = UNITY_W;
  reg         [31:0]    up_w2 = 32'd0;
  reg         [ 3:0]    up_shift = 4'd0;
  reg         [63:0]    up_w_c = {32'd0, UNITY_W};
  reg         [ 3:0]    up_shift_c = 4'd0;
  reg                   up_upd_tgl = 1'b0;
  reg                   up_clr_tgl = 1'b0;
  reg                   up_done = 1'b0;
  reg         [31:0]    up_missed = 32'd0;

  reg                   crpa_up_req_m1 = 1'b0;
  reg                   crpa_up_req_m2 = 1'b0;
  reg                   crpa_up_ack = 1'b0;
  reg         [255:0]   crpa_up_res = 256'd0;

  // d side of the result handshake (declared here: the up side reads them)
  reg                   crpa_d_req = 1'b0;
  reg                   crpa_d_ack_m1 = 1'b0;
  reg                   crpa_d_ack_m2 = 1'b0;
  reg         [255:0]   crpa_d_res = 256'd0;

  wire        [ 2:0]    up_status_s;    // {applied toggle, result drop, frame error}
  wire                  up_w_busy = up_upd_tgl ^ up_status_s[2];

  wire        [XW-1:0]  up_xfer_word = {1'b1, up_clr_tgl, up_upd_tgl, up_soft_rst, up_cov_en,
                                        up_dac_sel, up_cap_sel, up_int_len, up_shift_c, up_w_c};

  assign irq = up_done;

  up_axi #(
    .AXI_ADDRESS_WIDTH (16)
  ) i_up_axi (
    .up_rstn (up_rstn),
    .up_clk (up_clk),
    .up_axi_awvalid (s_axi_awvalid),
    .up_axi_awaddr (s_axi_awaddr),
    .up_axi_awready (s_axi_awready),
    .up_axi_wvalid (s_axi_wvalid),
    .up_axi_wdata (s_axi_wdata),
    .up_axi_wstrb (s_axi_wstrb),
    .up_axi_wready (s_axi_wready),
    .up_axi_bvalid (s_axi_bvalid),
    .up_axi_bresp (s_axi_bresp),
    .up_axi_bready (s_axi_bready),
    .up_axi_arvalid (s_axi_arvalid),
    .up_axi_araddr (s_axi_araddr),
    .up_axi_arready (s_axi_arready),
    .up_axi_rvalid (s_axi_rvalid),
    .up_axi_rresp (s_axi_rresp),
    .up_axi_rdata (s_axi_rdata),
    .up_axi_rready (s_axi_rready),
    .up_wreq (up_wreq),
    .up_waddr (up_waddr),
    .up_wdata (up_wdata),
    .up_wack (up_wack),
    .up_rreq (up_rreq),
    .up_raddr (up_raddr),
    .up_rdata (up_rdata),
    .up_rack (up_rack));

  // writes, and the result handshake (both change up_done)

  wire                  up_req_new = crpa_up_req_m2 & ~crpa_up_ack;

  always @(posedge up_clk) begin
    if (up_rstn == 1'b0) begin
      up_wack <= 1'b0;
      up_scratch <= 32'd0;
      up_soft_rst <= 1'b0;
      up_cov_en <= 1'b0;
      up_dac_sel <= 1'b0;
      up_cap_sel <= 1'b0;
      up_int_len <= INT_LEN_DEFAULT;
      up_w1 <= UNITY_W;
      up_w2 <= 32'd0;
      up_shift <= 4'd0;
      up_w_c <= {32'd0, UNITY_W};
      up_shift_c <= 4'd0;
      up_upd_tgl <= 1'b0;
      up_clr_tgl <= 1'b0;
      up_done <= 1'b0;
      up_missed <= 32'd0;
      crpa_up_req_m1 <= 1'b0;
      crpa_up_req_m2 <= 1'b0;
      crpa_up_ack <= 1'b0;
    end else begin
      up_wack <= up_wreq;
      crpa_up_req_m1 <= crpa_d_req;
      crpa_up_req_m2 <= crpa_up_req_m1;

      if (up_wreq == 1'b1) begin
        case (up_waddr)
          14'h02: up_scratch <= up_wdata;
          14'h03: begin
            up_soft_rst <= up_wdata[0];
            up_cov_en <= up_wdata[1];
            up_dac_sel <= up_wdata[2];
            up_cap_sel <= up_wdata[3];
          end
          14'h04: begin
            if (up_wdata[0] == 1'b1) begin
              up_done <= 1'b0;
            end
            if (up_wdata[3:2] != 2'd0) begin
              up_clr_tgl <= ~up_clr_tgl;
            end
          end
          14'h05: up_int_len <= (up_wdata[23:0] == 24'd0) ? 24'd1 : up_wdata[23:0];
          14'h06: up_w1 <= up_wdata;
          14'h07: up_w2 <= up_wdata;
          14'h08: up_shift <= up_wdata[3:0];
          14'h09: begin
            up_w_c <= {up_w2, up_w1};
            up_shift_c <= up_shift;
            up_upd_tgl <= ~up_upd_tgl;
          end
          14'h0a: up_missed <= 32'd0;
          default: ;
        endcase
      end

      // a new block: keep it unless the previous one is still unread (DONE set)
      if (up_req_new == 1'b1) begin
        crpa_up_ack <= 1'b1;
        if (up_done == 1'b0) begin
          crpa_up_res <= crpa_d_res;
          up_done <= 1'b1;
        end else begin
          up_missed <= up_missed + 32'd1;
        end
      end else if (crpa_up_req_m2 == 1'b0 && crpa_up_ack == 1'b1) begin
        crpa_up_ack <= 1'b0;
      end
    end
  end

  // reads

  // crpa_up_res layout: {r11, r22, r21re, r21im, sat[23:0], peak1, peak2, seq}
  wire        [47:0]    up_r11 = crpa_up_res[255:208];
  wire        [47:0]    up_r22 = crpa_up_res[207:160];
  wire        [47:0]    up_rre = crpa_up_res[159:112];
  wire        [47:0]    up_rim = crpa_up_res[111:64];
  wire        [23:0]    up_sat = crpa_up_res[63:40];
  wire        [11:0]    up_pk1 = crpa_up_res[39:28];
  wire        [11:0]    up_pk2 = crpa_up_res[27:16];
  wire        [15:0]    up_seq = crpa_up_res[15:0];

  always @(posedge up_clk) begin
    if (up_rstn == 1'b0) begin
      up_rack <= 1'b0;
      up_rdata <= 32'd0;
    end else begin
      up_rack <= up_rreq;
      if (up_rreq == 1'b1) begin
        case (up_raddr)
          14'h00: up_rdata <= VERSION;
          14'h01: up_rdata <= ID;
          14'h02: up_rdata <= up_scratch;
          14'h03: up_rdata <= {28'd0, up_cap_sel, up_dac_sel, up_cov_en, up_soft_rst};
          14'h04: up_rdata <= {28'd0, up_status_s[1], up_status_s[0], up_w_busy, up_done};
          14'h05: up_rdata <= {8'd0, up_int_len};
          14'h06: up_rdata <= up_w1;
          14'h07: up_rdata <= up_w2;
          14'h08: up_rdata <= {28'd0, up_shift};
          14'h0a: up_rdata <= up_missed;
          14'h10: up_rdata <= up_r11[31:0];
          14'h11: up_rdata <= {{16{up_r11[47]}}, up_r11[47:32]};
          14'h12: up_rdata <= up_r22[31:0];
          14'h13: up_rdata <= {{16{up_r22[47]}}, up_r22[47:32]};
          14'h14: up_rdata <= up_rre[31:0];
          14'h15: up_rdata <= {{16{up_rre[47]}}, up_rre[47:32]};
          14'h16: up_rdata <= up_rim[31:0];
          14'h17: up_rdata <= {{16{up_rim[47]}}, up_rim[47:32]};
          14'h18: up_rdata <= {8'd0, up_sat};
          14'h19: up_rdata <= {4'd0, up_pk2, 4'd0, up_pk1};
          14'h1a: up_rdata <= {16'd0, up_seq};
          default: up_rdata <= 32'd0;
        endcase
      end else begin
        up_rdata <= 32'd0;
      end
    end
  end

  // ---------------------------------------------------------------------------
  // crossings

  wire        [XW-1:0]  d_word;

  up_xfer_cntrl #(
    .DATA_WIDTH (XW)
  ) i_xfer_cntrl (
    .up_rstn (up_rstn),
    .up_clk (up_clk),
    .up_data_cntrl (up_xfer_word),
    .up_xfer_done (),
    .d_rst (rst),
    .d_clk (clk),
    .d_data_cntrl (d_word));

  reg                   d_applied = 1'b0;
  reg                   d_frame_err = 1'b0;
  reg                   d_drop = 1'b0;

  up_xfer_status #(
    .DATA_WIDTH (3)
  ) i_xfer_status (
    .up_rstn (up_rstn),
    .up_clk (up_clk),
    .up_data_status (up_status_s),
    .d_rst (rst),
    .d_clk (clk),
    .d_data_status ({d_applied, d_drop, d_frame_err}));

  // ---------------------------------------------------------------------------
  // d (l_clk) side

  wire                  d_word_ok = d_word[98];
  wire                  d_clr_tgl = d_word[97];
  wire                  d_upd_tgl = d_word[96];
  wire                  d_soft_rst = d_word[95] & d_word_ok;
  wire                  d_cov_en = d_word[94] & d_word_ok;
  wire                  d_dac_sel = d_word[93] & d_word_ok;
  wire                  d_cap_sel = d_word[92] & d_word_ok;
  wire        [23:0]    d_int_len = d_word[91:68];

  reg                   d_seen = 1'b0;
  reg                   d_upd_prev = 1'b0;
  reg                   d_clr_prev = 1'b0;

  // apply the committed set when a new update toggle arrives, and once after rst
  wire                  d_w_upd = d_word_ok & (~d_seen | (d_upd_tgl ^ d_upd_prev));

  wire                  w_ack, y_valid, y_sat, res_valid, frame_err;
  wire        [11:0]    y_i, y_q, y_x1i, y_x1q, res_peak1, res_peak2;
  wire        [47:0]    res_r11, res_r22, res_r21re, res_r21im;
  wire        [23:0]    res_sat;
  wire        [15:0]    res_seq;

  crpa_dp i_dp (
    .clk (clk),
    .rst (rst),
    .clr (d_soft_rst),
    .adc_valid (adc_valid),
    .adc_data_i0 (adc_data_i0),
    .adc_data_q0 (adc_data_q0),
    .adc_data_i1 (adc_data_i1),
    .adc_data_q1 (adc_data_q1),
    .w_upd (d_w_upd),
    .w_new (d_word[63:0]),
    .shift_new (d_word[67:64]),
    .w_ack (w_ack),
    .cov_en (d_cov_en),
    .int_len (d_int_len),
    .y_valid (y_valid),
    .y_i (y_i),
    .y_q (y_q),
    .y_sat (y_sat),
    .y_x1i (y_x1i),
    .y_x1q (y_x1q),
    .res_valid (res_valid),
    .res_r11 (res_r11),
    .res_r22 (res_r22),
    .res_r21re (res_r21re),
    .res_r21im (res_r21im),
    .res_sat (res_sat),
    .res_peak1 (res_peak1),
    .res_peak2 (res_peak2),
    .res_seq (res_seq),
    .frame_err (frame_err));

  always @(posedge clk) begin
    if (rst == 1'b1) begin
      d_seen <= 1'b0;
      d_upd_prev <= 1'b0;
      d_clr_prev <= 1'b0;
      d_applied <= 1'b0;
      d_frame_err <= 1'b0;
      d_drop <= 1'b0;
      crpa_d_req <= 1'b0;
      crpa_d_ack_m1 <= 1'b0;
      crpa_d_ack_m2 <= 1'b0;
    end else begin
      if (d_w_upd == 1'b1) begin
        d_seen <= 1'b1;
        d_upd_prev <= d_upd_tgl;
      end
      if (w_ack == 1'b1) begin
        d_applied <= d_upd_prev;
      end

      // sticky flags, cleared by a new clear toggle
      if (d_word_ok == 1'b1 && d_clr_tgl != d_clr_prev) begin
        d_clr_prev <= d_clr_tgl;
        d_frame_err <= 1'b0;
        d_drop <= 1'b0;
      end else begin
        if (frame_err == 1'b1) begin
          d_frame_err <= 1'b1;
        end
        if (res_valid == 1'b1 && (crpa_d_req == 1'b1 || crpa_d_ack_m2 == 1'b1)) begin
          d_drop <= 1'b1;
        end
      end

      // result handshake: load and raise req only when idle (req and ack both low)
      crpa_d_ack_m1 <= crpa_up_ack;
      crpa_d_ack_m2 <= crpa_d_ack_m1;
      if (crpa_d_req == 1'b1 && crpa_d_ack_m2 == 1'b1) begin
        crpa_d_req <= 1'b0;
      end
      if (res_valid == 1'b1 && crpa_d_req == 1'b0 && crpa_d_ack_m2 == 1'b0) begin
        crpa_d_req <= 1'b1;
        crpa_d_res <= {res_r11, res_r22, res_r21re, res_r21im, res_sat, res_peak1, res_peak2, res_seq};
      end
    end
  end

  // DAC mux

  assign dac_data_i0 = d_dac_sel ? {y_i, 4'd0} : dma_dac_data_i0;
  assign dac_data_q0 = d_dac_sel ? {y_q, 4'd0} : dma_dac_data_q0;
  assign dac_data_i1 = d_dac_sel ? 16'd0 : dma_dac_data_i1;
  assign dac_data_q1 = d_dac_sel ? 16'd0 : dma_dac_data_q1;

  // capture mux

  always @(posedge clk) begin
    if (rst == 1'b1) begin
      cap_valid <= 1'b0;
    end else if (d_cap_sel == 1'b1) begin
      cap_valid <= y_valid;
    end else begin
      cap_valid <= adc_valid;
    end
    if (d_cap_sel == 1'b1) begin
      if (y_valid == 1'b1) begin
        cap_data_0 <= {{4{y_i[11]}}, y_i};
        cap_data_1 <= {{4{y_q[11]}}, y_q};
        cap_data_2 <= {{4{y_x1i[11]}}, y_x1i};
        cap_data_3 <= {{4{y_x1q[11]}}, y_x1q};
      end
    end else begin
      if (adc_valid == 1'b1) begin
        cap_data_0 <= adc_data_i0;
        cap_data_1 <= adc_data_q0;
        cap_data_2 <= adc_data_i1;
        cap_data_3 <= adc_data_q1;
      end
    end
  end

endmodule
