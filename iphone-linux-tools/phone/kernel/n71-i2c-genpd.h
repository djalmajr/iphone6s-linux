/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller owns the root consumer/OF references, serializes calls and retains pending objects. */
#ifndef N71_I2C_GENPD_H
#define N71_I2C_GENPD_H
#include <linux/i2c.h>
#include <linux/pm_domain.h>
#include <linux/pm_runtime.h>
#include "n71-i2c-power-lifecycle.h"
#include "n71-pmgr-access.h"

struct n71_i2c_genpd {
	struct device *consumer;
	struct device *domain;
	struct n71_pmgr_reference references[3];
	bool detach_attempted;
};

static inline void n71_genpd_unlock(struct n71_pmgr_access access[3])
{
	unsigned int index;

	for (index = 3; index > 0; index--)
		n71_pmgr_access_unlock(&access[index - 1]);
}

static inline int n71_genpd_lock(struct n71_i2c_genpd *backend,
		struct n71_pmgr_access access[3])
{
	unsigned int index;
	int error;

	if (!backend || !backend->consumer)
		return -EINVAL;
	for (index = 0; index < 3; index++) {
		if (backend->references[index].index != index ||
		    backend->references[index].pmgr != backend->references[0].pmgr) {
			error = -ENODEV;
			goto unlock;
		}
		error = n71_pmgr_access_lock(&backend->references[index], &access[index]);
		if (error)
			goto unlock;
		if (!access[index].provider->dev.driver->suppress_bind_attrs) {
			error = -ENODEV;
			goto unlock;
		}
	}
	return 0;
unlock:
	n71_genpd_unlock(access);
	return error;
}

static inline int n71_genpd_consumer_validate(struct n71_i2c_genpd *backend)
{
	struct device *consumer = backend->consumer;
	struct device_node *node = consumer->of_node, *expected;
	struct platform_device *controller;
	struct i2c_adapter *adapter;
	struct of_phandle_args domain;
	struct resource resource;
	const char *status;
	int error;

	if (!node || consumer->bus || consumer->driver || consumer->pm_domain ||
	    !device_is_registered(consumer))
		return -ENODEV;
	expected = of_find_node_by_path("/soc/i2c@20a111000");
	error = !expected || node != expected ? -ENODEV : 0;
	of_node_put(expected);
	if (error)
		return error;
	if (of_device_is_available(node) || of_get_child_count(node) ||
	    of_property_read_string(node, "status", &status) || strcmp(status, "disabled") ||
	    !of_device_is_compatible(node, "apple,s8000-i2c") ||
	    !of_device_is_compatible(node, "apple,i2c"))
		return -ENODEV;
	controller = of_find_device_by_node(node);
	if (controller) {
		put_device(&controller->dev);
		return -EBUSY;
	}
	adapter = of_find_i2c_adapter_by_node(node);
	if (adapter) {
		put_device(&adapter->dev);
		return -EBUSY;
	}
	error = of_address_to_resource(node, 0, &resource);
	if (error)
		return error;
	if (resource.start != 0x20a111000ULL || resource_size(&resource) != 0x1000 ||
	    resource_type(&resource) != IORESOURCE_MEM ||
	    of_count_phandle_with_args(node, "power-domains", "#power-domain-cells") != 1)
		return -ENODEV;
	error = of_parse_phandle_with_args(node, "power-domains", "#power-domain-cells", 0, &domain);
	if (error)
		return error;
	error = domain.np != backend->references[0].node || domain.args_count ? -ENODEV : 0;
	of_node_put(domain.np);
	return error;
}

static inline bool n71_genpd_runtime_matches(struct n71_i2c_genpd *backend, bool active)
{
	struct device *device = backend->domain;
	unsigned long flags;
	bool matches;

	if (!device || !device->pm_domain || !device_is_registered(device))
		return false;
	spin_lock_irqsave(&device->power.lock, flags);
	matches = device->power.runtime_status == (active ? RPM_ACTIVE : RPM_SUSPENDED) &&
		atomic_read(&device->power.usage_count) == (active ? 1 : 0) &&
		!atomic_read(&device->power.child_count) && !device->power.runtime_error &&
		!device->power.request_pending &&
		(!device->power.disable_depth || (!active && backend->detach_attempted &&
			device->power.disable_depth == 1));
	spin_unlock_irqrestore(&device->power.lock, flags);
	return matches;
}

static inline int n71_genpd_words(struct n71_pmgr_access access[3], bool active)
{
	unsigned int index, sample, word;
	int error;

	for (index = 0; index < (active ? 3U : 1U); index++) {
		for (sample = 0; sample < 2; sample++) {
			error = regmap_read_bypassed(access[index].map, n71_domains[index].offset, &word);
			if (error)
				return error;
			if (word & 0x80000400U)
				return -EIO;
			if (active) {
				if ((word & 0xfU) != 0xfU ||
				    ((word & 0xf0U) != 0xf0U && !(word & 0x10000000U)))
					return -EIO;
			} else if (word & 0x100000ffU) {
				return -EBUSY;
			}
		}
	}
	return 0;
}

static inline int n71_genpd_attach(void *context)
{
	struct n71_i2c_genpd *backend = context;
	struct n71_pmgr_access access[3] = {0};
	struct device *domain;
	int error = n71_genpd_lock(backend, access);

	if (error)
		return error;
	if (backend->domain) {
		error = -EBUSY;
		goto unlock;
	}
	error = n71_genpd_consumer_validate(backend);
	if (error)
		goto unlock;
	domain = dev_pm_domain_attach_by_id(backend->consumer, 0);
	if (IS_ERR_OR_NULL(domain)) {
		error = domain ? PTR_ERR(domain) : -ENODEV;
		goto unlock;
	}
	backend->domain = get_device(domain);
	backend->detach_attempted = false;
unlock:
	n71_genpd_unlock(access);
	return error;
}

static inline int n71_genpd_resume(void *context)
{
	struct n71_i2c_genpd *backend = context;
	struct n71_pmgr_access access[3] = {0};
	int error = n71_genpd_lock(backend, access);

	if (error)
		return error;
	if (!n71_genpd_runtime_matches(backend, false) || backend->detach_attempted)
		error = -EBUSY;
	else
		error = pm_runtime_resume_and_get(backend->domain);
	n71_genpd_unlock(access);
	return error;
}

static inline int n71_genpd_put_suspend(void *context)
{
	struct n71_i2c_genpd *backend = context;
	struct n71_pmgr_access access[3] = {0};
	int error;

	if (!backend || !backend->domain)
		return -ENODEV;
	error = n71_genpd_lock(backend, access);

	/* The lifecycle has already consumed its logical usage ownership. */
	if (error) {
		pm_runtime_put_noidle(backend->domain);
		return error;
	}
	if (atomic_read(&backend->domain->power.usage_count) != 1) {
		pm_runtime_put_noidle(backend->domain);
		error = -EBUSY;
	} else {
		error = pm_runtime_put_sync_suspend(backend->domain);
	}
	n71_genpd_unlock(access);
	return error;
}

static inline int n71_genpd_suspend(void *context)
{
	struct n71_i2c_genpd *backend = context;
	struct n71_pmgr_access access[3] = {0};
	int error = n71_genpd_lock(backend, access);

	if (error)
		return error;
	if (!backend->domain)
		error = -ENODEV;
	else if (backend->detach_attempted && n71_genpd_runtime_matches(backend, false))
		error = 0;
	else
		error = pm_runtime_suspend(backend->domain);
	n71_genpd_unlock(access);
	return error;
}

static inline int n71_genpd_verify(struct n71_i2c_genpd *backend, bool active)
{
	struct n71_pmgr_access access[3] = {0};
	int error = n71_genpd_lock(backend, access);

	if (error)
		return error;
	error = n71_genpd_runtime_matches(backend, active) ? n71_genpd_words(access, active) : -EBUSY;
	n71_genpd_unlock(access);
	return error;
}

static inline int n71_genpd_verify_active(void *context)
{
	return n71_genpd_verify(context, true);
}

static inline int n71_genpd_verify_quiescent(void *context)
{
	return n71_genpd_verify(context, false);
}

static inline int n71_genpd_detach(void *context)
{
	struct n71_i2c_genpd *backend = context;
	struct n71_pmgr_access access[3] = {0};
	struct device *domain;
	int error = n71_genpd_lock(backend, access);

	if (error)
		return error;
	if (!n71_genpd_runtime_matches(backend, false)) {
		error = -EBUSY;
		goto unlock;
	}
	error = n71_genpd_words(access, false);
	if (error)
		goto unlock;
	domain = backend->domain;
	backend->detach_attempted = true;
	dev_pm_domain_detach(domain, false);
	if (domain->pm_domain || device_is_registered(domain)) {
		error = -EBUSY;
		goto unlock;
	}
	backend->domain = NULL;
	backend->detach_attempted = false;
	put_device(domain);
unlock:
	n71_genpd_unlock(access);
	return error;
}

static inline struct n71_i2c_power_io n71_i2c_genpd_io(struct n71_i2c_genpd *backend)
{
	return (struct n71_i2c_power_io) {
		.context = backend, .attach = n71_genpd_attach,
		.resume_and_get = n71_genpd_resume, .put_and_suspend = n71_genpd_put_suspend,
		.suspend_zero_usage = n71_genpd_suspend, .verify_active = n71_genpd_verify_active,
		.verify_quiescent = n71_genpd_verify_quiescent, .detach_verified = n71_genpd_detach,
	};
}
#endif /* N71_I2C_GENPD_H */
