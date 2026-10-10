/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef N71_MSI_ALLOCATION_LEASE_H
#define N71_MSI_ALLOCATION_LEASE_H
struct pci_dev;
struct n71_msi_allocation {
	struct pci_dev *endpoint;
	unsigned int default_irq, vector;
};
#endif /* N71_MSI_ALLOCATION_LEASE_H */
