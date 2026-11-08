####################################################################################
## crpa_core IP, ADI hdl library style.
## Build: make -C fw/hdl/library/crpa_core xilinx (the link made by scripts/setup.sh),
## or from the hdl project through LIB_DEPS. make changes into the real directory,
## ip/crpa_core, so the ADI paths are found from this file's location, not with ../.
####################################################################################

CRPA_DIR := $(patsubst %/,%,$(dir $(realpath $(firstword $(MAKEFILE_LIST)))))
HDL_DIR := $(realpath $(CRPA_DIR)/../../fw/hdl)

LIBRARY_NAME := crpa_core

GENERIC_DEPS += $(HDL_DIR)/library/common/up_axi.v
GENERIC_DEPS += $(HDL_DIR)/library/common/up_xfer_cntrl.v
GENERIC_DEPS += $(HDL_DIR)/library/common/up_xfer_status.v
GENERIC_DEPS += rtl/crpa_dp.v
GENERIC_DEPS += rtl/crpa_core.v

XILINX_DEPS += $(HDL_DIR)/library/xilinx/common/up_xfer_cntrl_constr.xdc
XILINX_DEPS += $(HDL_DIR)/library/xilinx/common/up_xfer_status_constr.xdc
XILINX_DEPS += crpa_core_constr.xdc
XILINX_DEPS += crpa_core_ip.tcl

include $(HDL_DIR)/library/scripts/library.mk
