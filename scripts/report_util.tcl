# usage: vivado -mode batch -source report_util.tcl -tclargs <xpr> <outdir>
set xpr    [lindex $argv 0]
set outdir [lindex $argv 1]
file mkdir $outdir
open_project $xpr
open_run impl_1
report_utilization                              -file $outdir/util_placed.rpt
report_utilization -hierarchical -hierarchical_depth 4 -file $outdir/util_hier.rpt
report_timing_summary -max_paths 10             -file $outdir/timing_summary.rpt
close_project
