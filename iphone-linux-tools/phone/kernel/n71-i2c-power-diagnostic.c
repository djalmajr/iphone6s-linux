// SPDX-License-Identifier: GPL-2.0-only
/* Explicit genpd cycle only: no controller, adapter, pins or charger access. */
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/string.h>
#include "n71-i2c-genpd.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Qualify disabled N71 I2C1 and protected PMGR providers; no activation");
static DEFINE_MUTEX(diagnostic_lock);
static struct n71_i2c_genpd diagnostic_backend;
static struct n71_i2c_power_state diagnostic_state;
static struct n71_i2c_power_io diagnostic_io;
static struct device_node *diagnostic_pmgr, *diagnostic_node;
static bool diagnostic_ready, diagnostic_retained;

static bool n71_diagnostic_clean(void)
{
	return !diagnostic_state.active && !diagnostic_state.attached &&
		!diagnostic_state.cleanup_pending && !diagnostic_state.usage_held &&
		!diagnostic_backend.domain;
}

static int n71_diagnostic_action(const char *text, const struct kernel_param *parameter)
{
	bool cycle = sysfs_streq(text, "cycle");
	int error;

	(void)parameter;
	if (!cycle && !sysfs_streq(text, "cleanup"))
		return -EINVAL;
	if (!try_module_get(THIS_MODULE))
		return -ENODEV;
	mutex_lock(&diagnostic_lock);
	if (!diagnostic_ready) {
		error = -ENODEV;
		goto unlock;
	}
	if (cycle) {
		if (!n71_diagnostic_clean() || diagnostic_retained) {
			error = -EBUSY;
			goto unlock;
		}
		/* Keep all caller objects and code alive until verified detach. */
		__module_get(THIS_MODULE);
		diagnostic_retained = true;
		error = n71_i2c_power_acquire(&diagnostic_io, &diagnostic_state);
		if (!error)
			error = n71_i2c_power_release(&diagnostic_io, &diagnostic_state);
	} else {
		error = n71_i2c_power_release(&diagnostic_io, &diagnostic_state);
	}
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
MODULE_PARM_DESC(action, "cycle performs acquire/release; cleanup retries a retained release");
module_param_cb(status, &status_ops, NULL, 0400);
MODULE_PARM_DESC(status, "Inspect pending cleanup and retained module before unload; never force unload");

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
	pr_info("N71_I2C_POWER_UNLOADED no-controller-or-charger-access=1\n");
}
module_init(n71_i2c_power_diagnostic_init);
module_exit(n71_i2c_power_diagnostic_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 explicit I2C1 genpd cycle with retained cleanup ownership");
