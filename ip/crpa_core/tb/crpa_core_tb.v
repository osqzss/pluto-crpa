// Testbench for crpa_core: AXI-Lite registers, clock domain crossings, muxes, flags.
// The datapath itself is checked bit exactly by crpa_dp_tb; here the model vectors of
// the "core" case (model/gen_vectors.py) check that it is reached correctly through
// the registers.
//
// Plusargs: +VEC=<dir of the core case>  +LCLK_NS=<l_clk period, ns> (s_axi_aclk 100 MHz)
//
// Sequence:
//  1. Reset values of all registers; DAC mux passes the DMA data; raw capture.
//  2. Weight set 0 over AXI, wait for W_BUSY low; COV_EN, DAC_SEL, CAP_SEL.
//  3. Stream the input from sample 0. A PS process switches weight sets during the
//     stream and reads every block it can. Checks:
//     - each capture output is y of the current set or of the one being written, and
//       never goes back (W1, W2 and OUT_SHIFT change together); x1 in the capture
//       matches the input of the same sample; DAC = y << 4 on ch0/1 and 0 on ch2/3
//     - block results equal the model block given by SEQ; MISSED counts the rest
//  4. Not reading: DONE holds the first unread block, MISSED counts the others.
//  5. INT_LEN 1: the handshake cannot keep up, RES_DROP is set; clearing works.
//  6. Two consecutive adc_valid: FRAME_ERR is set; clearing works.
//  7. SOFT_RST: block numbering restarts at 0. DAC_SEL 0 restores the DMA path.
// Prints PASS or FAIL.

`timescale 1ns/100ps

module crpa_core_tb;

  localparam MAXN = 6000;

  reg  [63:0]  in_mem  [0:MAXN-1];
  reg  [31:0]  out_mem [0:8*MAXN-1];    // set k at k * MAXN
  reg  [79:0]  set_mem [0:7];
  reg  [255:0] cov_mem [0:63];
  reg  [63:0]  bst_mem [0:63];
  integer n_samples, n_sets, n_blocks, int_len_v;
  reg [1023:0] vec;
  real lclk_ns;

  // clocks and resets

  reg          clk = 1'b0;
  reg          rst = 1'b1;
  reg          aclk = 1'b0;
  reg          aresetn = 1'b0;

  initial begin
    if (!$value$plusargs("LCLK_NS=%f", lclk_ns)) lclk_ns = 16.276;
    forever #(lclk_ns / 2.0) clk = ~clk;
  end
  always #5 aclk = ~aclk;

  // DUT

  reg          adc_valid = 1'b0;
  reg  [15:0]  adc_i0 = 0, adc_q0 = 0, adc_i1 = 0, adc_q1 = 0;
  reg  [15:0]  dma_i0 = 16'h1230, dma_q0 = 16'h4560, dma_i1 = 16'h7890, dma_q1 = 16'habc0;
  wire [15:0]  dac_i0, dac_q0, dac_i1, dac_q1;
  wire         cap_valid;
  wire [15:0]  cap_0, cap_1, cap_2, cap_3;
  wire         irq;

  reg          awvalid = 1'b0, wvalid = 1'b0, arvalid = 1'b0;
  reg  [15:0]  awaddr = 0, araddr = 0;
  reg  [31:0]  wdata = 0;
  wire         awready, wready, bvalid, arready, rvalid;
  wire [ 1:0]  bresp, rresp;
  wire [31:0]  rdata;

  crpa_core #(.ID (5)) dut (
    .clk (clk), .rst (rst),
    .adc_valid (adc_valid),
    .adc_data_i0 (adc_i0), .adc_data_q0 (adc_q0), .adc_data_i1 (adc_i1), .adc_data_q1 (adc_q1),
    .cap_valid (cap_valid), .cap_data_0 (cap_0), .cap_data_1 (cap_1), .cap_data_2 (cap_2),
    .cap_data_3 (cap_3),
    .dma_dac_data_i0 (dma_i0), .dma_dac_data_q0 (dma_q0), .dma_dac_data_i1 (dma_i1),
    .dma_dac_data_q1 (dma_q1),
    .dac_data_i0 (dac_i0), .dac_data_q0 (dac_q0), .dac_data_i1 (dac_i1), .dac_data_q1 (dac_q1),
    .irq (irq),
    .s_axi_aclk (aclk), .s_axi_aresetn (aresetn),
    .s_axi_awvalid (awvalid), .s_axi_awaddr (awaddr), .s_axi_awprot (3'd0), .s_axi_awready (awready),
    .s_axi_wvalid (wvalid), .s_axi_wdata (wdata), .s_axi_wstrb (4'hf), .s_axi_wready (wready),
    .s_axi_bvalid (bvalid), .s_axi_bresp (bresp), .s_axi_bready (1'b1),
    .s_axi_arvalid (arvalid), .s_axi_araddr (araddr), .s_axi_arprot (3'd0), .s_axi_arready (arready),
    .s_axi_rvalid (rvalid), .s_axi_rresp (rresp), .s_axi_rdata (rdata), .s_axi_rready (1'b1));

  // register byte offsets (docs/regmap.md)
  localparam VERSION = 16'h00, ID = 16'h04, SCRATCH = 16'h08, CTRL = 16'h0c, STATUS = 16'h10,
             INT_LEN = 16'h14, W1 = 16'h18, W2 = 16'h1c, OUT_SHIFT = 16'h20, UPDATE = 16'h24,
             MISSED = 16'h28, R11_LO = 16'h40, SAT_CNT = 16'h60, PEAK = 16'h64, SEQ = 16'h68;
  localparam C_SOFT_RST = 1, C_COV_EN = 2, C_DAC_SEL = 4, C_CAP_SEL = 8;
  localparam S_DONE = 1, S_W_BUSY = 2, S_FRAME_ERR = 4, S_RES_DROP = 8;

  integer errors = 0;

  task fail;
    input [8*96-1:0] msg;
    begin
      errors = errors + 1;
      if (errors <= 30) $display("ERROR %0s", msg);
    end
  endtask

  // AXI-Lite master. Calls are serialized by axi_busy (two processes use the bus).

  reg axi_busy = 1'b0;

  task axi_write;
    input [15:0] addr;
    input [31:0] data;
    begin
      while (axi_busy) @(posedge aclk);
      axi_busy = 1'b1;
      @(posedge aclk);
      #1 awvalid = 1'b1; wvalid = 1'b1; awaddr = addr; wdata = data;
      @(posedge aclk);
      while (!(awready && wready)) @(posedge aclk);
      #1 awvalid = 1'b0; wvalid = 1'b0;
      while (!bvalid) @(posedge aclk);
      @(posedge aclk);
      axi_busy = 1'b0;
    end
  endtask

  task axi_read;
    input  [15:0] addr;
    output [31:0] data;
    begin
      while (axi_busy) @(posedge aclk);
      axi_busy = 1'b1;
      @(posedge aclk);
      #1 arvalid = 1'b1; araddr = addr;
      @(posedge aclk);
      while (!arready) @(posedge aclk);
      #1 arvalid = 1'b0;
      while (!rvalid) @(posedge aclk);
      data = rdata;
      @(posedge aclk);
      axi_busy = 1'b0;
    end
  endtask

  task expect_reg;
    input [15:0] addr;
    input [31:0] mask;
    input [31:0] value;
    reg   [31:0] v;
    begin
      axi_read(addr, v);
      if ((v & mask) !== value) begin
        errors = errors + 1;
        $display("ERROR reg 0x%h = 0x%h, expected 0x%h (mask 0x%h)", addr, v, value, mask);
      end
    end
  endtask

  task wait_status;      // wait until (STATUS & mask) == value, up to n reads
    input [31:0] mask;
    input [31:0] value;
    input integer n;
    reg   [31:0] v;
    integer i;
    begin
      v = ~value;
      for (i = 0; i < n && (v & mask) != value; i = i + 1) axi_read(STATUS, v);
      if ((v & mask) != value) begin
        errors = errors + 1;
        $display("ERROR STATUS 0x%h, waiting for 0x%h (mask 0x%h)", v, value, mask);
      end
    end
  endtask

  task write_set;
    input integer k;
    begin
      // set_mem: {w1i, w1q, w2i, w2q, shift}; W1/W2 registers are {q, i}
      axi_write(W1, {set_mem[k][63:48], set_mem[k][79:64]});
      axi_write(W2, {set_mem[k][31:16], set_mem[k][47:32]});
      axi_write(OUT_SHIFT, set_mem[k][15:0]);
      axi_write(UPDATE, 32'd1);
    end
  endtask

  // ADC stimulus (l_clk)

  reg  run_stream = 1'b0;
  reg  run_dummy = 1'b0;
  reg  manual = 1'b0;       // the initial block drives adc_valid itself
  reg  stream_done = 1'b0;
  integer s_in = 0;

  always @(posedge clk) begin
    if (run_stream && s_in < n_samples) begin
      if (!adc_valid) begin
        adc_valid <= 1'b1;
        {adc_i0, adc_q0, adc_i1, adc_q1} <= in_mem[s_in];
        s_in = s_in + 1;
      end else begin
        adc_valid <= 1'b0;
      end
    end else if (run_dummy) begin
      adc_valid <= ~adc_valid;
      {adc_i0, adc_q0, adc_i1, adc_q1} <= {16'h0123, 16'h0fed, 16'h0800, 16'h07ff};
    end else if (!manual) begin
      adc_valid <= 1'b0;
      if (run_stream && s_in >= n_samples) stream_done <= 1'b1;
    end
  end

  // capture checker (combined mode during the stream)

  reg  check_cap = 1'b0;
  integer n_cap = 0;
  integer cur_set = 0;
  integer req_set = 0;       // set most recently written by the PS process
  integer n_switch_seen = 0;

  always @(posedge clk) begin
    if (check_cap && cap_valid) begin
      if (n_cap >= n_samples) begin
        fail("extra capture output");
      end else begin
        if (cap_2[11:0] !== in_mem[n_cap][59:48] || cap_3[11:0] !== in_mem[n_cap][43:32] ||
            cap_2[15:12] !== {4{cap_2[11]}} || cap_3[15:12] !== {4{cap_3[11]}})
          fail("capture x1 does not match the input of the same sample");
        if (dac_i0 !== {cap_0[11:0], 4'd0} || dac_q0 !== {cap_1[11:0], 4'd0} ||
            dac_i1 !== 16'd0 || dac_q1 !== 16'd0)
          fail("DAC output differs from the capture y, or ch2/3 not zero");
        if (cap_0[15:12] !== {4{cap_0[11]}} || cap_1[15:12] !== {4{cap_1[11]}})
          fail("capture y not sign-extended");
        if ({cap_0[11:0], 4'd0, cap_1[11:0], 4'd0} === out_mem[cur_set * MAXN + n_cap]) begin
          // current set
        end else if (cur_set < req_set &&
                     {cap_0[11:0], 4'd0, cap_1[11:0], 4'd0} === out_mem[(cur_set + 1) * MAXN + n_cap]) begin
          cur_set = cur_set + 1;
          n_switch_seen = n_switch_seen + 1;
        end else begin
          errors = errors + 1;
          if (errors <= 30)
            $display("ERROR sample %0d: y %h %h matches neither set %0d nor the next (%0d written)",
              n_cap, cap_0, cap_1, cur_set, req_set);
        end
      end
      n_cap = n_cap + 1;
    end
  end

  // PS process: read a finished block and compare

  integer n_read = 0;
  reg [31:0] missed_prev = 0;

  task read_block;
    output integer seq;
    reg [31:0] v, lo, hi;
    reg [255:0] r;
    reg [31:0] sat, pk;
    integer i;
    begin
      for (i = 0; i < 4; i = i + 1) begin
        axi_read(R11_LO + 8 * i, lo);
        axi_read(R11_LO + 8 * i + 4, hi);
        r[255 - 64 * i -: 64] = {hi, lo};
      end
      axi_read(SAT_CNT, sat);
      axi_read(PEAK, pk);
      axi_read(SEQ, v);
      seq = v;
      if (seq >= n_blocks) begin
        fail("SEQ beyond the vector blocks");
      end else begin
        if (r !== cov_mem[seq]) begin
          errors = errors + 1;
          $display("ERROR block %0d: R %h, expected %h", seq, r, cov_mem[seq]);
        end
        if (pk !== {4'd0, bst_mem[seq][11:0], 4'd0, bst_mem[seq][27:16]}) begin   // {peak2, peak1}
          errors = errors + 1;
          $display("ERROR block %0d: PEAK %h, expected %h %h", seq, pk, bst_mem[seq][31:16], bst_mem[seq][15:0]);
        end
        if (sat > int_len_v) fail("SAT_CNT larger than the block");
      end
    end
  endtask

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
        end
      end
      $fclose(fd);
    end
  endtask

  reg [1023:0] fname;
  reg [31:0] v;
  integer k, seq, last_seq, n_seen, missed_total;
  reg [31:0] st;

  initial begin
    if (!$value$plusargs("VEC=%s", vec)) begin
      $display("FAIL need +VEC=<dir>");
      $finish;
    end
    read_meta;
    if (n_samples > MAXN || n_sets > 8 || n_blocks > 64) begin
      $display("FAIL vectors larger than the testbench arrays");
      $finish;
    end
    $readmemh({vec, "/input.mem"}, in_mem, 0, n_samples - 1);
    $readmemh({vec, "/sets.mem"}, set_mem, 0, n_sets - 1);
    $readmemh({vec, "/cov.mem"}, cov_mem, 0, n_blocks - 1);
    $readmemh({vec, "/blkstat.mem"}, bst_mem, 0, n_blocks - 1);
    for (k = 0; k < n_sets; k = k + 1) begin
      $sformat(fname, "%0s/out_%0d.mem", vec, k);
      $readmemh(fname, out_mem, k * MAXN, k * MAXN + n_samples - 1);
    end

    // 1. reset values
    repeat (10) @(posedge aclk);
    aresetn = 1'b1;
    repeat (3) @(posedge clk);
    #1 rst = 1'b0;
    expect_reg(VERSION, 32'hffffffff, 32'h00010000);
    expect_reg(ID, 32'hffffffff, 32'd5);
    axi_write(SCRATCH, 32'hdeadbeef);
    expect_reg(SCRATCH, 32'hffffffff, 32'hdeadbeef);
    expect_reg(CTRL, 32'hffffffff, 32'd0);
    expect_reg(INT_LEN, 32'hffffffff, 32'd10000);
    expect_reg(W1, 32'hffffffff, 32'h00007fff);
    expect_reg(W2, 32'hffffffff, 32'd0);
    expect_reg(OUT_SHIFT, 32'hffffffff, 32'd0);
    expect_reg(MISSED, 32'hffffffff, 32'd0);
    run_dummy = 1'b1;
    repeat (200) @(posedge aclk);
    expect_reg(STATUS, 32'hffffffff, 32'd0);
    if (irq !== 1'b0) fail("irq high after reset");
    if ({dac_i0, dac_q0, dac_i1, dac_q1} !== {dma_i0, dma_q0, dma_i1, dma_q1})
      fail("DAC mux does not pass the DMA data after reset");
    #3 dma_i0 = 16'h5550;
    #1 if (dac_i0 !== 16'h5550) fail("DAC mux DMA path is not combinational");
    @(posedge clk);
    while (!cap_valid) @(posedge clk);
    if ({cap_0, cap_1, cap_2, cap_3} !== {16'h0123, 16'h0fed, 16'h0800, 16'h07ff})
      fail("raw capture does not pass the ADC data");
    axi_write(INT_LEN, 32'd0);
    expect_reg(INT_LEN, 32'hffffffff, 32'd1);

    // 2. set 0, then enable with the ADC stopped, so that block 0 starts at sample 0
    axi_write(INT_LEN, int_len_v);
    write_set(0);
    req_set = 0;
    wait_status(S_W_BUSY, 0, 200);
    run_dummy = 1'b0;
    repeat (20) @(posedge clk);
    axi_write(CTRL, C_COV_EN | C_DAC_SEL | C_CAP_SEL);
    repeat (400) @(posedge aclk);     // up_xfer_cntrl: well under 2 x 64 cycles plus sync

    // 3. stream, with weight switches and block reads
    check_cap = 1'b1;
    run_stream = 1'b1;
    last_seq = -1;
    n_seen = 0;
    k = 1;
    while (!stream_done) begin
      if (k < n_sets && s_in >= k * n_samples / n_sets) begin
        req_set = k;
        write_set(k);
        k = k + 1;
      end
      axi_read(STATUS, st);
      if (st[0] && !irq) fail("irq low while STATUS.DONE is set");   // only the PS clears DONE
      if (st[0]) begin
        read_block(seq);
        if (seq <= last_seq) fail("SEQ did not increase");
        last_seq = seq;
        n_seen = n_seen + 1;
        axi_write(STATUS, S_DONE);
      end
    end
    repeat (50) @(posedge clk);
    axi_read(STATUS, st);
    if (st[0]) begin
      read_block(seq);
      if (seq <= last_seq) fail("SEQ did not increase");
      last_seq = seq;
      n_seen = n_seen + 1;
      axi_write(STATUS, S_DONE);
    end
    axi_read(MISSED, v);
    missed_total = v;
    if (n_cap != n_samples) begin
      errors = errors + 1;
      $display("ERROR %0d capture outputs, expected %0d", n_cap, n_samples);
    end
    if (cur_set != n_sets - 1) begin
      errors = errors + 1;
      $display("ERROR output reached set %0d of %0d", cur_set, n_sets - 1);
    end
    if (last_seq != n_blocks - 1) begin
      errors = errors + 1;
      $display("ERROR last block read %0d, expected %0d", last_seq, n_blocks - 1);
    end
    if (n_seen + missed_total != n_blocks) begin
      errors = errors + 1;
      $display("ERROR %0d blocks read + %0d missed, expected %0d", n_seen, missed_total, n_blocks);
    end
    expect_reg(STATUS, S_RES_DROP | S_FRAME_ERR | S_W_BUSY, 0);
    check_cap = 1'b0;
    run_stream = 1'b0;

    // 4. not reading: DONE keeps the first block, MISSED counts the rest
    axi_write(MISSED, 0);
    axi_write(INT_LEN, 50);
    repeat (400) @(posedge aclk);
    axi_write(STATUS, S_DONE);
    run_dummy = 1'b1;
    wait_status(S_DONE, S_DONE, 200);
    axi_read(SEQ, v);
    seq = v;
    repeat (50 * 2 * 6) @(posedge clk);    // about 6 more blocks
    axi_read(SEQ, v);
    if (v != seq) fail("results changed while DONE was set");
    axi_read(MISSED, v);
    if (v < 4 || v > 8) begin
      errors = errors + 1;
      $display("ERROR MISSED %0d, expected about 6", v);
    end
    expect_reg(STATUS, S_RES_DROP, 0);

    // 5. INT_LEN 1: a block every sample, faster than the handshake
    axi_write(INT_LEN, 1);
    axi_write(STATUS, S_DONE);
    repeat (400) @(posedge aclk);
    wait_status(S_RES_DROP, S_RES_DROP, 200);
    axi_write(CTRL, C_DAC_SEL | C_CAP_SEL);       // COV_EN off, then clear
    repeat (400) @(posedge aclk);
    axi_write(STATUS, S_RES_DROP | S_DONE);
    wait_status(S_RES_DROP, 0, 200);

    // 6. frame hazard: two adc_valid in a row
    run_dummy = 1'b0;
    repeat (10) @(posedge clk);
    manual = 1'b1;
    #1 adc_valid = 1'b1;
    repeat (2) @(posedge clk);
    #1 adc_valid = 1'b0;
    manual = 1'b0;
    wait_status(S_FRAME_ERR, S_FRAME_ERR, 200);
    axi_write(STATUS, S_FRAME_ERR);
    wait_status(S_FRAME_ERR, 0, 200);

    // 7. soft reset restarts the block numbering; DAC_SEL 0 restores the DMA path
    axi_write(INT_LEN, 40);
    axi_write(CTRL, C_COV_EN | C_DAC_SEL | C_CAP_SEL);
    run_dummy = 1'b1;
    wait_status(S_DONE, S_DONE, 200);
    axi_write(STATUS, S_DONE);
    wait_status(S_DONE, S_DONE, 200);
    axi_read(SEQ, v);
    if (v == 0) fail("SEQ 0 before the soft reset (test setup)");
    axi_write(CTRL, C_SOFT_RST | C_COV_EN | C_DAC_SEL | C_CAP_SEL);
    repeat (400) @(posedge aclk);
    axi_write(CTRL, C_COV_EN | C_DAC_SEL | C_CAP_SEL);
    axi_write(STATUS, S_DONE);
    wait_status(S_DONE, S_DONE, 200);
    axi_read(SEQ, v);
    if (v != 0) begin
      errors = errors + 1;
      $display("ERROR SEQ %0d after soft reset, expected 0", v);
    end
    axi_write(CTRL, 0);
    repeat (400) @(posedge aclk);
    if ({dac_i0, dac_q0, dac_i1, dac_q1} !== {dma_i0, dma_q0, dma_i1, dma_q1})
      fail("DAC mux does not return to the DMA data");

    if (errors == 0) begin
      $display("PASS core l_clk %0.3f ns: %0d samples, %0d weight switches seen, %0d blocks read, %0d missed",
        lclk_ns, n_cap, n_switch_seen, n_seen, missed_total);
    end else begin
      $display("FAIL core l_clk %0.3f ns: %0d errors", lclk_ns, errors);
    end
    $finish;
  end

  initial begin
    #20_000_000;
    $display("FAIL timeout");
    $finish;
  end

endmodule
