/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdio.h>
#ifdef __linux__
#include <sys/prctl.h>
#endif
#include "n71_wlan_msi_host_fixture.h"
#include "n71-wlan-msi-host.h"

static unsigned int cases;
static void initialize(struct n71_wlan_msi_host *owner, struct pci_host_bridge *bridge,
			struct n71_wlan_msi_host_request *request, bool flag)
{
	cases++; memset(owner, 0, sizeof(*owner)); memset(bridge, 0, sizeof(*bridge));
	memset(&host_fixture, 0, sizeof(host_fixture)); host_fixture.bridge = bridge;
	bridge->msi_domain = flag;
	*request = (struct n71_wlan_msi_host_request){bridge, &host_fixture.request, &host_fixture.spec};
}
static void released(struct n71_wlan_msi_host *owner, struct pci_host_bridge *bridge, bool flag)
{
	assert(n71_wlan_msi_host_release(owner) == 0);
	assert(!owner->bridge && !owner->associated && !owner->native.domain && !host_fixture.resources);
	assert(!bridge->dev.domain && bridge->msi_domain == flag);
	unsigned int calls = host_fixture.release_calls;
	assert(n71_wlan_msi_host_release(owner) == 0 && calls == host_fixture.release_calls);
}
int main(void)
{
#ifdef __linux__
	assert(prctl(PR_SET_DUMPABLE, 0) == 0);
#endif
	struct n71_wlan_msi_host owner;
	struct pci_host_bridge bridge;
	struct n71_wlan_msi_host_request request;
	/* Mutations: ignore native acquire failure, lose partial owner, skip association or overwrite a live bridge. */
	for (unsigned int flag = 0; flag < 2; flag++) for (unsigned int fault = 0; fault < 4; fault++) {
		initialize(&owner, &bridge, &request, flag); host_fixture.fail_acquire = fault;
		int error = n71_wlan_msi_host_acquire(&owner, &request);
		assert(error == (fault == 1 ? -EINVAL : fault ? -ENOMEM : 0));
		assert(owner.bridge == &bridge && owner.saved_msi_domain == flag && host_fixture.acquire_calls == 1);
		assert(owner.associated == !fault && bridge.msi_domain == (fault ? flag : true));
		assert(bridge.dev.domain == (fault ? NULL : owner.native.domain));
		assert(n71_wlan_msi_host_acquire(&owner, &request) == -EBUSY && host_fixture.acquire_calls == 1);
		released(&owner, &bridge, flag);
	}
	/* Mutations: free a live bus, free parent before detach, drop owner on teardown error or lose previous flag. */
	for (unsigned int flag = 0; flag < 2; flag++) {
		initialize(&owner, &bridge, &request, flag);
		assert(n71_wlan_msi_host_acquire(&owner, &request) == 0);
		bridge.bus = &host_fixture;
		assert(n71_wlan_msi_host_release(&owner) == -EBUSY && !host_fixture.release_calls);
		assert(owner.associated && bridge.dev.domain == owner.native.domain && host_fixture.resources == 3);
		bridge.bus = NULL; owner.native.child = &host_fixture.child;
		assert(n71_wlan_msi_host_release(&owner) == -EBUSY && !owner.associated && owner.bridge == &bridge);
		assert(!bridge.dev.domain && bridge.msi_domain == flag && host_fixture.resources == 3);
		host_fixture.release_error = -EIO; owner.native.child = NULL;
		assert(n71_wlan_msi_host_release(&owner) == -EIO && owner.bridge == &bridge && host_fixture.resources == 3);
		host_fixture.release_error = 0; released(&owner, &bridge, flag);
	}
	/* Mutations: accept foreign bridge state or clear an association whose identity no longer matches. */
	for (unsigned int kind = 0; kind < 5; kind++) {
		initialize(&owner, &bridge, &request, false);
		if (kind < 2) {
			if (!kind) bridge.bus = &host_fixture;
			else bridge.dev.domain = &host_fixture.foreign;
			assert(n71_wlan_msi_host_acquire(&owner, &request) == -EBUSY);
			assert(!owner.bridge && !host_fixture.acquire_calls && !host_fixture.resources);
			assert(!kind ? bridge.bus != NULL : bridge.dev.domain == &host_fixture.foreign);
			continue;
		}
		assert(n71_wlan_msi_host_acquire(&owner, &request) == 0);
		if (kind == 2) bridge.dev.domain = &host_fixture.foreign;
		if (kind == 3) bridge.dev.domain = NULL;
		if (kind == 4) bridge.msi_domain = false;
		assert(n71_wlan_msi_host_release(&owner) == -EINVAL && owner.associated && owner.bridge == &bridge);
		assert(!host_fixture.release_calls && host_fixture.resources == 3);
		bridge.dev.domain = owner.native.domain; bridge.msi_domain = true;
		released(&owner, &bridge, false);
	}
	initialize(&owner, &bridge, &request, false); host_fixture.fail_acquire = 2;
	assert(n71_wlan_msi_host_acquire(&owner, &request) == -ENOMEM);
	bridge.dev.domain = &host_fixture.foreign;
	assert(n71_wlan_msi_host_release(&owner) == -EBUSY && !host_fixture.release_calls && host_fixture.resources == 1);
	assert(bridge.dev.domain == &host_fixture.foreign && owner.bridge == &bridge);
	bridge.dev.domain = NULL; released(&owner, &bridge, false);
	/* Mutations: omit argument guards; no bridge/native effect is allowed on invalid input. */
	for (unsigned int kind = 0; kind < 5; kind++) {
		initialize(&owner, &bridge, &request, false);
		if (kind == 2) request.bridge = NULL;
		if (kind == 3) request.message = NULL;
		if (kind == 4) request.spec = NULL;
		assert(n71_wlan_msi_host_acquire(!kind ? NULL : &owner, kind == 1 ? NULL : &request) == -EINVAL);
		assert(!owner.bridge && !bridge.dev.domain && !host_fixture.acquire_calls);
	}
	assert(n71_wlan_msi_host_release(NULL) == -EINVAL);
	printf("N71_WLAN_MSI_HOST_OK cases=%u\n", cases);
	return 0;
}
