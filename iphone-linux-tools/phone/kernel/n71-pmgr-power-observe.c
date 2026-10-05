// SPDX-License-Identifier: GPL-2.0-only
/* Observe I2C1 PMGR states through the already initialized syscon provider. */
#include <linux/module.h>
#include "n71-pmgr-access.h"

static bool run;
module_param(run, bool, 0400);
MODULE_PARM_DESC(run, "Observe existing N71 I2C1/sio_p/sio_busif states; no activation");

static int __init n71_pmgr_power_observe_init(void)
{
	struct device_node *pmgr, *node;
	unsigned int words[3][2], index;
	int error = -ENODEV;

	if (!run)
		return -ENODEV;
	pmgr = of_find_node_by_path(N71_PMGR_PATH);
	if (!pmgr)
		return -ENODEV;
	error = n71_pmgr_root_validate(pmgr);
	if (error)
		goto put_pmgr;
	for (index = 0; index < 3; index++) {
		node = of_find_node_by_path(n71_domains[index].path);
		if (!node) {
			error = -ENODEV;
			goto put_pmgr;
		}
		{
			const struct n71_pmgr_reference reference = {
				.index = index, .node = node, .pmgr = pmgr,
			};
			error = n71_pmgr_sample(&reference, words[index]);
		}
		of_node_put(node);
		if (error)
			goto put_pmgr;
	}
	for (index = 0; index < 3; index++)
		pr_info("N71_PMGR domain=%s offset=%05x sample0=%08x sample1=%08x stable=%u\n",
			n71_domains[index].label, n71_domains[index].offset,
			words[index][0], words[index][1], words[index][0] == words[index][1]);
	pr_info("N71_PMGR_OBSERVED writes=0 reads=6 atomic-chain=0 ownership=0\n");
put_pmgr:
	of_node_put(pmgr);
	return error;
}

static void __exit n71_pmgr_power_observe_exit(void)
{
	pr_info("N71_PMGR_UNLOADED hardware-changes=0\n");
}
module_init(n71_pmgr_power_observe_init);
module_exit(n71_pmgr_power_observe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("N71 bounded PMGR observation without domain activation");
