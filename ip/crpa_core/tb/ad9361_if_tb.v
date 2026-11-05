// Characterization testbench for the unmodified ADI axi_ad9361 core, as
// instantiated by projects/pluto (CMOS, 2R2T). Not a test of crpa_core: it checks
// the facts recorded in docs/interface.md. Run with scripts/sim_ad9361_if.sh.
//
// The AD9361 side is a model of the data port written from the HDL delineation
// logic and the driver settings. It does not prove how the real chip drives the
// frame; FRAME_ALIGN covers both frame alignments the HDL accepts.
//
// FRAME_ALIGN = 0: I0 is captured on a falling l_clk edge (rx_frame_s = 11/00).
// FRAME_ALIGN = 1: I0 is captured on a rising l_clk edge (rx_frame_s = 01/10).
//
// Prints "FAIL" for every failed check and a final "RESULT" line.

`timescale 1ns/100ps

module ad9361_if_tb;

  parameter FRAME_ALIGN = 0;
  parameter T_LCLK = 50;         // 20 MHz l_clk, the expected rate for fs = 10 MSPS

  // clocks

  reg rx_clk_in = 1'b0;
  reg axi_clk = 1'b0;
  reg delay_clk = 1'b0;
  always #(T_LCLK/2.0) rx_clk_in = ~rx_clk_in;
  always #5.0 axi_clk = ~axi_clk;
  always #2.5 delay_clk = ~delay_clk;

  // dut

  reg axi_rstn = 1'b0;
  reg rx_frame_in = 1'b0;
  reg [11:0] rx_data_in = 12'd0;
  wire l_clk, rst;
  wire tx_clk_out, tx_frame_out;
  wire [11:0] tx_data_out;
  wire adc_enable_i0, adc_enable_q0, adc_enable_i1, adc_enable_q1;
  wire adc_valid_i0, adc_valid_q0, adc_valid_i1, adc_valid_q1;
  wire [15:0] adc_data_i0, adc_data_q0, adc_data_i1, adc_data_q1;
  wire dac_enable_i0, dac_enable_q0, dac_enable_i1, dac_enable_q1;
  wire dac_valid_i0, dac_valid_q0, dac_valid_i1, dac_valid_q1;
  reg [15:0] dac_data_i0 = 0, dac_data_q0 = 0, dac_data_i1 = 0, dac_data_q1 = 0;
  wire adc_r1_mode, dac_r1_mode;

  reg awvalid = 0, wvalid = 0, bready = 1, arvalid = 0, rready = 1;
  reg [15:0] awaddr = 0, araddr = 0;
  reg [31:0] wdata = 0;
  wire awready, wready, bvalid, arready, rvalid;
  wire [1:0] bresp, rresp;
  wire [31:0] rdata;

  axi_ad9361 #(
    .ID (0),
    .MODE_1R1T (0),
    .FPGA_TECHNOLOGY (1),
    .CMOS_OR_LVDS_N (1),
    .ADC_INIT_DELAY (21)
  ) dut (
    .rx_clk_in_p (1'b0), .rx_clk_in_n (1'b0), .rx_frame_in_p (1'b0), .rx_frame_in_n (1'b0),
    .rx_data_in_p (6'd0), .rx_data_in_n (6'd0),
    .rx_clk_in (rx_clk_in), .rx_frame_in (rx_frame_in), .rx_data_in (rx_data_in),
    .tx_clk_out_p (), .tx_clk_out_n (), .tx_frame_out_p (), .tx_frame_out_n (),
    .tx_data_out_p (), .tx_data_out_n (),
    .tx_clk_out (tx_clk_out), .tx_frame_out (tx_frame_out), .tx_data_out (tx_data_out),
    .enable (), .txnrx (),
    .dac_sync_in (1'b0), .dac_sync_out (),
    .tdd_sync (1'b0), .tdd_sync_cntr (),
    .gps_pps (1'b0), .gps_pps_irq (),
    .delay_clk (delay_clk),
    .l_clk (l_clk), .clk (l_clk), .rst (rst),
    .adc_enable_i0 (adc_enable_i0), .adc_valid_i0 (adc_valid_i0), .adc_data_i0 (adc_data_i0),
    .adc_enable_q0 (adc_enable_q0), .adc_valid_q0 (adc_valid_q0), .adc_data_q0 (adc_data_q0),
    .adc_enable_i1 (adc_enable_i1), .adc_valid_i1 (adc_valid_i1), .adc_data_i1 (adc_data_i1),
    .adc_enable_q1 (adc_enable_q1), .adc_valid_q1 (adc_valid_q1), .adc_data_q1 (adc_data_q1),
    .adc_dovf (1'b0), .adc_r1_mode (adc_r1_mode),
    .dac_enable_i0 (dac_enable_i0), .dac_valid_i0 (dac_valid_i0), .dac_data_i0 (dac_data_i0),
    .dac_enable_q0 (dac_enable_q0), .dac_valid_q0 (dac_valid_q0), .dac_data_q0 (dac_data_q0),
    .dac_enable_i1 (dac_enable_i1), .dac_valid_i1 (dac_valid_i1), .dac_data_i1 (dac_data_i1),
    .dac_enable_q1 (dac_enable_q1), .dac_valid_q1 (dac_valid_q1), .dac_data_q1 (dac_data_q1),
    .dac_dunf (1'b0), .dac_r1_mode (dac_r1_mode),
    .s_axi_aclk (axi_clk), .s_axi_aresetn (axi_rstn),
    .s_axi_awvalid (awvalid), .s_axi_awaddr (awaddr), .s_axi_awprot (3'd0), .s_axi_awready (awready),
    .s_axi_wvalid (wvalid), .s_axi_wdata (wdata), .s_axi_wstrb (4'hf), .s_axi_wready (wready),
    .s_axi_bvalid (bvalid), .s_axi_bresp (bresp), .s_axi_bready (bready),
    .s_axi_arvalid (arvalid), .s_axi_araddr (araddr), .s_axi_arprot (3'd0), .s_axi_arready (arready),
    .s_axi_rvalid (rvalid), .s_axi_rdata (rdata), .s_axi_rresp (rresp), .s_axi_rready (rready),
    .up_enable (1'b0), .up_txnrx (1'b0),
    .up_dac_gpio_in (32'd0), .up_dac_gpio_out (),
    .up_adc_gpio_in (32'd0), .up_adc_gpio_out ());

  // bookkeeping

  integer errors = 0;
  integer cyc = 0;   // l_clk cycle number; signals read at a posedge belong to cycle cyc

  task check(input cond, input [8*72-1:0] what);
    begin
      if (cond) begin
        $display("PASS  %0s", what);
      end else begin
        $display("FAIL  %0s", what);
        errors = errors + 1;
      end
    end
  endtask

  // axi-lite access (byte addresses, as in the Linux drivers)

  task axi_wr(input [15:0] a, input [31:0] d);
    reg aw_done, w_done;
    begin
      @(posedge axi_clk);
      awaddr <= a; wdata <= d; awvalid <= 1'b1; wvalid <= 1'b1;
      aw_done = 0; w_done = 0;
      while (!(aw_done && w_done)) begin
        @(posedge axi_clk);
        if (awvalid && awready) begin awvalid <= 1'b0; aw_done = 1; end
        if (wvalid && wready) begin wvalid <= 1'b0; w_done = 1; end
      end
      while (!bvalid) @(posedge axi_clk);
      @(posedge axi_clk);
    end
  endtask

  task axi_rd(input [15:0] a, output [31:0] d);
    reg ar_done;
    begin
      @(posedge axi_clk);
      araddr <= a; arvalid <= 1'b1;
      ar_done = 0;
      while (!ar_done) begin
        @(posedge axi_clk);
        if (arvalid && arready) begin arvalid <= 1'b0; ar_done = 1; end
      end
      while (!rvalid) @(posedge axi_clk);
      d = rdata;
      @(posedge axi_clk);
    end
  endtask

  // ad9361 receive port model: DDR words I0 Q0 I1 Q1, frame high for I0 Q0

  localparam F_RUN = 0, F_LOW = 1, F_HIGH = 2;
  integer frame_mode = F_RUN;
  reg rx_run = 1'b0;
  integer rx_pos = 0;
  integer rx_n = 0;
  integer i0_capt_cyc [0:1023];

  // Each word gets a stream tag and a 10-bit sample number. The top bit also
  // follows n[0], so both signs are exercised on every stream.
  function [11:0] rx_word(input integer pos, input integer n);
    reg [1:0] tag;
    begin
      tag = pos[1:0];
      rx_word = {tag[1] ^ n[0], tag[0], n[9:0]};
    end
  endfunction

  always @(rx_clk_in) begin
    #10;
    // the edge that follows this update captures the word just driven
    if (!rx_run && (rx_clk_in == (FRAME_ALIGN == 0))) rx_run = 1'b1;
    if (rx_run) begin
      if (rx_pos == 0) i0_capt_cyc[rx_n % 1024] = cyc;
      rx_data_in = rx_word(rx_pos, rx_n);
      case (frame_mode)
        F_LOW:   rx_frame_in = 1'b0;
        F_HIGH:  rx_frame_in = 1'b1;
        default: rx_frame_in = (rx_pos < 2);
      endcase
      if (rx_pos == 3) begin
        rx_pos = 0;
        rx_n = rx_n + 1;
      end else begin
        rx_pos = rx_pos + 1;
      end
    end
  end

  // dac inputs: every stream carries the cycle number, changing every l_clk, so the
  // word on the tx pins shows exactly which cycle the core read it in. The low
  // nibble is all ones and must not reach the pins.

  function [15:0] tx_word(input [1:0] tag, input integer c);
    tx_word = {tag, c[9:0], 4'hf};
  endfunction

  always @(posedge l_clk) begin
    cyc <= cyc + 1;
    dac_data_i0 <= tx_word(2'd0, cyc + 1);
    dac_data_q0 <= tx_word(2'd1, cyc + 1);
    dac_data_i1 <= tx_word(2'd2, cyc + 1);
    dac_data_q1 <= tx_word(2'd3, cyc + 1);
  end

  // rx monitor

  reg rx_mon = 1'b0;
  integer rx_valid_cnt = 0, rx_gap_err = 0, rx_align_err = 0, rx_data_err = 0, rx_seq_err = 0;
  integer rx_hold_err = 0, rx_last_valid = -1, rx_last_n = -1, rx_lat = -1, rx_lat_err = 0;
  integer rx_n_now;
  integer lat_now;
  reg [15:0] h_i0 = 0, h_q0 = 0, h_i1 = 0, h_q1 = 0;
  reg rx_have = 1'b0;

  function [15:0] sext(input [11:0] w);
    sext = {{4{w[11]}}, w};
  endfunction

  always @(posedge l_clk) if (rx_mon) begin
    if ((adc_valid_i0 != adc_valid_q0) || (adc_valid_i0 != adc_valid_i1) ||
        (adc_valid_i0 != adc_valid_q1)) rx_align_err = rx_align_err + 1;
    if (adc_valid_i0) begin
      rx_valid_cnt = rx_valid_cnt + 1;
      if ((rx_last_valid >= 0) && (cyc - rx_last_valid != 2)) rx_gap_err = rx_gap_err + 1;
      rx_last_valid = cyc;
      rx_n_now = adc_data_i0[9:0];
      if ((adc_data_i0 !== sext(rx_word(0, rx_n_now))) ||
          (adc_data_q0 !== sext(rx_word(1, rx_n_now))) ||
          (adc_data_i1 !== sext(rx_word(2, rx_n_now))) ||
          (adc_data_q1 !== sext(rx_word(3, rx_n_now)))) rx_data_err = rx_data_err + 1;
      if ((rx_last_n >= 0) && (rx_n_now != ((rx_last_n + 1) % 1024))) rx_seq_err = rx_seq_err + 1;
      rx_last_n = rx_n_now;
      lat_now = cyc - i0_capt_cyc[rx_n_now];
      if ((rx_lat >= 0) && (lat_now != rx_lat)) rx_lat_err = rx_lat_err + 1;
      rx_lat = lat_now;
      h_i0 <= adc_data_i0; h_q0 <= adc_data_q0; h_i1 <= adc_data_i1; h_q1 <= adc_data_q1;
      rx_have <= 1'b1;
    end else if (rx_have) begin
      // cycle between two valids: compare with the sample just validated
      if ((adc_data_i0 !== h_i0) || (adc_data_q0 !== h_q0) ||
          (adc_data_i1 !== h_i1) || (adc_data_q1 !== h_q1)) rx_hold_err = rx_hold_err + 1;
    end
  end

  // valid phase and tx valid monitor

  reg tx_mon = 1'b0;
  integer tx_valid_cnt = 0, tx_gap_err = 0, tx_align_err = 0, tx_last_valid = -1;
  integer phase_same = 0, phase_opp = 0;

  always @(posedge l_clk) if (tx_mon) begin
    if ((dac_valid_i0 != dac_valid_q0) || (dac_valid_i0 != dac_valid_i1) ||
        (dac_valid_i0 != dac_valid_q1)) tx_align_err = tx_align_err + 1;
    if (dac_valid_i0) begin
      tx_valid_cnt = tx_valid_cnt + 1;
      if ((tx_last_valid >= 0) && (cyc - tx_last_valid != 2)) tx_gap_err = tx_gap_err + 1;
      tx_last_valid = cyc;
      if (adc_valid_i0) phase_same = phase_same + 1; else phase_opp = phase_opp + 1;
    end
  end

  // tx pin monitor: sample the DDR bus a quarter period after each l_clk edge

  reg pin_mon = 1'b0;
  integer pin_state = 0;
  reg [11:0] w0, w1, w2;
  integer frames = 0, pin_order_err = 0, pin_frame_err = 0, pin_cap_err = 0, pin_lat_err = 0;
  integer pin_lat = -1, pin_cap_phase = -1, pin_nibble_err = 0;
  integer cap_cyc, this_lat, this_phase;
  integer lb_frames = 0, lb_i0q0_err = 0, lb_seq_err = 0, lb_i1q1_zero = 0, lb_i1q1_good = 0;
  integer lb_last_n = -1, lb_lat = -1, lb_n;
  reg lb_mode = 1'b0;
  reg prev_frame = 1'b0;

  always @(l_clk) if (pin_mon) begin
    #(T_LCLK/4.0);
    // two consecutive words with frame high then two with frame low
    case (pin_state)
      0: if (tx_frame_out && !prev_frame) begin w0 = tx_data_out; pin_state = 1; end
      1: begin
           w1 = tx_data_out;
           if (!tx_frame_out) pin_frame_err = pin_frame_err + 1;
           pin_state = 2;
         end
      2: begin
           w2 = tx_data_out;
           if (tx_frame_out) pin_frame_err = pin_frame_err + 1;
           pin_state = 3;
         end
      3: begin
           if (tx_frame_out) pin_frame_err = pin_frame_err + 1;
           frames = frames + 1;
           pin_state = 0;
           if (!lb_mode) begin
             // [11:10] stream tag, [9:0] the cycle in which the core read the word
             if ((w0[11:10] != 2'd0) || (w1[11:10] != 2'd1) || (w2[11:10] != 2'd2) ||
                 (tx_data_out[11:10] != 2'd3)) pin_order_err = pin_order_err + 1;
             if ((w0[9:0] != w1[9:0]) || (w0[9:0] != w2[9:0]) || (w0[9:0] != tx_data_out[9:0]))
               pin_cap_err = pin_cap_err + 1;
             cap_cyc = w0[9:0];
             this_lat = (cyc - cap_cyc + 1024) % 1024;
             if ((pin_lat >= 0) && (this_lat != pin_lat)) pin_lat_err = pin_lat_err + 1;
             pin_lat = this_lat;
             // tx_last_valid is the most recent dac_valid_i0 cycle
             this_phase = (cap_cyc - (tx_last_valid % 1024) + 1024) % 2;
             if ((pin_cap_phase >= 0) && (this_phase != pin_cap_phase)) pin_cap_err = pin_cap_err + 1;
             pin_cap_phase = this_phase;
           end else begin
             // internal loopback (data_sel 8): the pins carry the rx words
             lb_frames = lb_frames + 1;
             lb_n = w0[9:0];
             if ((w0 != rx_word(0, lb_n)) || (w1 != rx_word(1, lb_n))) lb_i0q0_err = lb_i0q0_err + 1;
             if ((lb_last_n >= 0) && (lb_n != ((lb_last_n + 1) % 1024))) lb_seq_err = lb_seq_err + 1;
             lb_last_n = lb_n;
             lb_lat = cyc - i0_capt_cyc[lb_n];
             if ((w2 == 12'd0) && (tx_data_out == 12'd0)) lb_i1q1_zero = lb_i1q1_zero + 1;
             if ((w2 == rx_word(2, lb_n)) && (tx_data_out == rx_word(3, lb_n))) lb_i1q1_good = lb_i1q1_good + 1;
           end
         end
    endcase
    prev_frame = tx_frame_out;
  end

  // frame-stuck monitor

  integer stuck_valid = 0, stuck_cycles = 0;
  reg stuck_mon = 1'b0;
  always @(posedge l_clk) if (stuck_mon) begin
    stuck_cycles = stuck_cycles + 1;
    if (adc_valid_i0) stuck_valid = stuck_valid + 1;
  end

  task wait_lclk(input integer n);
    integer k;
    begin
      for (k = 0; k < n; k = k + 1) @(posedge l_clk);
    end
  endtask

  // register values taken from drivers/iio/adc/ad9361_conv.c, ad9361_post_setup()

  localparam ADC_CH_FMT = (1<<9) | (1<<6) | (1<<4) | (1<<0);  // IQCOR, SIGNEXT, FORMAT, ENABLE

  task setup_core;
    integer ch;
    begin
      axi_wr(16'h0040, 32'h3);                  // adc RSTN
      axi_wr(16'h4040, 32'h3);                  // dac RSTN
      axi_wr(16'h0044, 32'h0);                  // adc r1_mode = 0
      axi_wr(16'h4048, 32'h0);                  // dac r1_mode = 0
      axi_wr(16'h404c, 32'h1);                  // dac rate = 1
      for (ch = 0; ch < 4; ch = ch + 1) begin
        axi_wr(16'h0410 + ch * 16'h40, 32'h0);
        axi_wr(16'h0414 + ch * 16'h40, (ch & 1) ? 32'h00004000 : 32'h40000000);
        axi_wr(16'h0400 + ch * 16'h40, ADC_CH_FMT);
        axi_wr(16'h4418 + ch * 16'h40, 32'h2);  // tx data_sel = DMA
      end
    end
  endtask

  task set_tx_sel(input [3:0] sel);
    integer ch;
    begin
      for (ch = 0; ch < 4; ch = ch + 1) axi_wr(16'h4418 + ch * 16'h40, {28'd0, sel});
    end
  endtask

  // main

  reg [31:0] rd;
  integer i;

  initial begin
    $display("INFO  FRAME_ALIGN=%0d, l_clk period %0d ns", FRAME_ALIGN, T_LCLK);
    #300;
    axi_rstn = 1'b1;
    #100;
    setup_core;
    wait_lclk(100);

    axi_rd(16'h0044, rd); check(rd[2] == 1'b0, "adc r1_mode register reads 0");
    axi_rd(16'h404c, rd); check(rd[15:0] == 16'd1, "dac rate register reads 1");
    check(!adc_r1_mode && !dac_r1_mode, "adc_r1_mode and dac_r1_mode outputs low");
    check(adc_enable_i0 && adc_enable_q0 && adc_enable_i1 && adc_enable_q1, "adc_enable_* high after channel enable");
    check(dac_enable_i0 && dac_enable_q0 && dac_enable_i1 && dac_enable_q1, "dac_enable_* high with data_sel = 2");

    // receive

    rx_mon = 1'b1; tx_mon = 1'b1;
    wait_lclk(800);
    rx_mon = 1'b0; tx_mon = 1'b0;
    check(rx_valid_cnt > 390, "adc_valid_i0 pulses seen");
    check(rx_gap_err == 0, "adc_valid_i0 period is exactly 2 l_clk");
    check(rx_align_err == 0, "adc_valid_i0, q0, i1, q1 coincide");
    check(rx_data_err == 0, "adc_data_* = sign-extended 12-bit words of one sample");
    check(rx_seq_err == 0, "no rx sample lost or repeated");
    check(rx_lat_err == 0, "rx latency constant");
    check(rx_hold_err == 0, "with DC filter off, adc_data_* hold through the non-valid cycle");
    $display("INFO  rx latency: I0 capture cycle to adc_valid_i0 = %0d l_clk", rx_lat);
    check(tx_gap_err == 0, "dac_valid_i0 period is exactly 2 l_clk");
    check(tx_align_err == 0, "dac_valid_i0, q0, i1, q1 coincide");
    $display("INFO  before any dac sync: dac_valid_i0 coincides with adc_valid_i0 %0d times, opposite %0d times",
      phase_same, phase_opp);
    check((phase_same == 0) || (phase_opp == 0), "adc/dac valid phase constant before sync");

    // dac sync, as done by cf_axi_dds_start_sync(): ADI_SYNC in reg 0x4044

    axi_wr(16'h4044, 32'h1);
    wait_lclk(100);
    phase_same = 0; phase_opp = 0; tx_last_valid = -1; tx_gap_err = 0;
    tx_mon = 1'b1; rx_mon = 1'b1;
    wait_lclk(200);
    pin_mon = 1'b1;
    wait_lclk(800);
    pin_mon = 1'b0;
    rx_mon = 1'b0;
    tx_mon = 1'b0;
    wait_lclk(10);
    $display("INFO  after dac sync: dac_valid_i0 coincides with adc_valid_i0 %0d times, opposite %0d times",
      phase_same, phase_opp);
    check(phase_opp == 0, "after sync dac_valid_i0 coincides with adc_valid_i0");
    check(tx_gap_err == 0, "dac_valid_i0 period still 2 l_clk after sync");

    // transmit, data_sel = DMA

    check(frames > 300, "tx frames seen on the pins");
    check(pin_order_err == 0, "tx pin word order is i0 q0 i1 q1");
    check(pin_frame_err == 0, "tx_frame_out high for i0 q0, low for i1 q1");
    check(pin_cap_err == 0, "all four streams read in the same cycle, fixed phase to dac_valid_i0");
    check(pin_lat_err == 0, "tx latency constant");
    $display("INFO  tx read cycle minus dac_valid_i0 cycle, modulo 2 = %0d", pin_cap_phase);
    $display("INFO  tx latency: read cycle to last word (q) on pins = %0d l_clk", pin_lat);

    // internal rx -> tx loopback, data_sel = 8, no ip change needed

    set_tx_sel(4'h8);
    wait_lclk(50);
    check(!dac_enable_i0, "dac_enable_i0 low when data_sel is not DMA");
    lb_mode = 1'b1; pin_state = 0; prev_frame = 1'b1;
    pin_mon = 1'b1;
    wait_lclk(400);
    pin_mon = 1'b0;
    wait_lclk(5);
    check(lb_frames > 150, "data_sel 8: frames seen");
    check(lb_i0q0_err == 0, "data_sel 8: rx ch0/1 words reach tx ch0/1");
    check(lb_seq_err == 0, "data_sel 8: no sample lost or repeated on ch0/1");
    $display("INFO  data_sel 8: tx ch2/3 frames all zero %0d, carrying rx ch2/3 %0d, of %0d",
      lb_i1q1_zero, lb_i1q1_good, lb_frames);
    $display("INFO  data_sel 8: rx I0 capture cycle to last word on pins = %0d l_clk", lb_lat);
    lb_mode = 1'b0;
    set_tx_sel(4'h2);

    // clock monitor register: l_clk cycles per 65536 axi clocks

    wait_lclk(20);
    #700000;
    axi_rd(16'h0054, rd);
    $display("INFO  reg 0x0054 clock monitor = %0d (expected about %0d)", rd, (65536 * 10) / T_LCLK);
    // reads about 0.06% low in simulation (cause not traced); within 0.2% is enough
    // to tell l_clk = 2 x fs from any other integer ratio
    check((rd > (65536 * 10) / T_LCLK * 0.998) && (rd < (65536 * 10) / T_LCLK * 1.002),
      "reg 0x0054 = l_clk cycles per 65536 axi clocks, within 0.2%");

    // status bit with a toggling frame

    axi_rd(16'h005c, rd);
    $display("INFO  reg 0x005c status with toggling frame = 0x%08x", rd);

    // frame not toggling: what the delineation logic does

    frame_mode = F_LOW;
    wait_lclk(20);
    stuck_valid = 0; stuck_cycles = 0; stuck_mon = 1'b1;
    wait_lclk(100);
    stuck_mon = 1'b0;
    axi_rd(16'h005c, rd);
    $display("INFO  frame stuck low:  adc_valid_i0 high %0d of %0d cycles, reg 0x005c = 0x%08x",
      stuck_valid, stuck_cycles, rd);

    frame_mode = F_HIGH;
    wait_lclk(20);
    stuck_valid = 0; stuck_cycles = 0; stuck_mon = 1'b1;
    wait_lclk(100);
    stuck_mon = 1'b0;
    axi_rd(16'h005c, rd);
    $display("INFO  frame stuck high: adc_valid_i0 high %0d of %0d cycles, reg 0x005c = 0x%08x",
      stuck_valid, stuck_cycles, rd);

    if (errors == 0) $display("RESULT PASS FRAME_ALIGN=%0d", FRAME_ALIGN);
    else $display("RESULT FAIL FRAME_ALIGN=%0d errors=%0d", FRAME_ALIGN, errors);
    $finish;
  end

  initial begin
    #3000000;
    $display("RESULT FAIL FRAME_ALIGN=%0d timeout", FRAME_ALIGN);
    $finish;
  end

endmodule
