/*
 * PS weight computation, see crpa_pi.h and plan Section 5.4.
 *
 * w ~ inv(R + delta I) e1 ~ [R22 + delta, -R21], delta = load x n.
 * Scaled so that the larger of |w1|, |w2| is 1 (|w2| can exceed |w1| when
 * the jammer is stronger on element 1). w1 is real and positive.
 * The operations follow model/crpa_model.py in the same order, so the
 * results match it exactly in IEEE double.
 */
#include <math.h>
#include "crpa_pi.h"

void pi_init(struct pi_loop *p, double load, double alpha)
{
	p->load = load;
	p->alpha = alpha;
	p->have_r = 0;
	p->r[0] = p->r[1] = p->r[2] = p->r[3] = 0.0;
}

static int16_t q15(double v)
{
	/* np.clip(np.rint(v * 32768.0), -32768, 32767); rint is round half
	 * even in the default rounding mode, as np.rint */
	double x = rint(v * 32768.0);
	if (x > 32767.0)
		x = 32767.0;
	if (x < -32768.0)
		x = -32768.0;
	return (int16_t)x;
}

void pi_quantize(double w1re, double w1im, double w2re, double w2im, int16_t w[4])
{
	w[0] = q15(w1re);
	w[1] = q15(w1im);
	w[2] = q15(w2re);
	w[3] = q15(w2im);
}

void pi_update(struct pi_loop *p, const struct crpa_r *r, uint32_t n, int16_t w[4])
{
	double in[4] = { (double)r->r11, (double)r->r22, (double)r->r21re, (double)r->r21im };
	int k;

	if (!p->have_r) {
		for (k = 0; k < 4; k++)
			p->r[k] = in[k];
		p->have_r = 1;
	} else {
		for (k = 0; k < 4; k++)
			p->r[k] = p->alpha * p->r[k] + (1.0 - p->alpha) * in[k];
	}

	double delta = p->load * (double)n;
	double w1 = p->r[1] + delta;      /* real */
	double w2re = -p->r[2];
	double w2im = -p->r[3];
	double m = fabs(w1);
	double m2 = hypot(w2re, w2im);
	if (m2 > m)
		m = m2;
	if (m == 0.0) {
		pi_quantize(1.0, 0.0, 0.0, 0.0, w);
		return;
	}
	pi_quantize(w1 / m, 0.0, w2re / m, w2im / m, w);
}
