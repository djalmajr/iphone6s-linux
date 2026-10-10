/* SPDX-License-Identifier: GPL-2.0-only */
/* Session mutex owns actions and lifetime; host spinlock protects config errors. */
#ifndef N71_PCIE_BRCMFMAC_CALLER_H
#define N71_PCIE_BRCMFMAC_CALLER_H

enum n71_driver_action {
	N71_DRIVER_PREPARE,
	N71_DRIVER_PUBLISH,
	N71_DRIVER_RELEASE,
};

static void n71_driver_latch_error(struct n71_diagnostic *state, struct n71_scan_host *host)
{
	unsigned long flags;
	int error;

	spin_lock_irqsave(&host->lock, flags);
	error = host->brcmfmac.error ? host->brcmfmac.error : n71_msi_allocation_error(host);
	if (!state->primary_error && error)
		state->primary_error = error;
	spin_unlock_irqrestore(&host->lock, flags);
}

static void n71_driver_report(struct n71_scan_host *host, const char *action, int error)
{
	unsigned long flags;

	spin_lock_irqsave(&host->lock, flags);
	dev_info(session_device, "N71_PCIE_DRIVER_RESULT action=%s error=%d pending=%u active=%u published=%u root=%u endpoint=%u pm=%u root_override=%u endpoint_override=%u operation_error=%d; not firmware or radio proof\n",
		 action, error, n71_scan_driver_pending(host), host->brcmfmac.active,
		 host->driver_published, !!host->driver_root, !!host->driver_endpoint,
		 host->driver_pm, host->driver_root_override, host->driver_endpoint_override,
		 host->brcmfmac.error);
	spin_unlock_irqrestore(&host->lock, flags);
}

static int n71_driver_cleanup(struct n71_diagnostic *state, struct n71_scan_host *host)
{
	int error;

	if (!n71_scan_driver_pending(host) && !host->driver_published && !host->brcmfmac.error)
		return 0;
	n71_driver_latch_error(state, host);
	if (!n71_scan_driver_pending(host))
		return 0;
	error = n71_pcie_brcmfmac_release(state->scan_bridge, host);
	n71_driver_latch_error(state, host);
	if (!error && n71_scan_driver_pending(host))
		error = -EBUSY;
	if (error && error != -EBUSY && !state->primary_error)
		state->primary_error = error;
	n71_driver_report(host, "cleanup", error);
	return error;
}

static int n71_driver_action(enum n71_driver_action action)
{
	struct n71_scan_host *host;
	int error;

	if (action != N71_DRIVER_RELEASE && (!driver_runtime || !scan_hold || !msi_parent || !iommu_parent))
		return -EINVAL;
	if (!try_module_get(THIS_MODULE))
		return -ENODEV;
	mutex_lock(&session_lock);
	if (!session || !n71_session_has_held_bus(session)) {
		error = -ENODEV;
	} else if (session->attached != 4 || session->powered != 4 || session->power_put_pending ||
		   !session->reset_pending || !session->module_retained) {
		error = -EBUSY;
	} else {
		host = pci_host_bridge_priv(session->scan_bridge);
		n71_driver_latch_error(session, host);
		if (action != N71_DRIVER_RELEASE && (session->primary_error || session->cleanup_error)) {
			error = -EBUSY;
		} else if (action != N71_DRIVER_RELEASE &&
			   (!session->dart || !session->dart->lease.running || !session->dart->device)) {
			error = -EACCES;
		} else if (action != N71_DRIVER_RELEASE && n71_msi_allocation_pending(host)) {
			error = -EBUSY;
		} else {
			if (action == N71_DRIVER_PREPARE)
				error = n71_pcie_brcmfmac_prepare(session->scan_bridge, host);
			else if (action == N71_DRIVER_PUBLISH)
				error = n71_pcie_brcmfmac_publish(session->scan_bridge, host);
			else
				error = n71_pcie_brcmfmac_release(session->scan_bridge, host);
			n71_driver_latch_error(session, host);
			if (action == N71_DRIVER_RELEASE && !error && n71_scan_driver_pending(host))
				error = -EBUSY;
			if (error && error != -EALREADY && error != -EBUSY && !session->primary_error)
				session->primary_error = error;
		}
		n71_driver_report(host, action == N71_DRIVER_PREPARE ? "prepare" :
				  action == N71_DRIVER_PUBLISH ? "publish" : "release", error);
	}
	mutex_unlock(&session_lock);
	module_put(THIS_MODULE);
	return error;
}

static int n71_driver_status(char *buffer, const struct kernel_param *parameter)
{
	struct n71_scan_host *host = NULL;
	unsigned long flags = 0;
	int length, error;

	(void)parameter;
	mutex_lock(&session_lock);
	if (session && session->scan_bridge) {
		host = pci_host_bridge_priv(session->scan_bridge);
		spin_lock_irqsave(&host->lock, flags);
	}
	error = session && session->primary_error ? session->primary_error :
		host ? host->brcmfmac.error ? host->brcmfmac.error : n71_msi_allocation_error(host) : 0;
	length = scnprintf(buffer, PAGE_SIZE,
		"requested=%u ready=%u held=%u pending=%u active=%u published=%u root=%u endpoint=%u pm=%u root_override=%u endpoint_override=%u reads=%u operation_error=%d error=%d session_error=%d\n",
		driver_runtime, !!host, n71_session_has_held_bus(session),
		host ? n71_scan_driver_pending(host) : 0, host ? host->brcmfmac.active : 0,
		host ? host->driver_published : 0, host ? !!host->driver_root : 0,
		host ? !!host->driver_endpoint : 0, host ? host->driver_pm : 0,
		host ? host->driver_root_override : 0, host ? host->driver_endpoint_override : 0,
		host ? host->driver_reads : 0, host ? host->brcmfmac.error : 0, error,
		session ? session->cleanup_error : 0);
	if (host)
		spin_unlock_irqrestore(&host->lock, flags);
	mutex_unlock(&session_lock);
	return length;
}
#endif /* N71_PCIE_BRCMFMAC_CALLER_H */
