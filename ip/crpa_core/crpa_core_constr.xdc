###############################################################################
## crpa_core: block result handshake between l_clk and s_axi_aclk.
## crpa_d_res is loaded before crpa_d_req rises and held until the acknowledge
## returns, so it is stable whenever crpa_up_res samples it. The up_xfer_cntrl and
## up_xfer_status crossings use the ADI constraint files.
###############################################################################

set_property ASYNC_REG TRUE [get_cells -hier -filter {name =~ *crpa_up_req_m* && IS_SEQUENTIAL}]
set_property ASYNC_REG TRUE [get_cells -hier -filter {name =~ *crpa_d_ack_m* && IS_SEQUENTIAL}]

set_false_path -to [get_cells -hier -filter {name =~ *crpa_up_req_m1_reg && IS_SEQUENTIAL}]
set_false_path -to [get_cells -hier -filter {name =~ *crpa_d_ack_m1_reg && IS_SEQUENTIAL}]
set_false_path -from [get_cells -hier -filter {name =~ *crpa_d_res_reg* && IS_SEQUENTIAL}] \
               -to [get_cells -hier -filter {name =~ *crpa_up_res_reg* && IS_SEQUENTIAL}]
