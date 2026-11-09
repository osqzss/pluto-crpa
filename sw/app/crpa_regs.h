/*
 * crpa_core register map (docs/regmap.md, IP version 1.0).
 * Byte offsets from the start of the UIO map (0x7C450000).
 */
#ifndef CRPA_REGS_H
#define CRPA_REGS_H

#define CRPA_VERSION    0x00
#define CRPA_ID         0x04
#define CRPA_SCRATCH    0x08
#define CRPA_CTRL       0x0C
#define CRPA_STATUS     0x10
#define CRPA_INT_LEN    0x14
#define CRPA_W1         0x18
#define CRPA_W2         0x1C
#define CRPA_OUT_SHIFT  0x20
#define CRPA_UPDATE     0x24
#define CRPA_MISSED     0x28
#define CRPA_R11_LO     0x40
#define CRPA_R11_HI     0x44
#define CRPA_R22_LO     0x48
#define CRPA_R22_HI     0x4C
#define CRPA_R21RE_LO   0x50
#define CRPA_R21RE_HI   0x54
#define CRPA_R21IM_LO   0x58
#define CRPA_R21IM_HI   0x5C
#define CRPA_SAT_CNT    0x60
#define CRPA_PEAK       0x64
#define CRPA_SEQ        0x68

#define CRPA_VERSION_MAJOR(v)  (((v) >> 16) & 0xffff)
#define CRPA_VERSION_EXPECTED  0x00010000u

/* CTRL */
#define CTRL_SOFT_RST   (1u << 0)
#define CTRL_COV_EN     (1u << 1)
#define CTRL_DAC_SEL    (1u << 2)
#define CTRL_CAP_SEL    (1u << 3)

/* STATUS */
#define ST_DONE         (1u << 0)   /* R/W1C, drives irq */
#define ST_W_BUSY       (1u << 1)
#define ST_FRAME_ERR    (1u << 2)   /* sticky; write 1 to bit 2 or 3 clears both */
#define ST_RES_DROP     (1u << 3)
#define ST_CLEAR_ALL    (ST_DONE | ST_FRAME_ERR | ST_RES_DROP)  /* 0xD */

#define INT_LEN_MAX     ((1u << 24) - 1)
#define SHIFT_MAX       15
#define W_UNITY         0x7FFF

/* Weight register: {q[31:16], i[15:0]}, Q1.15 */
#define W_PACK(i, q)    ((((unsigned)(q) & 0xffffu) << 16) | ((unsigned)(i) & 0xffffu))

#endif
