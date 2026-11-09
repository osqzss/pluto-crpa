/*
 * Host test driver for crpa_pi.c (make test). Reads lines from stdin:
 *   init LOAD ALPHA
 *   blk N R11 R22 R21RE R21IM
 * and prints "w1i w1q w2i w2q" for each blk line.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "crpa_pi.h"

int main(void)
{
	struct pi_loop p;
	char line[512];
	pi_init(&p, 0.0, 0.0);
	while (fgets(line, sizeof(line), stdin)) {
		double load, alpha;
		long long n, a, b, c, d;
		if (sscanf(line, "init %lf %lf", &load, &alpha) == 2) {
			pi_init(&p, load, alpha);
		} else if (sscanf(line, "blk %lld %lld %lld %lld %lld", &n, &a, &b, &c, &d) == 5) {
			struct crpa_r r = { a, b, c, d };
			int16_t w[4];
			pi_update(&p, &r, (uint32_t)n, w);
			printf("%d %d %d %d\n", w[0], w[1], w[2], w[3]);
		} else {
			fprintf(stderr, "bad line: %s", line);
			return 2;
		}
	}
	return 0;
}
