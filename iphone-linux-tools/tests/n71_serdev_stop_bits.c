/* SPDX-License-Identifier: GPL-2.0-only */
/* Compile the actual patch additions against a synthetic TTY backend. */
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#define CSTOPB 0x40U

struct ktermios {
	unsigned int c_cflag, c_iflag, c_oflag, c_lflag;
	unsigned char c_cc[19];
	unsigned int c_ispeed, c_ospeed;
};
struct tty_struct { struct ktermios termios; };
struct serport { struct tty_struct *tty; };
struct serdev_controller;
struct serdev_controller_ops {
	int (*set_stop_bits)(struct serdev_controller *, unsigned int);
};
struct serdev_controller {
	const struct serdev_controller_ops *ops;
	struct serport *private;
};
struct serdev_device { struct serdev_controller *ctrl; };
static int backend_error, backend_reject;

static struct serport *serdev_controller_get_drvdata(struct serdev_controller *ctrl)
{
	return ctrl->private;
}

static int termios_equal(const struct ktermios *left, const struct ktermios *right)
{
	return left->c_cflag == right->c_cflag && left->c_iflag == right->c_iflag &&
		left->c_oflag == right->c_oflag && left->c_lflag == right->c_lflag &&
		left->c_ispeed == right->c_ispeed && left->c_ospeed == right->c_ospeed &&
		memcmp(left->c_cc, right->c_cc, sizeof(left->c_cc)) == 0;
}

static int tty_set_termios(struct tty_struct *tty, struct ktermios *new_termios)
{
	if (backend_error)
		return backend_error;
	tty->termios = *new_termios;
	if (backend_reject)
		tty->termios.c_cflag ^= CSTOPB;
	return 0;
}

#include "n71-serdev-added-functions.h"

int main(void)
{
	struct tty_struct tty = {0};
	struct serport port = {&tty};
	const struct serdev_controller_ops unsupported = {NULL};
	struct serdev_controller ctrl = {&n71_test_ctrl_ops, &port};
	struct serdev_device device = {&ctrl};
	const unsigned int invalid[] = {0, 3, UINT_MAX};
	unsigned int bits, value, index;
	struct ktermios old, expected;

	/* Kills wrong stop mask, reversed 1/2 and clobbered unrelated settings. */
	memset(&tty.termios, 0xa5, sizeof(tty.termios));
	for (bits = 1; bits <= 2; bits++) {
		for (value = 0; value < 65536; value++) {
			tty.termios.c_cflag = 0xdead0000U | value;
			old = tty.termios;
			expected = old;
			expected.c_cflag = (old.c_cflag & ~0x40U) | (bits == 2 ? 0x40U : 0);
			assert(serdev_device_set_stop_bits(&device, bits) == 0);
			assert(termios_equal(&tty.termios, &expected));
		}
	}
	old = tty.termios;
	/* Kills accepting invalid bit counts or backend calls before validation. */
	for (index = 0; index < sizeof(invalid) / sizeof(invalid[0]); index++) {
		assert(serdev_device_set_stop_bits(&device, invalid[index]) == -EINVAL);
		assert(ttyport_set_stop_bits(&ctrl, invalid[index]) == -EINVAL);
		assert(termios_equal(&old, &tty.termios));
	}
	device.ctrl = NULL;
	assert(serdev_device_set_stop_bits(&device, 2) == -EOPNOTSUPP);
	device.ctrl = &ctrl;
	ctrl.ops = NULL;
	assert(serdev_device_set_stop_bits(&device, 2) == -EOPNOTSUPP);
	ctrl.ops = &unsupported;
	assert(serdev_device_set_stop_bits(&device, 2) == -EOPNOTSUPP);
	ctrl.ops = &n71_test_ctrl_ops;
	port.tty = NULL;
	assert(serdev_device_set_stop_bits(&device, 2) == -ENODEV);
	port.tty = &tty;
	/* Kills swallowed callback/TTY errors and missing accepted-state readback. */
	backend_error = -EIO;
	assert(serdev_device_set_stop_bits(&device, 2) == -EIO);
	assert(termios_equal(&old, &tty.termios));
	backend_error = -ETIMEDOUT;
	assert(serdev_device_set_stop_bits(&device, 1) == -ETIMEDOUT);
	backend_error = 0;
	backend_reject = 1;
	assert(serdev_device_set_stop_bits(&device, 2) == -EINVAL);
	assert(serdev_device_set_stop_bits(&device, 1) == -EINVAL);
	backend_reject = 0;
	assert(serdev_device_set_stop_bits(&device, 2) == 0);
	assert((tty.termios.c_cflag & 0x40U) == 0x40U);
	puts("N71_SERDEV_STOP_BITS_CONTRACT_OK");
	return 0;
}
