/*
 * PS weight computation: power inversion with diagonal loading and IIR
 * smoothing of R. Port of pi_weights(), quantize_weights() and PiLoop in
 * model/crpa_model.py; sw/app/test_pi.py checks that both give the same
 * Q1.15 weights.
 */
#ifndef CRPA_PI_H
#define CRPA_PI_H

#include <stdint.h>

/* One covariance block as read from crpa_core (48-bit values, sign-extended). */
struct crpa_r {
	int64_t r11, r22, r21re, r21im;
};

struct pi_loop {
	double load;     /* diagonal load, LSB^2 per sample */
	double alpha;    /* smoothing: R_s = alpha R_s + (1 - alpha) R; 0 = none */
	int have_r;
	double r[4];     /* smoothed R11, R22, Re R21, Im R21 */
};

void pi_init(struct pi_loop *p, double load, double alpha);

/* Smooth R, then compute the weights for a block of n samples.
 * w = (w1i, w1q, w2i, w2q) in Q1.15. */
void pi_update(struct pi_loop *p, const struct crpa_r *r, uint32_t n, int16_t w[4]);

/* Float weights, larger magnitude scaled to 1, to Q1.15 (round half even, clip). */
void pi_quantize(double w1re, double w1im, double w2re, double w2im, int16_t w[4]);

#endif
