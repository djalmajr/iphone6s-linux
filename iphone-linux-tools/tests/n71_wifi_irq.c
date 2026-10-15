/* Compile the actual patched brcmfmac method against observable PCI/IRQ mocks. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#define PCIE 0
#define IRQF_SHARED 0x80
#define brcmf_dbg(...) ((void)0)
#define brcmf_err(bus, ...) ((void)(bus))

struct brcmf_bus { int marker; };
struct device { struct brcmf_bus *data; };
struct pci_dev { struct device dev; int irq; bool msi_enabled; };
struct brcmf_pciedev_info { struct pci_dev *pdev; bool irq_allocated; };
typedef int (*irq_handler_t)(int, void *);

static struct brcmf_bus bus;
static struct pci_dev device;
static struct brcmf_pciedev_info info;
static int msi_result, irq_result, disable_count, request_count;
static char calls[8];
static unsigned int call_count;

static void record(char call)
{
	assert(call_count + 1 < sizeof(calls));
	calls[call_count++] = call;
}

static void *dev_get_drvdata(struct device *dev)
{
	assert(dev == &device.dev);
	return dev->data;
}

static void brcmf_pcie_intr_disable(struct brcmf_pciedev_info *devinfo)
{
	assert(devinfo == &info);
	record('D');
}

static int pci_enable_msi(struct pci_dev *pdev)
{
	assert(pdev == &device);
	assert(!pdev->msi_enabled);
	record('M');
	if (!msi_result) {
		pdev->irq = 73;
		pdev->msi_enabled = true;
	}
	return msi_result;
}

static void pci_disable_msi(struct pci_dev *pdev)
{
	assert(pdev == &device && pdev->msi_enabled);
	record('X');
	disable_count++;
	pdev->msi_enabled = false;
}

static int brcmf_pcie_quick_check_isr(int irq, void *data)
{
	(void)irq;
	(void)data;
	return 0;
}

static int brcmf_pcie_isr_thread(int irq, void *data)
{
	(void)irq;
	(void)data;
	return 0;
}

static int request_threaded_irq(int irq, irq_handler_t quick, irq_handler_t thread,
				unsigned long flags, const char *name, void *data)
{
	assert(msi_result == 0 && device.msi_enabled);
	assert(irq == 73 && quick == brcmf_pcie_quick_check_isr);
	assert(thread == brcmf_pcie_isr_thread && flags == IRQF_SHARED);
	assert(!strcmp(name, "brcmf_pcie_intr") && data == &info);
	record('R');
	request_count++;
	return irq_result;
}

#include "n71_wifi_irq_method.h"

static void reset(int msi, int irq, int old_irq)
{
	memset(&device, 0, sizeof(device));
	memset(&info, 0, sizeof(info));
	memset(calls, 0, sizeof(calls));
	device.dev.data = &bus;
	device.irq = old_irq;
	info.pdev = &device;
	msi_result = msi;
	irq_result = irq;
	disable_count = request_count = call_count = 0;
}

int main(void)
{
	const int errors[] = {-ENOSPC, -EBUSY, -EINVAL, -EIO, -ENODEV, -ENOMEM};
	const int old_irqs[] = {0, 31};
	unsigned int i, j, cases = 0;
	for (i = 0; i < sizeof(errors) / sizeof(errors[0]); i++) {
		for (j = 0; j < sizeof(old_irqs) / sizeof(old_irqs[0]); j++) {
			reset(errors[i], 0, old_irqs[j]);
			assert(brcmf_pcie_request_irq(&info) == errors[i]);
			assert(!strcmp(calls, "DM"));
			assert(!request_count && !disable_count);
			assert(!info.irq_allocated && !device.msi_enabled);
			assert(device.irq == old_irqs[j]);
			cases++;
		}
	}
	for (i = 0; i < 3; i++) {
		reset(0, errors[i], 31);
		assert(brcmf_pcie_request_irq(&info) == -EIO);
		assert(!strcmp(calls, "DMRX"));
		assert(request_count == 1 && disable_count == 1);
		assert(!info.irq_allocated && !device.msi_enabled);
		cases++;
	}
	reset(0, 0, 31);
	assert(brcmf_pcie_request_irq(&info) == 0);
	assert(!strcmp(calls, "DMR"));
	assert(request_count == 1 && !disable_count);
	assert(info.irq_allocated && device.msi_enabled);
	cases++;
	printf("N71_BRCMFMAC_IRQ_OK cases=%u\n", cases);
	return 0;
}
