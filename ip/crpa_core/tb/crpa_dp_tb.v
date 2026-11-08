// Testbench for crpa_dp against the model vectors (model/gen_vectors.py).
//
// Plusargs:
//   +VEC=<dir>      vector case directory (input.mem, config.mem, output.mem, cov.mem,
//                   blkstat.mem, meta.txt)
//   +GAP=<n>        0: adc_valid every 2 cycles (2R2T). n > 0: 2 + random 0..n cycles
//   +SEED=<n>       random seed for GAP and for the w_upd timing
//
// Weight set k applies from sample start_k. w_upd is given either one cycle before the
// adc_valid of that sample or in the same cycle, chosen at random, so both paths of
// crpa_dp are used. Checks: every output sample (y_i, y_q as dac data, and y_x1i/q),
// every block (R, sat count, peaks, sequence), no frame_err. Prints PASS or FAIL.

`timescale 1ns/100ps

module crpa_dp_tb;

  localparam MAXN = 100000;
  localparam MAXS = 256;
  localparam MAXB = 256;

  reg  [63:0]  in_mem  [0:MAXN-1];
  reg  [31:0]  out_mem [0:MAXN-1];
  reg  [111:0] cfg_mem [0:MAXS-1];
  reg  [255:0] cov_mem [0:MAXB-1];
  reg  [63:0]  bst_mem [0:MAXB-1];

  integer n_samples, n_sets, n_blocks, int_len_v, n_sat;
  integer gap, seed;
  reg [1023:0] vec;

  reg          clk = 1'b0;
  reg          rst = 1'b1;
  reg          clr = 1'b0;
  reg          adc_valid = 1'b0;
  reg  [15:0]  d_i0 = 0, d_q0 = 0, d_i1 = 0, d_q1 = 0;
  reg          w_upd = 1'b0;
  reg  [63:0]  w_new = 0;
  reg  [ 3:0]  shift_new = 0;
  reg          cov_en = 1'b0;
  reg  [23:0]  int_len = 24'd1;

  wire         w_ack, y_valid, y_sat, res_valid, frame_err;
  wire [11:0]  y_i, y_q, y_x1i, y_x1q, res_peak1, res_peak2;
  wire [47:0]  res_r11, res_r22, res_r21re, res_r21im;
  wire [23:0]  res_sat;
  wire [15:0]  res_seq;

  always #8.138 clk = ~clk;    // 61.44 MHz, the highest l_clk

  crpa_dp dut (
    .clk (clk), .rst (rst), .clr (clr),
    .adc_valid (adc_valid),
    .adc_data_i0 (d_i0), .adc_data_q0 (d_q0), .adc_data_i1 (d_i1), .adc_data_q1 (d_q1),
    .w_upd (w_upd), .w_new (w_new), .shift_new (shift_new), .w_ack (w_ack),
    .cov_en (cov_en), .int_len (int_len),
    .y_valid (y_valid), .y_i (y_i), .y_q (y_q), .y_sat (y_sat), .y_x1i (y_x1i), .y_x1q (y_x1q),
    .res_valid (res_valid), .res_r11 (res_r11), .res_r22 (res_r22),
    .res_r21re (res_r21re), .res_r21im (res_r21im), .res_sat (res_sat),
    .res_peak1 (res_peak1), .res_peak2 (res_peak2), .res_seq (res_seq),
    .frame_err (frame_err));

  integer errors = 0;
  integer n_out = 0;
  integer n_res = 0;
  integer n_ack = 0;

  // output checks

  always @(posedge clk) begin
    if (y_valid == 1'b1) begin
      if (n_out >= n_samples) begin
        errors = errors + 1;
        $display("ERROR extra output sample %0d", n_out);
      end else begin
        if ({y_i, 4'd0} !== out_mem[n_out][31:16] || {y_q, 4'd0} !== out_mem[n_out][15:0] ||
            y_x1i !== in_mem[n_out][59:48] || y_x1q !== in_mem[n_out][43:32]) begin
          errors = errors + 1;
          if (errors <= 20) begin
            $display("ERROR sample %0d: y %h %h x1 %h %h, expected y %h %h x1 %h %h", n_out,
              {y_i, 4'd0}, {y_q, 4'd0}, y_x1i, y_x1q, out_mem[n_out][31:16], out_mem[n_out][15:0],
              in_mem[n_out][59:48], in_mem[n_out][43:32]);
          end
        end
      end
      n_out = n_out + 1;
    end
    if (res_valid == 1'b1) begin
      if (n_res >= n_blocks) begin
        errors = errors + 1;
        $display("ERROR extra block %0d", n_res);
      end else if ({{16{res_r11[47]}}, res_r11} !== cov_mem[n_res][255:192] ||
                   {{16{res_r22[47]}}, res_r22} !== cov_mem[n_res][191:128] ||
                   {{16{res_r21re[47]}}, res_r21re} !== cov_mem[n_res][127:64] ||
                   {{16{res_r21im[47]}}, res_r21im} !== cov_mem[n_res][63:0] ||
                   {8'd0, res_sat} !== bst_mem[n_res][63:32] ||
                   {4'd0, res_peak1} !== bst_mem[n_res][31:16] ||
                   {4'd0, res_peak2} !== bst_mem[n_res][15:0] ||
                   res_seq !== n_res[15:0]) begin
        errors = errors + 1;
        $display("ERROR block %0d: R %h %h %h %h sat %0d pk %0d %0d seq %0d; expected %h sat/pk %h",
          n_res, res_r11, res_r22, res_r21re, res_r21im, res_sat, res_peak1, res_peak2, res_seq,
          cov_mem[n_res], bst_mem[n_res]);
      end
      n_res = n_res + 1;
    end
    if (w_ack == 1'b1) begin
      n_ack = n_ack + 1;
    end
    if (frame_err == 1'b1) begin
      errors = errors + 1;
      $display("ERROR frame_err");
    end
  end

  // stimulus

  task read_meta;
    integer fd, r, v;
    reg [8*16-1:0] key;
    begin
      fd = $fopen({vec, "/meta.txt"}, "r");
      if (fd == 0) begin
        $display("FAIL cannot open %0s/meta.txt", vec);
        $finish;
      end
      while (!$feof(fd)) begin
        r = $fscanf(fd, "%s %d\n", key, v);
        if (r == 2) begin
          if (key == "samples") n_samples = v;
          if (key == "sets") n_sets = v;
          if (key == "blocks") n_blocks = v;
          if (key == "int_len") int_len_v = v;
          if (key == "sat") n_sat = v;
        end
      end
      $fclose(fd);
    end
  endtask

  integer k, s, set_idx, wait_c, same_cycle;
  reg [31:0] next_start;

  task load_set_values;
    input integer idx;
    begin
      // cfg: {start[31:0], w1i, w1q, w2i, w2q, shift} -> w_new {w2q, w2i, w1q, w1i}
      w_new = {cfg_mem[idx][31:16], cfg_mem[idx][47:32], cfg_mem[idx][63:48], cfg_mem[idx][79:64]};
      shift_new = cfg_mem[idx][3:0];
    end
  endtask

  initial begin
    if (!$value$plusargs("VEC=%s", vec)) begin
      $display("FAIL need +VEC=<dir>");
      $finish;
    end
    if (!$value$plusargs("GAP=%d", gap)) gap = 0;
    if (!$value$plusargs("SEED=%d", seed)) seed = 1;
    read_meta;
    if (n_samples > MAXN || n_sets > MAXS || n_blocks > MAXB) begin
      $display("FAIL vectors larger than the testbench arrays");
      $finish;
    end
    $readmemh({vec, "/input.mem"}, in_mem, 0, n_samples - 1);
    $readmemh({vec, "/output.mem"}, out_mem, 0, n_samples - 1);
    $readmemh({vec, "/config.mem"}, cfg_mem, 0, n_sets - 1);
    if (n_blocks > 0) begin
      $readmemh({vec, "/cov.mem"}, cov_mem, 0, n_blocks - 1);
      $readmemh({vec, "/blkstat.mem"}, bst_mem, 0, n_blocks - 1);
    end
    int_len = int_len_v;

    repeat (4) @(posedge clk);
    #1 rst = 1'b0;
    cov_en = 1'b1;
    repeat (4) @(posedge clk);

    set_idx = 0;
    next_start = cfg_mem[0][111:80];
    for (s = 0; s < n_samples; s = s + 1) begin
      same_cycle = 0;
      if (set_idx < n_sets && next_start == s) begin
        load_set_values(set_idx);
        same_cycle = $random(seed) & 1;
        if (same_cycle == 0) begin
          #1 w_upd = 1'b1;
          @(posedge clk);
          #1 w_upd = 1'b0;
        end
        set_idx = set_idx + 1;
        if (set_idx < n_sets) next_start = cfg_mem[set_idx][111:80];
      end
      #1;
      adc_valid = 1'b1;
      w_upd = same_cycle;
      {d_i0, d_q0, d_i1, d_q1} = in_mem[s];
      @(posedge clk);
      #1;
      adc_valid = 1'b0;
      w_upd = 1'b0;
      {d_i0, d_q0, d_i1, d_q1} = 64'hxxxx_xxxx_xxxx_xxxx;   // only the valid cycle may matter
      wait_c = (gap > 0) ? ($unsigned($random(seed)) % (gap + 1)) : 0;
      @(posedge clk);
      repeat (wait_c) @(posedge clk);
    end
    repeat (20) @(posedge clk);

    if (n_out != n_samples) begin
      errors = errors + 1;
      $display("ERROR %0d output samples, expected %0d", n_out, n_samples);
    end
    if (n_res != n_blocks) begin
      errors = errors + 1;
      $display("ERROR %0d blocks, expected %0d", n_res, n_blocks);
    end
    if (n_ack != n_sets) begin
      errors = errors + 1;
      $display("ERROR %0d weight acks, expected %0d", n_ack, n_sets);
    end
    if (errors == 0) begin
      $display("PASS %0s gap %0d: %0d samples, %0d sets, %0d blocks (int_len %0d)",
        vec, gap, n_samples, n_sets, n_blocks, int_len_v);
    end else begin
      $display("FAIL %0s gap %0d: %0d errors", vec, gap, errors);
    end
    $finish;
  end

endmodule
