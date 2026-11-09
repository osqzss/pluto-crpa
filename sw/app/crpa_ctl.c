/*
 * crpa_ctl: PS application for the pluto-crpa two-element CRPA.
 * Runs on the Pluto. crpa_core through UIO, the AD9363 through local libiio.
 *
 *   crpa_ctl status                      read-only: AD9363, TX path, crpa_core
 *   crpa_ctl off                         force the safe state
 *   crpa_ctl run [settings]              dry run: path set, TX muted, LO parked
 *   crpa_ctl run --on --tx-att DB --min-tx-att DB [settings]   transmit
 *
 * Conducted or shielded use only. The safety rules are those of
 * scripts/t1_passthrough.py (plan Section 11, T1): --on needs an interactive
 * terminal and the typed word CONDUCTED, TX1 attenuation never goes below
 * --min-tx-att (50 minus the external attenuation in the TX1 path), the TX LO
 * stays powered down and parked at 2400 MHz except while transmitting, and
 * every exit path (quit, end of input, error, SIGINT, SIGTERM, SIGHUP,
 * SIGQUIT) ends in the safe state. The cleanup runs on the Pluto, so a USB
 * or ssh drop (SIGHUP) still reaches it. SIGKILL or a crash does not: then
 * run "crpa_ctl off" or power-cycle the Pluto.
 *
 * Data path while running: crpa_core CTRL = COV_EN | DAC_SEL [| CAP_SEL],
 * TX data_sel = 2 on all four channels, so TX1 carries y and TX2 zero.
 * Weight loop: wait for DONE (irq through /dev/uioN, or --poll-status),
 * read R, clear DONE, compute w, write W1, W2, OUT_SHIFT, UPDATE
 * (docs/regmap.md, PS sequence).
 */
#define _GNU_SOURCE
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <getopt.h>
#include <iio.h>
#include <math.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#include "crpa_regs.h"
#include "crpa_pi.h"

/* ---- constants (as scripts/t1_passthrough.py) ---- */
#define L1            1575420000LL
#define CA_HALF_BW    1023000LL
#define LO_GUARD      500000LL
#define TX_PARK       2400000000LL
#define TX_MAX_ATT    89.75
#define FS_MIN        2084000LL      /* results/t0b_hw_test.md */
#define FS_MAX        30720000LL     /* l_clk = 2 fs <= 61.44 MHz */
#define BW_MIN        200000LL
#define BW_MAX        20000000LL
#define FS_TOL        10
#define BW_TOL        1000
#define LO_TOL        100
#define LO_MATCH_TOL  10
#define CONFIRM       "CONDUCTED"
#define CORE          0x80000000u    /* DEBUGFS_DRA_PCORE_REG_MAGIC */
#define UIO_NAME      "crpa_core"
#define PATH_SEL      2              /* TX data_sel: DMA, which crpa_core drives */

/* axi_ad9361 core registers (docs/interface.md, Section 5) */
#define AD_ADC_R1_MODE   0x0044
#define AD_ADC_STATUS    0x005C
#define AD_DAC_SYNC      0x4044
#define AD_DAC_R1_MODE   0x4048
#define AD_DAC_RATE      0x404C
#define AD_DAC_SEL(c)    (0x4418 + 0x40 * (c))

/* ---- settings ---- */
enum mode { MODE_FIXED, MODE_PI };

struct settings {
	long long delta, fs, bw;
	int rx_gain;
	int on;
	double tx_att, min_tx_att;
	int have_tx_att, have_min_tx_att;
	enum mode mode;
	int16_t w[4];
	int shift;
	double load, alpha;
	uint32_t int_len;
	int cap_sel;
	const char *out;
	int csv_every;
	double duration;
	double monitor;
	int poll_status;
	int rt;            /* SCHED_FIFO priority, 0 = normal scheduling */
};

/* ---- logging ---- */
static FILE *log_fp;
static FILE *csvf;

static void say(const char *fmt, ...)
{
	char buf[1024];
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	/* A closed stdout (ssh gone) must not stop the cleanup: SIGPIPE is ignored. */
	fprintf(stdout, "%s\n", buf);
	fflush(stdout);
	if (log_fp) {
		struct timespec ts;
		clock_gettime(CLOCK_MONOTONIC, &ts);
		fprintf(log_fp, "%10.3f %s\n", ts.tv_sec + ts.tv_nsec * 1e-9, buf);
		fflush(log_fp);
	}
}

static char errbuf[512];

static int fail(const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(errbuf, sizeof(errbuf), fmt, ap);
	va_end(ap);
	return -1;
}

#define TRY(x) do { if ((x) < 0) return -1; } while (0)

/* ---- signals ---- */
static volatile sig_atomic_t stop_sig;
static const int stop_signals[] = { SIGINT, SIGTERM, SIGHUP, SIGQUIT };

static void on_signal(int s)
{
	if (!stop_sig)
		stop_sig = s;
}

static void set_signals(int catch)
{
	struct sigaction sa;
	unsigned i;
	memset(&sa, 0, sizeof(sa));
	sa.sa_handler = catch ? on_signal : SIG_IGN;
	sigemptyset(&sa.sa_mask);
	for (i = 0; i < sizeof(stop_signals) / sizeof(stop_signals[0]); i++)
		sigaction(stop_signals[i], &sa, NULL);
}

static double now(void)
{
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec + ts.tv_nsec * 1e-9;
}

/* ---- crpa_core over UIO ---- */
static volatile uint32_t *core;
static int uio_fd = -1;
static size_t core_size;

static uint32_t rd(unsigned off) { return core[off / 4]; }
static void wr(unsigned off, uint32_t v) { core[off / 4] = v; }

static int read_sysfs(const char *path, char *buf, size_t n)
{
	FILE *f = fopen(path, "r");
	if (!f)
		return -1;
	if (!fgets(buf, (int)n, f)) {
		fclose(f);
		return -1;
	}
	fclose(f);
	buf[strcspn(buf, "\n")] = 0;
	return 0;
}

static int uio_open(void)
{
	DIR *d = opendir("/sys/class/uio");
	struct dirent *e;
	char path[320], buf[64];
	int found = -1;

	if (!d)
		return fail("no /sys/class/uio: UIO not available");
	while ((e = readdir(d))) {
		if (strncmp(e->d_name, "uio", 3))
			continue;
		snprintf(path, sizeof(path), "/sys/class/uio/%s/name", e->d_name);
		if (read_sysfs(path, buf, sizeof(buf)) == 0 && !strcmp(buf, UIO_NAME)) {
			found = atoi(e->d_name + 3);
			break;
		}
	}
	closedir(d);
	if (found < 0)
		return fail("no UIO device named %s (device tree or of_id missing?)", UIO_NAME);
	snprintf(path, sizeof(path), "/sys/class/uio/uio%d/maps/map0/size", found);
	if (read_sysfs(path, buf, sizeof(buf)))
		return fail("cannot read %s", path);
	core_size = strtoul(buf, NULL, 0);
	if (core_size < 0x100)
		return fail("uio%d map0 size %zu is too small", found, core_size);
	snprintf(path, sizeof(path), "/dev/uio%d", found);
	uio_fd = open(path, O_RDWR | O_CLOEXEC);
	if (uio_fd < 0)
		return fail("open %s: %s", path, strerror(errno));
	void *p = mmap(NULL, core_size, PROT_READ | PROT_WRITE, MAP_SHARED, uio_fd, 0);
	if (p == MAP_FAILED)
		return fail("mmap %s: %s", path, strerror(errno));
	core = p;
	uint32_t v = rd(CRPA_VERSION);
	if (CRPA_VERSION_MAJOR(v) != CRPA_VERSION_MAJOR(CRPA_VERSION_EXPECTED))
		return fail("crpa_core VERSION 0x%08x, expected major %u", v,
			    CRPA_VERSION_MAJOR(CRPA_VERSION_EXPECTED));
	return 0;
}

/* Unmask the irq. uio_pdrv_genirq masks it in its handler. */
static int uio_unmask(void)
{
	uint32_t one = 1;
	if (write(uio_fd, &one, sizeof(one)) != sizeof(one))
		return fail("unmask irq: %s", strerror(errno));
	return 0;
}

static int64_t rd48(unsigned lo)
{
	uint32_t l = rd(lo);
	int32_t h = (int32_t)rd(lo + 4);
	return (int64_t)(((uint64_t)(int64_t)h << 32) | l);
}

/* Commit W1, W2, OUT_SHIFT together. */
static void write_weights(const int16_t w[4], int shift)
{
	wr(CRPA_W1, W_PACK(w[0], w[1]));
	wr(CRPA_W2, W_PACK(w[2], w[3]));
	wr(CRPA_OUT_SHIFT, (uint32_t)shift);
	wr(CRPA_UPDATE, 1);
}

static int wait_w_busy(void)
{
	double t0 = now();
	while (rd(CRPA_STATUS) & ST_W_BUSY) {
		if (now() - t0 > 0.5)
			return fail("W_BUSY stays set (l_clk stopped?)");
		usleep(100);
	}
	return 0;
}

/* ---- AD9363 through libiio ---- */
static struct iio_context *ctx;
static struct iio_device *phy, *adc;

static int iio_open(void)
{
	ctx = iio_create_local_context();
	if (!ctx)
		return fail("cannot create the local IIO context");
	phy = iio_context_find_device(ctx, "ad9361-phy");
	adc = iio_context_find_device(ctx, "cf-ad9361-lpc");
	if (!phy || !adc)
		return fail("ad9361-phy or cf-ad9361-lpc not found");
	return 0;
}

static struct iio_channel *chan(const char *name, int out)
{
	return iio_device_find_channel(phy, name, out);
}

static int attr_get(const char *ch, int out, const char *attr, char *buf, size_t n)
{
	struct iio_channel *c = chan(ch, out);
	ssize_t r;
	if (!c)
		return fail("no channel %s", ch);
	r = iio_channel_attr_read(c, attr, buf, n);
	if (r < 0)
		return fail("read %s %s %s: %s", out ? "out" : "in", ch, attr, strerror((int)-r));
	buf[strcspn(buf, "\n")] = 0;
	return 0;
}

static int attr_set(const char *ch, int out, const char *attr, const char *val)
{
	struct iio_channel *c = chan(ch, out);
	ssize_t r;
	if (!c)
		return fail("no channel %s", ch);
	r = iio_channel_attr_write(c, attr, val);
	if (r < 0)
		return fail("write %s %s %s = %s: %s", out ? "out" : "in", ch, attr, val,
			    strerror((int)-r));
	return 0;
}

static int attr_num(const char *ch, int out, const char *attr, double *v)
{
	char buf[128], *end;
	TRY(attr_get(ch, out, attr, buf, sizeof(buf)));
	*v = strtod(buf, &end);
	if (end == buf)
		return fail("%s %s reads '%s', not a number", ch, attr, buf);
	return 0;
}

static int attr_setf(const char *ch, int out, const char *attr, const char *fmt, ...)
{
	char buf[64];
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	return attr_set(ch, out, attr, buf);
}

/* "[min step max]" */
static int attr_range(const char *ch, int out, const char *attr, double *lo, double *hi)
{
	char buf[128];
	double step;
	TRY(attr_get(ch, out, attr, buf, sizeof(buf)));
	if (sscanf(buf, " [ %lf %lf %lf ]", lo, &step, hi) != 3)
		return fail("%s %s reads '%s', not a range", ch, attr, buf);
	return 0;
}

static int reg_get(uint32_t addr, uint32_t *v)
{
	int r = iio_device_reg_read(adc, CORE | addr, v);
	if (r < 0)
		return fail("axi_ad9361 reg 0x%04x read: %s", addr, strerror(-r));
	return 0;
}

static int reg_set(uint32_t addr, uint32_t v)
{
	int r = iio_device_reg_write(adc, CORE | addr, v);
	if (r < 0)
		return fail("axi_ad9361 reg 0x%04x write: %s", addr, strerror(-r));
	return 0;
}

static int get_sel(unsigned sel[4])
{
	unsigned c;
	uint32_t v;
	for (c = 0; c < 4; c++) {
		TRY(reg_get(AD_DAC_SEL(c), &v));
		sel[c] = v & 0xf;
	}
	return 0;
}

static int loopback_get(char *buf, size_t n)
{
	ssize_t r = iio_device_debug_attr_read(phy, "loopback", buf, n);
	if (r < 0)
		return fail("read debugfs loopback: %s", strerror((int)-r));
	buf[strcspn(buf, "\n")] = 0;
	return 0;
}

static int loopback_set(const char *v)
{
	ssize_t r = iio_device_debug_attr_write(phy, "loopback", v);
	if (r < 0)
		return fail("write debugfs loopback: %s", strerror((int)-r));
	return 0;
}

static int tx_att_set(const char *ch, double att)
{
	return attr_setf(ch, 1, "hardwaregain", "%.2f", -att);
}

static int tx_att_get(const char *ch, double *att)
{
	TRY(attr_num(ch, 1, "hardwaregain", att));
	*att = -*att;
	return 0;
}

static int lo_get(const char *ch, long long *f)
{
	double v;
	TRY(attr_num(ch, 1, "frequency", &v));
	*f = llround(v);
	return 0;
}

static int lo_down(int *down)
{
	char buf[16];
	TRY(attr_get("altvoltage1", 1, "powerdown", buf, sizeof(buf)));
	*down = !strcmp(buf, "1");
	return 0;
}

static int adc_ok(int *ok)
{
	uint32_t v;
	TRY(reg_get(AD_ADC_STATUS, &v));
	*ok = v & 1;
	return 0;
}

/* ---- checks ---- */
static int check_tx_att(double att, double min_att, char *msg, size_t n)
{
	if (!(att >= 0 && att <= TX_MAX_ATT))
		snprintf(msg, n, "TX attenuation %g dB is outside 0 to %g", att, TX_MAX_ATT);
	else if (fabs(att * 4 - round(att * 4)) > 1e-9)
		snprintf(msg, n, "TX attenuation %g dB is not a multiple of 0.25", att);
	else if (att < min_att)
		snprintf(msg, n, "TX attenuation %g dB is below the minimum of %g dB", att, min_att);
	else
		return 0;
	return -1;
}

static int refused;

static void refuse(const char *fmt, ...)
{
	char buf[512];
	va_list ap;
	va_start(ap, fmt);
	vsnprintf(buf, sizeof(buf), fmt, ap);
	va_end(ap);
	say("REFUSED: %s", buf);
	refused++;
}

static void check_settings(const struct settings *s)
{
	char msg[256];
	long long edge = llabs(s->delta) + CA_HALF_BW;

	if (llabs(s->delta) < CA_HALF_BW + LO_GUARD)
		refuse("|delta| %lld Hz puts the LO less than %lld Hz from the C/A main lobe",
		       llabs(s->delta), LO_GUARD);
	if (s->fs < FS_MIN || s->fs > FS_MAX)
		refuse("fs %lld is outside %lld to %lld", s->fs, FS_MIN, FS_MAX);
	if (s->bw < BW_MIN || s->bw > BW_MAX)
		refuse("bandwidth %lld is outside %lld to %lld", s->bw, BW_MIN, BW_MAX);
	if (s->bw > s->fs)
		refuse("bandwidth %lld is more than fs %lld", s->bw, s->fs);
	if (edge * 2 > s->bw)
		refuse("signal edge at %lld Hz is outside the bandwidth, +/-%lld Hz", edge, s->bw / 2);
	if (edge * 2 > s->fs)
		refuse("signal edge at %lld Hz is outside fs/2 = %lld Hz", edge, s->fs / 2);
	if (check_tx_att(s->min_tx_att, 0, msg, sizeof(msg)))
		refuse("--min-tx-att: %s", msg);
	else if (s->on && check_tx_att(s->tx_att, s->min_tx_att, msg, sizeof(msg)))
		refuse("%s", msg);
	if (s->int_len < 1 || s->int_len > INT_LEN_MAX)
		refuse("--int-len %u is outside 1 to %u", s->int_len, INT_LEN_MAX);
	if (s->shift < 0 || s->shift > SHIFT_MAX)
		refuse("--shift %d is outside 0 to %d", s->shift, SHIFT_MAX);
	if (!(s->alpha >= 0 && s->alpha < 1))
		refuse("--alpha %g is outside 0 to 1 (exclusive)", s->alpha);
	if (!(s->load >= 0))
		refuse("--load %g is negative", s->load);
	if (s->csv_every < 0)
		refuse("--csv-every %d is negative", s->csv_every);
}

/* Read-only checks of the Pluto before anything is written. */
static void precheck(const struct settings *s)
{
	uint32_t v;
	unsigned sel[4], c;
	char buf[64];
	double lo, hi;

	if (reg_get(AD_ADC_R1_MODE, &v) < 0) { refuse("%s", errbuf); return; }
	if (v & 0x4)
		refuse("ADC r1_mode is set: the Pluto is not in 2R2T");
	if (reg_get(AD_DAC_R1_MODE, &v) < 0) { refuse("%s", errbuf); return; }
	if (v & 0x20)
		refuse("DAC r1_mode is set: the Pluto is not in 2R2T");
	if (reg_get(AD_DAC_RATE, &v) < 0) { refuse("%s", errbuf); return; }
	if (v != 1)
		refuse("DAC rate register is %u, not 1 as in CMOS 2R2T", v);
	if (reg_get(AD_ADC_STATUS, &v) < 0) { refuse("%s", errbuf); return; }
	if (!(v & 1))
		refuse("adc_status is low: RX frame not toggling or delay not locked");
	if (iio_device_attr_read(phy, "ensm_mode", buf, sizeof(buf)) < 0)
		refuse("cannot read ensm_mode");
	else if (buf[strcspn(buf, "\n")] = 0, strcmp(buf, "fdd"))
		refuse("ensm_mode is %s, not fdd", buf);
	if (loopback_get(buf, sizeof(buf)) < 0)
		refuse("%s", errbuf);
	else if (strcmp(buf, "0"))
		refuse("debugfs loopback is %s, not 0: a path may be active. Run 'crpa_ctl off' first", buf);
	if (get_sel(sel) < 0) { refuse("%s", errbuf); return; }
	for (c = 0; c < 4; c++)
		if (sel[c] != 0 && sel[c] != 3) {
			refuse("TX data_sel is [%u %u %u %u]: another path or a TX buffer may be active. "
			       "Run 'crpa_ctl off' first if it is safe to stop it",
			       sel[0], sel[1], sel[2], sel[3]);
			break;
		}
	if (rd(CRPA_CTRL) & (CTRL_DAC_SEL | CTRL_COV_EN))
		refuse("crpa_core CTRL is 0x%x: another crpa_ctl may be running. Run 'crpa_ctl off' "
		       "first if it is safe to stop it", rd(CRPA_CTRL));
	if (attr_range("voltage0", 0, "hardwaregain_available", &lo, &hi) < 0)
		refuse("%s", errbuf);
	else if (s->rx_gain < lo || s->rx_gain > hi)
		refuse("RX gain %d dB is outside %g to %g", s->rx_gain, lo, hi);
	if (attr_range("altvoltage0", 1, "frequency_available", &lo, &hi) < 0)
		refuse("%s", errbuf);
	else if (L1 + s->delta < lo || L1 + s->delta > hi || TX_PARK < lo || TX_PARK > hi)
		refuse("LO %lld or park %lld is outside %g to %g", L1 + s->delta, TX_PARK, lo, hi);
}

/* ---- safe state ---- */
struct step {
	const char *name;
	int (*fn)(void);
	int done;
	char err[512];
};

static int st_att1(void) { return tx_att_set("voltage0", TX_MAX_ATT); }
static int st_att2(void) { return tx_att_set("voltage1", TX_MAX_ATT); }
static int st_loop(void) { return loopback_set("0"); }
static int st_core(void)
{
	/* DAC mux back to DMA, capture raw, blocks stopped. Weights kept. */
	if (!core)
		return fail("crpa_core not mapped");
	wr(CRPA_CTRL, 0);
	if (rd(CRPA_CTRL) != 0)
		return fail("CTRL reads 0x%x", rd(CRPA_CTRL));
	return 0;
}
static int st_sel0(void) { return reg_set(AD_DAC_SEL(0), 0); }
static int st_sel1(void) { return reg_set(AD_DAC_SEL(1), 0); }
static int st_sel2(void) { return reg_set(AD_DAC_SEL(2), 0); }
static int st_sel3(void) { return reg_set(AD_DAC_SEL(3), 0); }
static int st_down(void) { return attr_set("altvoltage1", 1, "powerdown", "1"); }
static int st_park(void) { return attr_setf("altvoltage1", 1, "frequency", "%lld", TX_PARK); }
static int st_verify(void)
{
	double a1, a2;
	long long f;
	int down;
	unsigned sel[4];
	char lb[16], what[128] = "";

	TRY(tx_att_get("voltage0", &a1));
	TRY(tx_att_get("voltage1", &a2));
	if (fabs(a1 - TX_MAX_ATT) > 1e-6 || fabs(a2 - TX_MAX_ATT) > 1e-6)
		strcat(what, " TX attenuation");
	TRY(loopback_get(lb, sizeof(lb)));
	if (strcmp(lb, "0"))
		strcat(what, " loopback");
	TRY(get_sel(sel));
	if (sel[0] || sel[1] || sel[2] || sel[3])
		strcat(what, " data_sel");
	if (core && (rd(CRPA_CTRL) & (CTRL_DAC_SEL | CTRL_CAP_SEL | CTRL_COV_EN)))
		strcat(what, " crpa CTRL");
	TRY(lo_down(&down));
	if (!down)
		strcat(what, " powerdown");
	TRY(lo_get("altvoltage1", &f));
	if (llabs(f - TX_PARK) > LO_TOL)
		strcat(what, " TX LO");
	if (what[0])
		return fail("readback wrong:%s", what);
	return 0;
}

/* Every step runs whatever happened to the others; failed steps get one
 * more try unless nothing at all worked. Returns the number not confirmed. */
static int safe_state(void)
{
	struct step steps[] = {
		{ "TX1 attenuation", st_att1 }, { "TX2 attenuation", st_att2 },
		{ "loopback off", st_loop }, { "crpa_core CTRL", st_core },
		{ "data_sel ch0", st_sel0 }, { "data_sel ch1", st_sel1 },
		{ "data_sel ch2", st_sel2 }, { "data_sel ch3", st_sel3 },
		/* down first, so the tone stops at once and stays off if the retune fails */
		{ "TX LO powerdown", st_down }, { "TX LO park", st_park },
		{ "readback", st_verify },
	};
	int n = sizeof(steps) / sizeof(steps[0]), pass, i, left = n, before;
	sigset_t all, old;

	sigfillset(&all);
	sigprocmask(SIG_BLOCK, &all, &old);
	for (pass = 0; pass < 2 && left; pass++) {
		before = left;
		left = 0;
		for (i = 0; i < n; i++) {
			if (steps[i].done)
				continue;
			if (steps[i].fn() == 0) {
				steps[i].done = 1;
			} else {
				snprintf(steps[i].err, sizeof(steps[i].err), "%s", errbuf);
				left++;
			}
		}
		if (left == before)
			break;  /* nothing worked: no point in retrying */
	}
	for (i = 0; i < n; i++)
		if (!steps[i].done)
			say("SAFE STATE: %s failed: %s", steps[i].name, steps[i].err);
	sigprocmask(SIG_SETMASK, &old, NULL);
	return left;
}

static int finish(int failed, int rc)
{
	if (failed) {
		say("SAFE STATE NOT CONFIRMED (%d steps). TX may still be active: "
		    "run 'crpa_ctl off' or power-cycle the Pluto.", failed);
		return 3;
	}
	say("Safe state: TX attenuation %.2f dB, crpa_core CTRL 0, data_sel 0, "
	    "TX LO powered down at %lld Hz", TX_MAX_ATT, TX_PARK);
	return rc;
}

/* ---- reports ---- */
static void report_rf(void)
{
	long long rxlo = 0, txlo = 0;
	double fs = 0, rbw = 0, tbw = 0, g1 = 0, g2 = 0, a1 = 0, a2 = 0;
	char m1[32] = "?", m2[32] = "?", r1[32] = "?", r2[32] = "?", lb[16] = "?", pd[8] = "?";
	unsigned sel[4] = { 9, 9, 9, 9 };

	lo_get("altvoltage0", &rxlo);
	lo_get("altvoltage1", &txlo);
	attr_num("voltage0", 0, "sampling_frequency", &fs);
	attr_num("voltage0", 0, "rf_bandwidth", &rbw);
	attr_num("voltage0", 1, "rf_bandwidth", &tbw);
	say("RX LO %lld | TX LO %lld | fs %.0f | RX bw %.0f | TX bw %.0f", rxlo, txlo, fs, rbw, tbw);
	attr_get("voltage0", 0, "gain_control_mode", m1, sizeof(m1));
	attr_get("voltage1", 0, "gain_control_mode", m2, sizeof(m2));
	attr_num("voltage0", 0, "hardwaregain", &g1);
	attr_num("voltage1", 0, "hardwaregain", &g2);
	attr_get("voltage0", 0, "rssi", r1, sizeof(r1));
	attr_get("voltage1", 0, "rssi", r2, sizeof(r2));
	say("RX gain %s %.0f / %s %.0f dB | RSSI %s / %s", m1, g1, m2, g2, r1, r2);
	tx_att_get("voltage0", &a1);
	tx_att_get("voltage1", &a2);
	attr_get("altvoltage1", 1, "powerdown", pd, sizeof(pd));
	loopback_get(lb, sizeof(lb));
	get_sel(sel);
	say("TX attenuation %.2f / %.2f dB | TX LO powerdown %s | loopback %s | data_sel [%u %u %u %u]",
	    a1, a2, pd, lb, sel[0], sel[1], sel[2], sel[3]);
}

static void w_text(const int16_t w[4], int shift, char *buf, size_t n)
{
	double g = ldexp(1.0, shift) / 32768.0;
	snprintf(buf, n, "w1 %+.4f%+.4fj w2 %+.4f%+.4fj (|w1| %.3f |w2| %.3f) shift %d",
		 w[0] * g, w[1] * g, w[2] * g, w[3] * g,
		 hypot(w[0], w[1]) / 32768.0, hypot(w[2], w[3]) / 32768.0, shift);
}

static void report_core(void)
{
	uint32_t w1 = rd(CRPA_W1), w2 = rd(CRPA_W2);
	say("crpa_core VERSION 0x%08x CTRL 0x%x STATUS 0x%x INT_LEN %u MISSED %u SEQ %u",
	    rd(CRPA_VERSION), rd(CRPA_CTRL), rd(CRPA_STATUS), rd(CRPA_INT_LEN),
	    rd(CRPA_MISSED), rd(CRPA_SEQ));
	say("crpa_core staged W1 0x%08x W2 0x%08x OUT_SHIFT %u (committed set not readable)",
	    w1, w2, rd(CRPA_OUT_SHIFT));
}

/* ---- configuration ---- */
static int set_rx_gain(int gain, int set_mode)
{
	const char *ch[2] = { "voltage0", "voltage1" };
	char mode[32];
	double got;
	int i;

	for (i = 0; i < 2; i++) {
		if (set_mode)
			TRY(attr_set(ch[i], 0, "gain_control_mode", "manual"));
		TRY(attr_setf(ch[i], 0, "hardwaregain", "%d", gain));
	}
	for (i = 0; i < 2; i++) {
		TRY(attr_num(ch[i], 0, "hardwaregain", &got));
		TRY(attr_get(ch[i], 0, "gain_control_mode", mode, sizeof(mode)));
		if (got != gain || strcmp(mode, "manual"))
			return fail("%s RX gain reads %g %s, wanted %d manual", ch[i], got, mode, gain);
	}
	return 0;
}

/* Everything but the path. The TX LO stays powered down; with tune_tx it moves
 * to L1 + delta, which runs the TX quad calibration there, at maximum
 * attenuation. */
static int configure(const struct settings *s, int tune_tx)
{
	struct { const char *ch; int out; const char *attr; long long val; int tol; } w[] = {
		{ "voltage0", 0, "sampling_frequency", s->fs, FS_TOL },
		{ "voltage0", 0, "rf_bandwidth", s->bw, BW_TOL },
		{ "voltage0", 1, "rf_bandwidth", s->bw, BW_TOL },
	};
	long long target = L1 + s->delta, rxlo, txlo;
	double v, a1, a2;
	int i, down, ok;

	for (i = 0; i < 3; i++) {
		/* skip what would change nothing: each bandwidth write runs a TX quad calibration */
		TRY(attr_num(w[i].ch, w[i].out, w[i].attr, &v));
		if (fabs(v - w[i].val) > w[i].tol)
			TRY(attr_setf(w[i].ch, w[i].out, w[i].attr, "%lld", w[i].val));
		TRY(attr_num(w[i].ch, w[i].out, w[i].attr, &v));
		if (fabs(v - w[i].val) > w[i].tol)
			return fail("%s reads %.0f, wanted %lld", w[i].attr, v, w[i].val);
	}
	TRY(attr_num("voltage0", 1, "sampling_frequency", &v));
	if (fabs(v - s->fs) > FS_TOL)
		return fail("TX sampling frequency %.0f differs from RX %lld", v, s->fs);
	TRY(attr_setf("altvoltage0", 1, "frequency", "%lld", target));
	TRY(lo_get("altvoltage0", &rxlo));
	if (llabs(rxlo - target) > LO_TOL)
		return fail("RX LO reads %lld, wanted %lld", rxlo, target);
	if (tune_tx) {
		TRY(attr_setf("altvoltage1", 1, "frequency", "%lld", target));
		TRY(lo_get("altvoltage1", &txlo));
		if (llabs(txlo - rxlo) > LO_MATCH_TOL)
			return fail("TX LO %lld and RX LO %lld differ", txlo, rxlo);
	}
	TRY(set_rx_gain(s->rx_gain, 1));
	TRY(lo_down(&down));
	if (!down)
		return fail("TX LO came up during configuration");
	TRY(tx_att_get("voltage0", &a1));
	TRY(tx_att_get("voltage1", &a2));
	if (fabs(a1 - TX_MAX_ATT) > 1e-6 || fabs(a2 - TX_MAX_ATT) > 1e-6)
		return fail("TX attenuation changed during configuration");
	usleep(200000);
	TRY(adc_ok(&ok));
	if (!ok)
		return fail("adc_status low after configuration");
	return 0;
}

/* crpa_core start (docs/regmap.md, PS sequence steps 1, 2 and 4), then the TX path. */
static int path_on(const struct settings *s, const int16_t w[4])
{
	unsigned sel[4], c;

	wr(CRPA_INT_LEN, s->int_len);
	if (rd(CRPA_INT_LEN) != s->int_len)
		return fail("INT_LEN reads %u, wanted %u", rd(CRPA_INT_LEN), s->int_len);
	write_weights(w, s->shift);
	TRY(wait_w_busy());
	/* after the rate change in configure(): soft reset, clear all flags */
	wr(CRPA_CTRL, CTRL_SOFT_RST);
	wr(CRPA_CTRL, 0);
	wr(CRPA_STATUS, ST_CLEAR_ALL);
	wr(CRPA_MISSED, 0);      /* any write clears it */
	(void)rd(CRPA_STATUS);
	TRY(uio_unmask());
	wr(CRPA_CTRL, CTRL_COV_EN | CTRL_DAC_SEL | (s->cap_sel ? CTRL_CAP_SEL : 0));
	for (c = 0; c < 4; c++)
		TRY(reg_set(AD_DAC_SEL(c), PATH_SEL));
	TRY(reg_set(AD_DAC_SYNC, 1));   /* repeatable latency (docs/interface.md, Section 4) */
	usleep(1000);
	TRY(get_sel(sel));
	for (c = 0; c < 4; c++)
		if (sel[c] != PATH_SEL)
			return fail("TX data_sel reads [%u %u %u %u], wanted %d",
				    sel[0], sel[1], sel[2], sel[3], PATH_SEL);
	return 0;
}

/* ---- running state ---- */
struct run {
	struct settings *s;
	struct pi_loop pi;
	int16_t w[4];          /* last committed (written with UPDATE) */
	int shift;
	unsigned long blocks;
	unsigned last_seq;
	int have_seq;
	unsigned long seq_gaps;
	double t0, last_block_t;
	double p1, p2, py;      /* last block, dBFS */
	unsigned last_sat;
	unsigned peak1, peak2;
	unsigned long sat_blocks;
};

static double dbfs(double r, uint32_t n)
{
	double p = r / (double)n / (2048.0 * 2048.0);
	return 10.0 * log10(p > 1e-12 ? p : 1e-12);
}

/* Estimated output power from R and the weights in force: y = conj(w1) x1 +
 * conj(w2) x2, so sum|y|^2 = |w1|^2 R11 + |w2|^2 R22 + 2 Re(conj(w1) w2 conj(R21)).
 * The weights written after the previous block take effect early in this block,
 * so this is approximate for the first block after a change. No saturation. */
static double py_est(const struct crpa_r *r, const int16_t w[4], int shift)
{
	double g = ldexp(1.0, shift) / 32768.0;
	double a = w[0] * g, b = w[1] * g, c = w[2] * g, d = w[3] * g;
	/* conj(w1) w2 = (a - jb)(c + jd) = (ac + bd) + j(ad - bc) */
	double xr = a * c + b * d, xi = a * d - b * c;
	/* Re(x conj(R21)) = xr R21re + xi R21im */
	return (a * a + b * b) * r->r11 + (c * c + d * d) * r->r22 +
	       2.0 * (xr * r->r21re + xi * r->r21im);
}

static int block(struct run *R, uint32_t status)
{
	struct settings *s = R->s;
	struct crpa_r r;
	uint32_t sat, peak, seq, missed;
	int16_t wn[4];
	int discard = (R->blocks == 0);
	double t = now();

	r.r11 = rd48(CRPA_R11_LO);
	r.r22 = rd48(CRPA_R22_LO);
	r.r21re = rd48(CRPA_R21RE_LO);
	r.r21im = rd48(CRPA_R21IM_LO);
	sat = rd(CRPA_SAT_CNT) & 0xffffff;
	peak = rd(CRPA_PEAK);
	seq = rd(CRPA_SEQ) & 0xffff;
	missed = rd(CRPA_MISSED);
	wr(CRPA_STATUS, ST_DONE);
	(void)rd(CRPA_STATUS);   /* the clear has reached the core before the unmask */
	if (!s->poll_status)
		TRY(uio_unmask());

	if (!discard && (status & ST_FRAME_ERR))
		return fail("STATUS.FRAME_ERR at a fixed sample rate (STATUS 0x%x, block %lu)",
			    status, R->blocks);
	if (status & ST_RES_DROP) {
		say("WARNING: RES_DROP set (block %lu); clearing it", R->blocks);
		wr(CRPA_STATUS, ST_RES_DROP);
	}
	if (R->have_seq && seq != ((R->last_seq + 1) & 0xffff))
		R->seq_gaps++;
	R->last_seq = seq;
	R->have_seq = 1;

	R->p1 = dbfs((double)r.r11, s->int_len);
	R->p2 = dbfs((double)r.r22, s->int_len);
	R->py = dbfs(py_est(&r, R->w, R->shift), s->int_len);
	R->last_sat = sat;
	R->peak1 = peak & 0xfff;
	R->peak2 = (peak >> 16) & 0xfff;
	if (sat)
		R->sat_blocks++;

	/* first block after the start or a reset: discard (PS sequence step 4) */
	if (!discard && s->mode == MODE_PI) {
		pi_update(&R->pi, &r, s->int_len, wn);
		write_weights(wn, R->shift);
		memcpy(R->w, wn, sizeof(wn));
	}

	if (csvf && s->csv_every && (R->blocks % (unsigned)s->csv_every) == 0)
		fprintf(csvf, "%lu,%u,%.6f,%lld,%lld,%lld,%lld,%u,%u,%u,%u,%u,%d,%d,%d,%d,%d,"
			"%.2f,%.2f,%.2f,%s%s\n",
			R->blocks, seq, t - R->t0, (long long)r.r11, (long long)r.r22,
			(long long)r.r21re, (long long)r.r21im, sat, R->peak1, R->peak2, missed,
			status, R->w[0], R->w[1], R->w[2], R->w[3], R->shift,
			R->p1, R->p2, R->py, s->mode == MODE_PI ? "pi" : "fixed",
			discard ? ",discard" : ",");
	R->blocks++;
	R->last_block_t = t;
	return 0;
}

static void summary(struct run *R)
{
	char wt[160];
	w_text(R->w, R->shift, wt, sizeof(wt));
	say("blocks %lu missed %lu seq_gaps %lu sat_blocks %lu | x1 %.1f x2 %.1f y~ %.1f dBFS | "
	    "peak %u/%u sat %u | %s",
	    R->blocks, (unsigned long)rd(CRPA_MISSED), R->seq_gaps, R->sat_blocks,
	    R->p1, R->p2, R->py, R->peak1, R->peak2, R->last_sat, wt);
}

/* Raise if the running path is no longer what was set up. */
static int monitor(struct run *R)
{
	struct settings *s = R->s;
	unsigned sel[4], c;
	uint32_t want = CTRL_COV_EN | CTRL_DAC_SEL | (s->cap_sel ? CTRL_CAP_SEL : 0);
	long long f;
	double a2;
	int down, ok;

	TRY(get_sel(sel));
	for (c = 0; c < 4; c++)
		if (sel[c] != PATH_SEL)
			return fail("TX data_sel changed to [%u %u %u %u] (a TX buffer or DDS write?)",
				    sel[0], sel[1], sel[2], sel[3]);
	if (rd(CRPA_CTRL) != want)
		return fail("crpa_core CTRL changed to 0x%x", rd(CRPA_CTRL));
	TRY(lo_down(&down));
	TRY(lo_get("altvoltage1", &f));
	if (s->on) {
		if (down)
			return fail("TX LO is powered down");
		if (llabs(f - (L1 + s->delta)) > LO_TOL)
			return fail("TX LO moved to %lld", f);
	} else {
		if (!down)
			return fail("TX LO came up in a dry run");
		if (llabs(f - TX_PARK) > LO_TOL)
			return fail("TX LO left the park frequency in a dry run (%lld)", f);
	}
	TRY(tx_att_get("voltage1", &a2));
	if (fabs(a2 - TX_MAX_ATT) > 1e-6)
		return fail("TX2 attenuation changed");
	TRY(adc_ok(&ok));
	if (!ok)
		return fail("adc_status went low");
	if (now() - R->last_block_t > 1.0 + 20.0 * s->int_len / (double)s->fs)
		return fail("no block for %.1f s (l_clk stopped?)", now() - R->last_block_t);
	return 0;
}

/* ---- interactive commands ---- */
static const char *HELP =
	"Commands:\n"
	"  rx DB          RX gain on both channels (manual)\n"
	"  tx DB          TX1 attenuation, 0.25 dB steps, not below --min-tx-att (with --on)\n"
	"  w A B C D      fixed weights w1 = A + jB, w2 = C + jD (each -1 to 1); stops PI\n"
	"  pi             power inversion from the next block (restarts smoothing)\n"
	"  load L         diagonal load, LSB^2 per sample\n"
	"  shift S        OUT_SHIFT 0..15 (output gain 2^S)\n"
	"  level | s      last block: levels, peaks, weights\n"
	"  status         all settings\n"
	"  note TEXT      add a line to the log, e.g. the receiver C/N0\n"
	"  quit           safe state and exit (also Ctrl-C)";

static int parse_w(const char *txt, int16_t w[4])
{
	double v[4];
	int i;
	if (sscanf(txt, "%lf%*[ ,]%lf%*[ ,]%lf%*[ ,]%lf", &v[0], &v[1], &v[2], &v[3]) != 4)
		return -1;
	for (i = 0; i < 4; i++)
		if (!(v[i] >= -1.0 && v[i] <= 1.0))
			return -1;
	pi_quantize(v[0], v[1], v[2], v[3], w);
	return 0;
}

static int command(struct run *R, char *line, double rx_lo, double rx_hi)
{
	struct settings *s = R->s;
	char *word = line, *rest;
	char msg[256];

	while (isspace((unsigned char)*word))
		word++;
	rest = word + strcspn(word, " \t");
	if (*rest)
		*rest++ = 0;
	while (isspace((unsigned char)*rest))
		rest++;

	if (!*word)
		return 1;
	if (!strcmp(word, "q") || !strcmp(word, "quit"))
		return 0;
	if (!strcmp(word, "h") || !strcmp(word, "help") || !strcmp(word, "?")) {
		puts(HELP);
		fflush(stdout);
	} else if (!strcmp(word, "status")) {
		report_rf();
		report_core();
		summary(R);
	} else if (!strcmp(word, "s") || !strcmp(word, "level")) {
		summary(R);
	} else if (!strcmp(word, "note")) {
		say("NOTE %s", rest);
	} else if (!strcmp(word, "rx")) {
		char *end;
		long g = strtol(rest, &end, 10);
		if (end == rest || *end) {
			say("rx needs a whole number of dB");
		} else if (g < rx_lo || g > rx_hi) {
			say("RX gain must be %g to %g", rx_lo, rx_hi);
		} else {
			TRY(set_rx_gain((int)g, 0));
			say("RX gain %ld dB on both channels", g);
		}
	} else if (!strcmp(word, "tx")) {
		char *end;
		double att = strtod(rest, &end), got;
		if (!s->on) {
			say("tx is only available with --on (dry run keeps TX at maximum attenuation)");
		} else if (end == rest || *end) {
			say("tx needs a number of dB");
		} else if (check_tx_att(att, s->min_tx_att, msg, sizeof(msg))) {
			say("%s", msg);
		} else {
			TRY(tx_att_set("voltage0", att));
			TRY(tx_att_get("voltage0", &got));
			if (fabs(got - att) > 1e-6)
				return fail("TX1 attenuation reads %g", got);
			s->tx_att = att;
			say("TX1 attenuation %.2f dB", att);
		}
	} else if (!strcmp(word, "w")) {
		int16_t w[4];
		char wt[160];
		if (parse_w(rest, w)) {
			say("w needs four numbers from -1 to 1: w1re w1im w2re w2im");
		} else {
			s->mode = MODE_FIXED;
			write_weights(w, R->shift);
			memcpy(R->w, w, sizeof(w));
			w_text(w, R->shift, wt, sizeof(wt));
			say("fixed weights: %s", wt);
		}
	} else if (!strcmp(word, "pi")) {
		pi_init(&R->pi, s->load, s->alpha);
		s->mode = MODE_PI;
		say("power inversion on (load %g, alpha %g)", s->load, s->alpha);
	} else if (!strcmp(word, "load")) {
		char *end;
		double l = strtod(rest, &end);
		if (end == rest || *end || !(l >= 0)) {
			say("load needs a number >= 0 (LSB^2 per sample)");
		} else {
			s->load = l;
			R->pi.load = l;
			say("diagonal load %g LSB^2 per sample", l);
		}
	} else if (!strcmp(word, "shift")) {
		char *end;
		long v = strtol(rest, &end, 10);
		if (end == rest || *end || v < 0 || v > SHIFT_MAX) {
			say("shift needs 0..%d", SHIFT_MAX);
		} else {
			R->shift = (int)v;
			s->shift = (int)v;
			write_weights(R->w, R->shift);
			say("OUT_SHIFT %ld", v);
		}
	} else {
		say("unknown command; type help");
	}
	return 1;
}

/* ---- line input usable with poll ---- */
struct lines {
	int fd;
	char buf[512];
	size_t n;
	int eof;
};

/* Returns 1 with a line, 0 if none is complete yet. Reads from the fd only
 * if can_read (poll reported it readable), so it never blocks. */
static int line_get(struct lines *L, int can_read, char *out, size_t outn)
{
	char *nl = memchr(L->buf, '\n', L->n);
	if (!nl && can_read && !L->eof && L->n < sizeof(L->buf)) {
		ssize_t r = read(L->fd, L->buf + L->n, sizeof(L->buf) - L->n);
		if (r <= 0) {
			if (r == 0 || (errno != EINTR && errno != EAGAIN))
				L->eof = 1;
		} else {
			L->n += (size_t)r;
		}
		nl = memchr(L->buf, '\n', L->n);
	}
	if (!nl && L->n == sizeof(L->buf))
		nl = L->buf + L->n - 1;   /* overlong line: cut */
	if (!nl)
		return 0;
	size_t len = (size_t)(nl - L->buf);
	size_t c = len < outn - 1 ? len : outn - 1;
	memcpy(out, L->buf, c);
	out[c] = 0;
	memmove(L->buf, nl + 1, L->n - len - 1);
	L->n -= len + 1;
	out[strcspn(out, "\r")] = 0;
	return 1;
}

static int confirm(const struct settings *s, struct lines *L)
{
	char line[128];
	printf("About to transmit the combiner output on TX1, at TX attenuation %.2f dB\n"
	       "(minimum allowed %.2f dB):\n"
	       "  RX LO = TX LO = %lld Hz (L1 + %lld), fs %lld, bandwidth %lld, RX gain %d dB\n"
	       "Required: TX1 -> DC block -> receiver, by cable, with external attenuation plus\n"
	       "the minimum above at least 50 dB. RX1 and RX2 fed by cable through attenuators.\n"
	       "TX2 and no port connected to an antenna.\n"
	       "Type %s to confirm the setup is conducted and meets this: ",
	       s->tx_att, s->min_tx_att, L1 + s->delta, s->delta, s->fs, s->bw, s->rx_gain, CONFIRM);
	fflush(stdout);
	while (!L->eof && !stop_sig) {
		struct pollfd p = { L->fd, POLLIN, 0 };
		int r = poll(&p, 1, 500);
		if (line_get(L, r > 0 && (p.revents & (POLLIN | POLLHUP | POLLERR)), line, sizeof(line)))
			return !strcmp(line, CONFIRM);
	}
	return 0;
}

/* ---- main loop ---- */
static int loop(struct run *R, struct lines *L)
{
	struct settings *s = R->s;
	double next_mon = now() + s->monitor, t_end = s->duration > 0 ? now() + s->duration : 0;
	double rx_lo, rx_hi;
	char line[256];

	TRY(attr_range("voltage0", 0, "hardwaregain_available", &rx_lo, &rx_hi));
	R->t0 = R->last_block_t = now();
	while (!stop_sig) {
		struct pollfd p[2];
		int n = 0, li = -1, timeout_ms, r, can_read;
		double t = now();

		if (t_end && t >= t_end) {
			say("duration reached");
			return 0;
		}
		if (t >= next_mon) {
			TRY(monitor(R));
			summary(R);
			next_mon = t + s->monitor;
		}
		timeout_ms = (int)((next_mon - t) * 1000) + 1;
		if (t_end && (int)((t_end - t) * 1000) + 1 < timeout_ms)
			timeout_ms = (int)((t_end - t) * 1000) + 1;
		if (s->poll_status) {
			uint32_t st = rd(CRPA_STATUS);
			if (st & ST_DONE)
				TRY(block(R, st));
			if (timeout_ms > 1)
				timeout_ms = 0;   /* busy-poll STATUS; stdin checked without waiting */
		} else {
			p[n].fd = uio_fd;
			p[n].events = POLLIN;
			n++;
		}
		if (L) {
			li = n;
			p[n].fd = L->fd;
			p[n].events = POLLIN;
			p[n].revents = 0;
			n++;
		}
		if (s->poll_status && !L) {
			usleep(100);
			continue;
		}
		r = poll(p, (nfds_t)n, s->poll_status ? 0 : timeout_ms);
		if (r < 0) {
			if (errno == EINTR)
				continue;
			return fail("poll: %s", strerror(errno));
		}
		if (s->poll_status)
			usleep(100);
		if (!s->poll_status && (p[0].revents & POLLIN)) {
			uint32_t count;
			if (read(uio_fd, &count, sizeof(count)) != sizeof(count))
				return fail("read uio: %s", strerror(errno));
			uint32_t st = rd(CRPA_STATUS);
			if (st & ST_DONE)
				TRY(block(R, st));
			else
				TRY(uio_unmask());   /* spurious: DONE already clear */
		}
		if (L) {
			can_read = (p[li].revents & (POLLIN | POLLHUP | POLLERR)) != 0;
			while (line_get(L, can_read, line, sizeof(line))) {
				can_read = 0;
				if (line[0])
					say("> %s", line);
				r = command(R, line, rx_lo, rx_hi);
				if (r < 0)
					return -1;
				if (r == 0)
					return 0;
			}
			if (L->eof) {
				say("end of input");
				return 0;
			}
		}
	}
	say("stopped by signal %d", (int)stop_sig);
	return 0;
}

static int run_path(struct settings *s, struct lines *L)
{
	struct run R;
	char wt[160];
	int16_t w0[4];

	memset(&R, 0, sizeof(R));
	R.s = s;
	R.shift = s->shift;
	pi_init(&R.pi, s->load, s->alpha);
	if (s->mode == MODE_FIXED)
		memcpy(w0, s->w, sizeof(w0));
	else
		pi_quantize(1.0, 0.0, 0.0, 0.0, w0);   /* unity until the first PI update */
	memcpy(R.w, w0, sizeof(w0));

	TRY(configure(s, s->on));
	TRY(path_on(s, w0));
	if (s->on) {
		/* the last two writes: nothing is emitted until the LO comes up */
		TRY(tx_att_set("voltage0", s->tx_att));
		TRY(attr_set("altvoltage1", 1, "powerdown", "0"));
		say("ON: crpa_core output on TX1");
	} else {
		say("DRY RUN: path set with TX muted; TX LO stays parked and powered down");
	}
	R.blocks = 0;
	R.t0 = R.last_block_t = now();
	TRY(monitor(&R));
	report_rf();
	report_core();
	w_text(w0, s->shift, wt, sizeof(wt));
	say("mode %s, start %s, INT_LEN %u (%.3f ms), load %g, alpha %g",
	    s->mode == MODE_PI ? "pi" : "fixed", wt, s->int_len, 1e3 * s->int_len / (double)s->fs,
	    s->load, s->alpha);
	if (L) {
		puts(HELP);
		fflush(stdout);
	}
	TRY(loop(&R, L));
	summary(&R);
	return 0;
}

/* ---- main ---- */
static void usage(void)
{
	puts("Usage: crpa_ctl status | off | run [options]\n"
	     "run options:\n"
	     "  --on                 transmit, after a typed confirmation (needs a terminal)\n"
	     "  --tx-att DB          TX1 attenuation; needed with --on\n"
	     "  --min-tx-att DB      needed with --on: 50 minus the external TX1 attenuation\n"
	     "  --delta HZ           LO = L1 + delta (default 3000000)\n"
	     "  --fs HZ              sample rate (default 10000000)\n"
	     "  --bw HZ              RF bandwidth (default 9000000)\n"
	     "  --rx-gain DB         manual, both channels (default 60)\n"
	     "  --mode fixed|pi      weights (default fixed)\n"
	     "  --w A,B,C,D          fixed weights w1 = A + jB, w2 = C + jD (default 1,0,0,0)\n"
	     "  --load L             PI diagonal load, LSB^2 per sample (default 0)\n"
	     "  --alpha A            PI smoothing of R, 0 <= A < 1 (default 0)\n"
	     "  --int-len N          samples per block (default 10000)\n"
	     "  --shift S            OUT_SHIFT 0..15 (default 0)\n"
	     "  --cap-sel            capture mux: ch0/1 = y, ch2/3 = x1\n"
	     "  --out PREFIX         PREFIX.csv and PREFIX.log (default /tmp/crpa)\n"
	     "  --csv-every N        one CSV row per N blocks, 0 = none (default 1)\n"
	     "  --duration S         stop after S seconds (default: until quit or signal)\n"
	     "  --monitor S          seconds between path checks and summaries (default 2)\n"
	     "  --poll-status        poll STATUS.DONE instead of waiting for the irq\n"
	     "  --rt PRIO            SCHED_FIFO priority, 0 = normal scheduling (default 40;\n"
	     "                       below the irq threads at 50). Without it a 1 Hz system\n"
	     "                       task stalls the loop for 5-8 ms and drops blocks");
}

int main(int argc, char **argv)
{
	struct settings s = {
		.delta = 3000000, .fs = 10000000, .bw = 9000000, .rx_gain = 60,
		.mode = MODE_FIXED, .w = { W_UNITY, 0, 0, 0 }, .shift = 0, .load = 0, .alpha = 0,
		.int_len = 10000, .out = "/tmp/crpa", .csv_every = 1, .monitor = 2.0, .rt = 40,
	};
	static const struct option opts[] = {
		{ "on", no_argument, 0, 'o' }, { "tx-att", required_argument, 0, 't' },
		{ "min-tx-att", required_argument, 0, 'm' }, { "delta", required_argument, 0, 'd' },
		{ "fs", required_argument, 0, 'f' }, { "bw", required_argument, 0, 'b' },
		{ "rx-gain", required_argument, 0, 'g' }, { "mode", required_argument, 0, 'M' },
		{ "w", required_argument, 0, 'w' }, { "load", required_argument, 0, 'l' },
		{ "alpha", required_argument, 0, 'a' }, { "int-len", required_argument, 0, 'n' },
		{ "shift", required_argument, 0, 's' }, { "cap-sel", no_argument, 0, 'c' },
		{ "out", required_argument, 0, 'O' }, { "csv-every", required_argument, 0, 'e' },
		{ "duration", required_argument, 0, 'D' }, { "monitor", required_argument, 0, 'p' },
		{ "poll-status", no_argument, 0, 'P' }, { "rt", required_argument, 0, 'R' },
		{ "help", no_argument, 0, 'h' },
		{ 0, 0, 0, 0 },
	};
	const char *cmd;
	int c, rc = 0, failed;
	struct lines Lb = { .fd = 0 }, *L = NULL;
	char path[256];

	setvbuf(stdout, NULL, _IOLBF, 0);
	signal(SIGPIPE, SIG_IGN);
	if (argc < 2 || !strcmp(argv[1], "-h") || !strcmp(argv[1], "--help")) {
		usage();
		return argc < 2 ? 2 : 0;
	}
	cmd = argv[1];
	optind = 2;
	while ((c = getopt_long(argc, argv, "", opts, NULL)) != -1) {
		switch (c) {
		case 'o': s.on = 1; break;
		case 't': s.tx_att = atof(optarg); s.have_tx_att = 1; break;
		case 'm': s.min_tx_att = atof(optarg); s.have_min_tx_att = 1; break;
		case 'd': s.delta = llround(atof(optarg)); break;
		case 'f': s.fs = llround(atof(optarg)); break;
		case 'b': s.bw = llround(atof(optarg)); break;
		case 'g': s.rx_gain = atoi(optarg); break;
		case 'M':
			if (!strcmp(optarg, "pi"))
				s.mode = MODE_PI;
			else if (!strcmp(optarg, "fixed"))
				s.mode = MODE_FIXED;
			else {
				fprintf(stderr, "--mode is fixed or pi\n");
				return 2;
			}
			break;
		case 'w':
			if (parse_w(optarg, s.w)) {
				fprintf(stderr, "--w needs four numbers from -1 to 1\n");
				return 2;
			}
			break;
		case 'l': s.load = atof(optarg); break;
		case 'a': s.alpha = atof(optarg); break;
		case 'n': s.int_len = (uint32_t)strtoul(optarg, NULL, 0); break;
		case 's': s.shift = atoi(optarg); break;
		case 'c': s.cap_sel = 1; break;
		case 'O': s.out = optarg; break;
		case 'e': s.csv_every = atoi(optarg); break;
		case 'D': s.duration = atof(optarg); break;
		case 'p': s.monitor = atof(optarg); break;
		case 'P': s.poll_status = 1; break;
		case 'R': s.rt = atoi(optarg); break;
		case 'h': usage(); return 0;
		default: usage(); return 2;
		}
	}
	if (optind != argc) {
		fprintf(stderr, "unexpected argument: %s\n", argv[optind]);
		return 2;
	}
	if (strcmp(cmd, "status") && strcmp(cmd, "off") && strcmp(cmd, "run")) {
		usage();
		return 2;
	}
	if (strcmp(cmd, "run") && argc > 2) {
		fprintf(stderr, "%s takes no options\n", cmd);
		return 2;
	}
	if (s.on && !s.have_tx_att) {
		fprintf(stderr, "--on needs an explicit --tx-att\n");
		return 2;
	}
	if (s.on && !s.have_min_tx_att) {
		fprintf(stderr, "--on needs an explicit --min-tx-att: 50 minus the external TX1 attenuation\n");
		return 2;
	}
	if (!s.on && (s.have_tx_att || s.have_min_tx_att)) {
		fprintf(stderr, "--tx-att and --min-tx-att are only used with --on\n");
		return 2;
	}
	if (s.rt < 0 || s.rt > 99) {
		fprintf(stderr, "--rt is 0 (off) or 1-99\n");
		return 2;
	}
	if (!(s.monitor > 0)) {
		fprintf(stderr, "--monitor must be > 0\n");
		return 2;
	}

	set_signals(1);

	if (iio_open() < 0) {
		say("ERROR: %s", errbuf);
		return 1;
	}
	if (uio_open() < 0) {
		say("ERROR: %s", errbuf);
		if (!strcmp(cmd, "off"))
			return finish(safe_state(), 1);   /* still mute the AD9363 side */
		return 1;
	}

	if (!strcmp(cmd, "off")) {
		set_signals(0);
		return finish(safe_state(), 0);
	}
	if (!strcmp(cmd, "status")) {
		report_rf();
		report_core();
		return 0;
	}

	/* run */
	check_settings(&s);
	if (!refused)
		precheck(&s);
	if (refused)
		return 1;

	if (isatty(0))
		L = &Lb;
	if (s.on) {
		if (!L) {
			say("REFUSED: --on needs an interactive terminal for the confirmation (ssh -t)");
			return 1;
		}
		if (!confirm(&s, L)) {
			say("REFUSED: setup not confirmed; nothing was changed");
			return stop_sig ? 128 + stop_sig : 1;
		}
	}
	if (stop_sig)
		return 128 + stop_sig;

	snprintf(path, sizeof(path), "%s.log", s.out);
	log_fp = fopen(path, "w");
	if (!log_fp) {
		say("ERROR: cannot open %s: %s", path, strerror(errno));
		return 1;
	}
	if (s.csv_every) {
		snprintf(path, sizeof(path), "%s.csv", s.out);
		csvf = fopen(path, "w");
		if (!csvf) {
			say("ERROR: cannot open %s: %s", path, strerror(errno));
			return 1;
		}
		fprintf(csvf, "blk,seq,t_s,r11,r22,r21re,r21im,sat,peak1,peak2,missed,status,"
			      "w1i,w1q,w2i,w2q,shift,p1_dbfs,p2_dbfs,py_dbfs,mode,flag\n");
	}
	say("settings: delta %lld fs %lld bw %lld rx_gain %d on %d tx_att %.2f min_tx_att %.2f "
	    "mode %s load %g alpha %g int_len %u shift %d cap_sel %d rt %d%s",
	    s.delta, s.fs, s.bw, s.rx_gain, s.on, s.tx_att, s.min_tx_att,
	    s.mode == MODE_PI ? "pi" : "fixed", s.load, s.alpha, s.int_len, s.shift, s.cap_sel,
	    s.rt, s.on ? "; confirmed conducted setup" : "");

	if (s.rt) {
		/* The Pluto has one CPU; another task holding it for a few ms drops blocks. */
		struct sched_param sp = { .sched_priority = s.rt };
		if (mlockall(MCL_CURRENT | MCL_FUTURE))
			say("WARNING: mlockall: %s", strerror(errno));
		if (sched_setscheduler(0, SCHED_FIFO, &sp)) {
			say("ERROR: SCHED_FIFO %d: %s", s.rt, strerror(errno));
			return 1;
		}
		say("scheduling: SCHED_FIFO priority %d, memory locked", s.rt);
	}

	failed = safe_state();
	if (failed) {
		say("ERROR: could not reach the safe state before starting");
		rc = 1;
	} else if (run_path(&s, L) < 0) {
		say("ERROR: %s", errbuf);
		rc = 1;
	}
	if (stop_sig && !rc)
		rc = 128 + stop_sig;
	set_signals(0);
	failed = safe_state();
	rc = finish(failed, rc);
	if (csvf)
		fclose(csvf);
	if (log_fp)
		fclose(log_fp);
	return rc;
}
