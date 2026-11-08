# Out-of-context synthesis and implementation of crpa_core alone, for resources and
# timing before block design integration. Clocks: clk (l_clk) 61.44 MHz, the highest
# rate; s_axi_aclk 100 MHz. Reports go to the directory given as the first argument.
# Usage: vivado -mode batch -source scripts/ooc_crpa.tcl -tclargs <out dir>
set out [lindex $argv 0]
set root [file normalize [file join [file dirname [info script]] ..]]
set lib $root/fw/hdl/library
file mkdir $out
read_verilog [list $lib/common/up_axi.v $lib/common/up_xfer_cntrl.v $lib/common/up_xfer_status.v \
  $root/ip/crpa_core/rtl/crpa_dp.v $root/ip/crpa_core/rtl/crpa_core.v]
synth_design -top crpa_core -part xc7z010clg225-1 -mode out_of_context
create_clock -name l_clk -period 16.276 [get_ports clk]
create_clock -name s_axi_aclk -period 10.000 [get_ports s_axi_aclk]
read_xdc [list $lib/xilinx/common/up_xfer_cntrl_constr.xdc $lib/xilinx/common/up_xfer_status_constr.xdc \
  $root/ip/crpa_core/crpa_core_constr.xdc]
# In the block design the two clocks are asynchronous; any path left between them
# would be a missing CDC constraint, so report them instead of hiding them here.
opt_design
place_design
route_design
report_utilization -file $out/util.rpt
report_utilization -hierarchical -file $out/util_hier.rpt
report_timing_summary -file $out/timing_summary.rpt
report_clock_interaction -file $out/clock_interaction.rpt
report_cdc -file $out/cdc.rpt
report_methodology -file $out/methodology.rpt
