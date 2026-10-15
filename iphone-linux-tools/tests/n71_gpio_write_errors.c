/* SPDX-License-Identifier: GPL-2.0-only */
/* Exercise actual provider callbacks with failed and partial regmap writes. */
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define BIT(n) (1U << (n))
#define GENMASK(high, low) ((UINT32_MAX >> (31 - (high))) & (UINT32_MAX << (low)))
#define FIELD_PREP(mask, value) (((value) << __builtin_ctz(mask)) & (mask))
#define REG_GPIO(x) (4 * (x))
#define REG_GPIOx_DATA BIT(0)
#define REG_GPIOx_MODE GENMASK(3, 1)
#define REG_GPIOx_OUT 1
#define REG_GPIOx_IN_IRQ_HI 2
#define REG_GPIOx_IN_IRQ_LO 3
#define REG_GPIOx_IN_IRQ_UP 4
#define REG_GPIOx_IN_IRQ_DN 5
#define REG_GPIOx_IN_IRQ_ANY 6
#define REG_GPIOx_IN_IRQ_OFF 7
#define REG_GPIOx_PERIPH GENMASK(6, 5)
#define REG_GPIOx_INPUT_ENABLE BIT(9)
#define IRQ_TYPE_EDGE_RISING 1U
#define IRQ_TYPE_EDGE_FALLING 2U
#define IRQ_TYPE_EDGE_BOTH 3U
#define IRQ_TYPE_LEVEL_HIGH 4U
#define IRQ_TYPE_LEVEL_LOW 8U
#define IRQ_TYPE_SENSE_MASK 15U
#define IRQ_TYPE_LEVEL_MASK 12U

typedef uint32_t u32;
struct regmap { uint32_t words[512]; };
struct apple_gpio_pinctrl { struct regmap *map; };
struct gpio_chip { struct apple_gpio_pinctrl *private; };
struct pinctrl_dev { struct apple_gpio_pinctrl *private; };
struct irq_data { struct gpio_chip *private; unsigned int hwirq; int handler; };
static unsigned int write_count, last_offset, last_mask, last_value;
static int write_error, partial_write;

static int regmap_update_bits(struct regmap *map, unsigned int offset,
			      unsigned int mask, unsigned int value)
{
	assert(offset % 4 == 0 && offset / 4 < 512);
	write_count++;
	last_offset = offset;
	last_mask = mask;
	last_value = value;
	if (!write_error || partial_write)
		map->words[offset / 4] = (map->words[offset / 4] & ~mask) | (value & mask);
	return write_error;
}

static struct apple_gpio_pinctrl *pinctrl_dev_get_drvdata(struct pinctrl_dev *dev)
{
	return dev->private;
}

static struct apple_gpio_pinctrl *gpiochip_get_data(struct gpio_chip *chip)
{
	return chip->private;
}

static struct gpio_chip *irq_data_get_irq_chip_data(struct irq_data *data)
{
	return data->private;
}

static void handle_level_irq(void) { }
static void handle_edge_irq(void) { }

static void irq_set_handler_locked(struct irq_data *data, void (*handler)(void))
{
	assert(handler == handle_level_irq || handler == handle_edge_irq);
	data->handler = handler == handle_level_irq ? 1 : 2;
}

#include "n71-gpio-provider-functions.h"

int main(void)
{
	struct regmap map;
	struct apple_gpio_pinctrl provider = {&map};
	struct pinctrl_dev pins = {&provider};
	struct gpio_chip chip = {&provider};
	struct irq_data irq = {&chip, 0, 17};
	const unsigned int groups[] = {2, 10, 114, 115, 511};
	const int errors[] = {0, -EIO, -ENOMEM, -ETIMEDOUT};
	const unsigned int types[] = {1, 2, 3, 4, 8};
	const unsigned int modes[] = {4, 5, 6, 2, 3};
	unsigned int cases = 0, gi, ei, operation, index, value;

	/* Kills swallowed errors in all int callbacks, including partial effects. */
	for (gi = 0; gi < sizeof(groups) / sizeof(groups[0]); gi++)
	for (ei = 0; ei < sizeof(errors) / sizeof(errors[0]); ei++)
	for (partial_write = 0; partial_write <= 1; partial_write++)
	for (operation = 0; operation < 5; operation++)
	for (value = 0; value < 4; value++) {
		unsigned int group = groups[gi], mask, requested;
		int result;

		for (index = 0; index < 512; index++) map.words[index] = 0xa55a5aa5U;
		write_error = errors[ei];
		write_count = 0;
		if (operation == 0) {
			mask = 0x260; requested = (value << 5) | 0x200;
			result = apple_gpio_pinmux_set(&pins, value, group);
		} else if (operation == 1) {
			mask = 1; requested = value ? 1 : 0;
			result = apple_gpio_set(&chip, group, (int)value);
		} else if (operation == 2) {
			mask = 0x26f; requested = 0x20e;
			result = apple_gpio_direction_input(&chip, group);
		} else if (operation == 3) {
			mask = 0x6f; requested = value ? 3 : 2;
			result = apple_gpio_direction_output(&chip, group, (int)value);
		} else {
			mask = 0xe; requested = modes[value] << 1;
			irq.hwirq = group; irq.handler = 17;
			result = apple_gpio_irq_set_type(&irq, types[value]);
			assert(irq.handler == (write_error ? 17 : (types[value] & 12U ? 1 : 2)));
		}
		assert(result == write_error && write_count == 1);
		/* Kills wrong scope/mask/value and changes to other pin registers. */
		assert(last_offset == group * 4 && last_mask == mask && last_value == requested);
		for (index = 0; index < 512; index++) {
			uint32_t expected = 0xa55a5aa5U;
			if (index == group && (!write_error || partial_write))
				expected = (expected & ~mask) | (requested & mask);
			assert(map.words[index] == expected);
		}
		cases++;
	}
	write_error = 0; partial_write = 0;
	for (index = 0; index < 16; index++) {
		int supported = index == 1 || index == 2 || index == 3 || index == 4 || index == 8;
		write_count = 0; irq.handler = 17;
		if (supported) {
			assert(apple_gpio_irq_set_type(&irq, index) == 0 && write_count == 1);
			assert(irq.handler == (index & 12U ? 1 : 2));
		} else {
			assert(apple_gpio_irq_set_type(&irq, index) == -EINVAL);
			assert(write_count == 0 && irq.handler == 17);
		}
		cases++;
	}
	printf("N71_GPIO_WRITE_ERRORS_OK cases=%u\n", cases);
	return 0;
}
