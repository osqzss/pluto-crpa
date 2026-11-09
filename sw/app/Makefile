# crpa_ctl for the Pluto, built with the toolchain and sysroot of our own
# firmware build (plan Section 7). The Buildroot toolchain wrapper passes
# --sysroot=fw/buildroot/output/staging itself.
#
#   make            cross-compile crpa_ctl
#   make test       host: weight computation against model/crpa_model.py
#   make clean

ROOT     := $(abspath ../..)
BR_OUT   ?= $(ROOT)/fw/buildroot/output
CROSS    ?= $(BR_OUT)/host/bin/arm-none-linux-gnueabihf-
CC       := $(CROSS)gcc
HOSTCC   ?= cc
PYTHON   ?= $(ROOT)/.venv/bin/python
CFLAGS   ?= -O2
CFLAGS   += -std=gnu11 -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers
LDLIBS   := -liio -lm

all: crpa_ctl

crpa_ctl: crpa_ctl.c crpa_pi.c crpa_pi.h crpa_regs.h
	$(CC) $(CFLAGS) -o $@ crpa_ctl.c crpa_pi.c $(LDLIBS)

pi_cli: pi_cli.c crpa_pi.c crpa_pi.h
	$(HOSTCC) -O2 -std=gnu11 -Wall -Wextra -o $@ pi_cli.c crpa_pi.c -lm

test: pi_cli
	$(PYTHON) -I test_pi.py ./pi_cli

clean:
	rm -f crpa_ctl pi_cli

.PHONY: all test clean
