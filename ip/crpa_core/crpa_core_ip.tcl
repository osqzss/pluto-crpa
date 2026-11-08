###############################################################################
## crpa_core IP packaging, ADI hdl library style (see Makefile).
###############################################################################

# This directory is ip/crpa_core, also when reached through fw/hdl/library/crpa_core.
set crpa_dir [file normalize [file dirname [info script]]]
source [file join $crpa_dir ../../fw/hdl/scripts/adi_env.tcl]
source $ad_hdl_dir/library/scripts/adi_ip_xilinx.tcl

# The project reaches this IP through the link fw/hdl/library/crpa_core, and
# Vivado resolves the file paths in component.xml relative to the link, not to
# ip/crpa_core. A path out of this directory (../../fw/hdl/library/...) therefore
# breaks in the project build. Copy the ADI common files into adi_common/
# (git-ignored) so that every packaged path stays inside the IP directory.
# The Makefile lists the originals as dependencies, so a change there repackages.
set adi_common_dir [file join $crpa_dir adi_common]
file mkdir $adi_common_dir
set adi_common_files {}
foreach f [list \
  "$ad_hdl_dir/library/common/up_axi.v" \
  "$ad_hdl_dir/library/common/up_xfer_cntrl.v" \
  "$ad_hdl_dir/library/common/up_xfer_status.v" \
  "$ad_hdl_dir/library/xilinx/common/up_xfer_cntrl_constr.xdc" \
  "$ad_hdl_dir/library/xilinx/common/up_xfer_status_constr.xdc" ] {
  file copy -force $f $adi_common_dir
  lappend adi_common_files [file join $adi_common_dir [file tail $f]]
}

adi_ip_create crpa_core
adi_ip_files crpa_core [concat $adi_common_files [list \
  "$crpa_dir/crpa_core_constr.xdc" \
  "$crpa_dir/rtl/crpa_dp.v" \
  "$crpa_dir/rtl/crpa_core.v" ]]

adi_ip_properties crpa_core

set cc [ipx::current_core]
set_property display_name {CRPA core (2-element combiner)} $cc
set_property description {Two-element CRPA combiner and covariance integrator for axi_ad9361 (2R2T)} $cc

ipx::add_bus_parameter ASSOCIATED_BUSIF [ipx::get_bus_interfaces s_axi_aclk -of_objects $cc]
set_property value s_axi [ipx::get_bus_parameters ASSOCIATED_BUSIF \
  -of_objects [ipx::get_bus_interfaces s_axi_aclk -of_objects $cc]]

ipx::infer_bus_interface clk xilinx.com:signal:clock_rtl:1.0 $cc
set reset_intf [ipx::infer_bus_interface rst xilinx.com:signal:reset_rtl:1.0 $cc]
set reset_polarity [ipx::add_bus_parameter "POLARITY" $reset_intf]
set_property value "ACTIVE_HIGH" $reset_polarity

set irq_intf [ipx::infer_bus_interface irq xilinx.com:signal:interrupt_rtl:1.0 $cc]
set irq_sens [ipx::add_bus_parameter "SENSITIVITY" $irq_intf]
set_property value "LEVEL_HIGH" $irq_sens

set_property driver_value 0 [ipx::get_ports *dma_dac_data* -of_objects $cc]

ipx::create_xgui_files $cc
ipx::update_checksums $cc
ipx::save_core $cc
