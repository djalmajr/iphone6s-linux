// SPDX-License-Identifier: GPL-2.0-only
#include <linux/module.h>
#include "n71-brcmfmac-config.h"
int n71_probe_capture(const struct n71_scan_io *, struct n71_brcmfmac_config *);
int n71_probe_write(const struct n71_scan_io *, struct n71_brcmfmac_config *, const struct n71_msi_config_request *);
int n71_probe_restore(const struct n71_scan_io *, struct n71_brcmfmac_config *, const struct n71_brcmfmac_quiescent *);
int n71_probe_capture(const struct n71_scan_io *io, struct n71_brcmfmac_config *state)
{ return n71_brcmfmac_capture(io, state); }
int n71_probe_write(const struct n71_scan_io *io, struct n71_brcmfmac_config *state, const struct n71_msi_config_request *request)
{ return n71_brcmfmac_write(io, state, request); }
int n71_probe_restore(const struct n71_scan_io *io, struct n71_brcmfmac_config *state, const struct n71_brcmfmac_quiescent *core)
{ return n71_brcmfmac_restore(io, state, core); }
static int __init n71_probe_init(void) { return 0; }
static void __exit n71_probe_exit(void) { }
module_init(n71_probe_init);
module_exit(n71_probe_exit);
MODULE_LICENSE("GPL");
