// SPDX-License-Identifier: GPL-2.0-only
/* Explicit genpd/configuration and fixed HDQ read; no charger limit writes. */
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/string.h>
#include "n71-i2c-genpd.h"
#include "n71-i2c-controller-observe.h"
#include "n71-i2c-configuration.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Qualify disabled N71 I2C1 and protected PMGR providers; no activation");
static DEFINE_MUTEX(diagnostic_lock);
static struct n71_i2c_genpd diagnostic_backend;
static struct n71_i2c_power_state diagnostic_state;
static struct n71_i2c_power_io diagnostic_io;
static struct n71_i2c_controller diagnostic_controller;
static struct n71_i2c_pin_owner diagnostic_pins;
static struct n71_i2c_hdq_read_state diagnostic_read;
static struct device_node *diagnostic_pmgr, *diagnostic_node;
static bool diagnostic_ready, diagnostic_retained;

static bool n71_diagnostic_clean(void)
{
	return !diagnostic_state.active && !diagnostic_state.attached &&
		!diagnostic_state.cleanup_pending && !diagnostic_state.usage_held &&
		!diagnostic_backend.domain && n71_i2c_controller_clean(&diagnostic_controller) &&
		n71_i2c_pin_owner_clean(&diagnostic_pins) && !diagnostic_read.cleanup_pending &&
		!diagnostic_read.controller;
}

static struct n71_i2c_configuration_request n71_diagnostic_configuration_request(void)
{
	return (struct n71_i2c_configuration_request) {
		.consumer = diagnostic_backend.consumer, .controller = &diagnostic_controller,
		.pins = &diagnostic_pins, .power = &diagnostic_state,
		.power_io = &diagnostic_io, .read = &diagnostic_read,
	};
}

static int n71_diagnostic_configuration_cleanup(void)
{
	struct n71_i2c_configuration_request request = n71_diagnostic_configuration_request();

	return n71_i2c_configuration_release(&request);
}

static int n71_diagnostic_configure(bool read_control)
{
	struct n71_i2c_configuration_request request = n71_diagnostic_configuration_request();
	struct n71_i2c_configuration_result result;

	n71_i2c_configuration_run(&request, read_control, &result);
	pr_info("N71_I2C_CONFIGURATION_STAGE stage=%u read=%u error=%d cleanup_error=%d\n",
		result.stage, read_control, result.error, result.cleanup_error);
	if (!read_control)
		pr_info("N71_I2C_CONFIGURE error=%d cleanup_error=%d pins_pending=%u controller_pending=%u last_saved_ctl=%08x last_saved_smsta=%08x charger_io=0\n",
			result.error, result.cleanup_error, diagnostic_pins.cleanup_pending,
			diagnostic_controller.restore_pending,
			diagnostic_controller.saved[N71_I2C_CTL],
			diagnostic_controller.saved[N71_I2C_SMSTA]);
	if (read_control) {
		pr_info("N71_I2C_HDQ_TRACE stage=%u sampled=%u status=%08x cleanup_stage=%u cleanup_sampled=%u cleanup_status=%08x\n",
			result.trace.stage, result.trace.sampled, result.trace.status,
			result.trace.cleanup_stage, result.trace.cleanup_sampled,
			result.trace.cleanup_status);
		pr_info("N71_I2C_HDQ_CONTROL error=%d cleanup_error=%d valid=%u value=%02x transfer_pending=%u transfer_error=%d charger_value_writes=0 gauge_verified=0\n",
			result.error, result.cleanup_error, result.value_valid, result.value,
			diagnostic_read.cleanup_pending, diagnostic_read.cleanup_error);
	}
	return result.error ? result.error : result.cleanup_error;
}

static int n71_diagnostic_action(const char *text, const struct kernel_param *parameter)
{
	bool configure = sysfs_streq(text, "configure");
	bool cycle = sysfs_streq(text, "cycle");
	bool inspect = sysfs_streq(text, "inspect");
	bool read_control = sysfs_streq(text, "read-hdq-control");
	int error;

	(void)parameter;
	if (!cycle && !inspect && !configure && !read_control && !sysfs_streq(text, "cleanup"))
		return -EINVAL;
	if (!try_module_get(THIS_MODULE))
		return -ENODEV;
	mutex_lock(&diagnostic_lock);
	if (!diagnostic_ready) {
		error = -ENODEV;
		goto unlock;
	}
	if (cycle || inspect || configure || read_control) {
		if (!n71_diagnostic_clean() || diagnostic_retained) {
			error = -EBUSY;
			goto unlock;
		}
		/* Keep all caller objects and code alive until verified detach. */
		__module_get(THIS_MODULE);
		diagnostic_retained = true;
		if (configure || read_control) {
			error = n71_diagnostic_configure(read_control);
			goto finished;
		}
		error = n71_i2c_power_acquire(&diagnostic_io, &diagnostic_state);
		if (!error) {
			int cleanup_error;

			if (inspect) {
				struct n71_i2c_controller_observation observation;

				error = n71_i2c_controller_observe(diagnostic_backend.consumer,
								   &diagnostic_state, &observation);
				pr_info("N71_I2C_CONTROLLER complete=%u stable=%u idle_status=%u error=%d rev=%08x,%08x smsta=%08x,%08x xfsta=%08x,%08x controller_writes=0 charger_io=0\n",
					observation.complete, observation.stable,
					observation.idle_status, error,
					observation.words[0][N71_I2C_OBSERVE_REV],
					observation.words[1][N71_I2C_OBSERVE_REV],
					observation.words[0][N71_I2C_OBSERVE_SMSTA],
					observation.words[1][N71_I2C_OBSERVE_SMSTA],
					observation.words[0][N71_I2C_OBSERVE_XFSTA],
					observation.words[1][N71_I2C_OBSERVE_XFSTA]);
			}
			cleanup_error = n71_i2c_power_release(&diagnostic_io, &diagnostic_state);
			if (!error)
				error = cleanup_error;
		}
	} else if (!n71_i2c_controller_clean(&diagnostic_controller) ||
		   !n71_i2c_pin_owner_clean(&diagnostic_pins) || diagnostic_read.cleanup_pending ||
		   diagnostic_read.controller) {
		error = n71_diagnostic_configuration_cleanup();
	} else {
		error = n71_i2c_power_release(&diagnostic_io, &diagnostic_state);
	}
finished:
	if (diagnostic_retained && n71_diagnostic_clean()) {
		diagnostic_retained = false;
		module_put(THIS_MODULE);
	}
	pr_info("N71_I2C_POWER_ACTION cycle=%u error=%d active=%u attached=%u cleanup_pending=%u usage_held=%u retained=%u cleanup_error=%d\n",
		cycle, error, diagnostic_state.active, diagnostic_state.attached,
		diagnostic_state.cleanup_pending, diagnostic_state.usage_held,
		diagnostic_retained, diagnostic_state.cleanup_error);
unlock:
	mutex_unlock(&diagnostic_lock);
	module_put(THIS_MODULE);
	return error;
}

static int n71_diagnostic_status(char *buffer, const struct kernel_param *parameter)
{
	int length;

	(void)parameter;
	mutex_lock(&diagnostic_lock);
	length = scnprintf(buffer, PAGE_SIZE,
			   "ready=%u active=%u attached=%u cleanup_pending=%u usage_held=%u module_retained=%u cleanup_error=%d\n",
			   diagnostic_ready, diagnostic_state.active, diagnostic_state.attached,
			   diagnostic_state.cleanup_pending, diagnostic_state.usage_held,
			   diagnostic_retained, diagnostic_state.cleanup_error);
	mutex_unlock(&diagnostic_lock);
	return length;
}

static const struct kernel_param_ops action_ops = {.set = n71_diagnostic_action};
static const struct kernel_param_ops status_ops = {.get = n71_diagnostic_status};
module_param_cb(action, &action_ops, NULL, 0200);
MODULE_PARM_DESC(action, "cycle/inspect/configure; read-hdq-control reads only SN2400 75:1d; cleanup retries retained release");
module_param_cb(status, &status_ops, NULL, 0400);
MODULE_PARM_DESC(status, "Inspect pending cleanup and retained module before unload; never force unload");

static int n71_diagnostic_configuration_status(char *buffer, const struct kernel_param *parameter)
{
	int length;

	(void)parameter;
	mutex_lock(&diagnostic_lock);
	length = scnprintf(buffer, PAGE_SIZE,
			   "pins_pending=%u pins_selected=%u pins_error=%d controller_pending=%u controller_error=%d controller_claimed=%u transfer_pending=%u transfer_error=%d\n",
			   diagnostic_pins.cleanup_pending, diagnostic_pins.selected,
			   diagnostic_pins.cleanup_error, diagnostic_controller.restore_pending,
			   diagnostic_controller.cleanup_error, diagnostic_controller.claimed,
			   diagnostic_read.cleanup_pending, diagnostic_read.cleanup_error);
	mutex_unlock(&diagnostic_lock);
	return length;
}

static const struct kernel_param_ops configuration_status_ops = {
	.get = n71_diagnostic_configuration_status,
};
module_param_cb(configuration_status, &configuration_status_ops, NULL, 0400);
MODULE_PARM_DESC(configuration_status, "Read pin/controller cleanup independently of legacy status");

static void n71_diagnostic_drop_refs(void)
{
	unsigned int index;

	if (diagnostic_backend.consumer) {
		diagnostic_backend.consumer->of_node = NULL;
		root_device_unregister(diagnostic_backend.consumer);
		diagnostic_backend.consumer = NULL;
	}
	for (index = 3; index > 0; index--) {
		of_node_put(diagnostic_backend.references[index - 1].node);
		diagnostic_backend.references[index - 1].node = NULL;
		diagnostic_backend.references[index - 1].pmgr = NULL;
	}
	of_node_put(diagnostic_node);
	diagnostic_node = NULL;
	of_node_put(diagnostic_pmgr);
	diagnostic_pmgr = NULL;
}

static int __init n71_i2c_power_diagnostic_init(void)
{
	struct n71_pmgr_access access[3] = {0};
	struct device *consumer;
	unsigned int index;
	int error = -ENODEV;

	if (!run)
		return -ENODEV;
	mutex_lock(&diagnostic_lock);
	diagnostic_pmgr = of_find_node_by_path(N71_PMGR_PATH);
	if (!diagnostic_pmgr)
		goto failed;
	error = n71_pmgr_root_validate(diagnostic_pmgr);
	if (error)
		goto failed;
	for (index = 0; index < 3; index++) {
		diagnostic_backend.references[index] = (struct n71_pmgr_reference) {
			.index = index, .pmgr = diagnostic_pmgr,
			.node = of_find_node_by_path(n71_domains[index].path),
		};
		if (!diagnostic_backend.references[index].node) {
			error = -ENODEV;
			goto failed;
		}
	}
	diagnostic_node = of_find_node_by_path("/soc/i2c@20a111000");
	if (!diagnostic_node) {
		error = -ENODEV;
		goto failed;
	}
	consumer = root_device_register("n71-i2c1-power");
	if (IS_ERR(consumer)) {
		error = PTR_ERR(consumer);
		goto failed;
	}
	diagnostic_backend.consumer = consumer;
	consumer->of_node = diagnostic_node; /* Borrow our retained OF reference. */
	error = n71_genpd_lock(&diagnostic_backend, access);
	if (!error)
		error = n71_genpd_consumer_validate(&diagnostic_backend);
	if (!error)
		error = n71_genpd_words(access, false);
	n71_genpd_unlock(access);
	if (error)
		goto failed;
	diagnostic_io = n71_i2c_genpd_io(&diagnostic_backend);
	diagnostic_ready = true;
	pr_info("N71_I2C_POWER_READY controller=disabled leaf=quiescent action=explicit charger_io=0\n");
	mutex_unlock(&diagnostic_lock);
	return 0;
failed:
	n71_diagnostic_drop_refs();
	mutex_unlock(&diagnostic_lock);
	return error;
}

static void __exit n71_i2c_power_diagnostic_exit(void)
{
	/* A retained reference prevents normal unload while cleanup is pending. */
	mutex_lock(&diagnostic_lock);
	diagnostic_ready = false;
	n71_diagnostic_drop_refs();
	mutex_unlock(&diagnostic_lock);
	pr_info("N71_I2C_POWER_UNLOADED controller_clean=1 pins_clean=1 charger_io=0\n");
}
module_init(n71_i2c_power_diagnostic_init);
module_exit(n71_i2c_power_diagnostic_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 explicit I2C1 genpd/controller cycles with retained cleanup ownership");
