/* SPDX-License-Identifier: GPL-2.0-only */
/* Contract tests for the real diagnostic caller; native allocation is modeled. */
static void expect_allocation(const char *expected)
{
	char buffer[PAGE_SIZE];
	unsigned int references=mock.refs;
	assert(msi_allocation_ops.get(buffer,NULL)>0);
	if (strcmp(buffer,expected)) fprintf(stderr,"allocation expected: %sallocation actual: %s",expected,buffer);
	assert(!strcmp(buffer,expected));
	assert(mock.refs==references && !session_lock && !active_lock);
}

static void expect_allocation_log(const char *expected)
{
	assert(!strcmp(mock.allocation_log,expected));
}

static unsigned int exercise_allocation_caller(void)
{
	struct platform_device p;
	struct n71_scan_host *host, saved_host;
	struct n71_diagnostic saved_state;
	unsigned int index, cases=0;
	void *bus;
	bool running;
	struct platform_device *device;

	/* Mutations killed: bypass opt-in, pin or absence checks; publish a false ready host. */
	p=setup();
	expect_allocation("ready=0 held=0 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=0 session_error=0\n");
	assert(cleanup_ops.set("msi-hold",NULL)==-EINVAL && cleanup_ops.set("msi-release",NULL)==-EINVAL);
	assert(n71_probe(&p)==0 && !mock.msi_allocations && !mock.msi_release_calls);
	finish(&p); cases++;
	for (index=0;index<3;index++) {
		p=setup_iommu();
		if (index==0) scan_hold=false;
		if (index==1) msi_parent=false;
		if (index==2) iommu_parent=false;
		assert(cleanup_ops.set("msi-hold",NULL)==-EINVAL && cleanup_ops.set("msi-release",NULL)==-EINVAL);
		assert(!mock.refs && !mock.gets && !mock.msi_allocations && !mock.msi_release_calls);
		finish(&p); cases++;
	}
	p=setup_iommu();
	assert(cleanup_ops.set("msi-hold",NULL)==-ENODEV && cleanup_ops.set("msi-release",NULL)==-ENODEV);
	mock.live=false;
	assert(cleanup_ops.set("msi-hold",NULL)==-ENODEV && cleanup_ops.set("msi-release",NULL)==-ENODEV);
	assert(!mock.refs && !mock.msi_allocations && !mock.msi_release_calls);
	mock.live=true; finish(&p); cases++;

	/* Mutations killed: dispatch skips allocation, repeats a held vector, or loses a getter/report field. */
	p=setup_iommu(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
	host=&mock.bridge.private;
	expect_allocation("ready=1 held=1 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=0 session_error=0\n");
	assert(cleanup_ops.set("msi-hold\n",NULL)==0 && mock.refs==1 && mock.msi_allocations==1);
	expect_allocation("ready=1 held=1 owner=1 phase=1 vector=320 default_irq=19 software_enabled=1 slots=1 mappings=1 child=1 error=0 session_error=0\n");
	expect_allocation_log("N71_PCIE_MSI_ALLOCATION_RESULT action=hold error=0 owner=1 phase=1 vector=320 default_irq=19 software_enabled=1 slots=1 mappings=1 child=1 operation_error=0; no IRQ delivery or DMA\n");
	expect_msi("requested=1 ready=1 held=1 associated=1 owner=1 domain=1 mappings=1 child=1 session_error=0\n");
	assert(cleanup_ops.set("msi-hold",NULL)==-EBUSY && mock.msi_allocations==1 && !session->primary_error);
	assert(cleanup_ops.set("msi-release",NULL)==0 && mock.refs==1 && mock.msi_vector_releases==1);
	expect_allocation("ready=1 held=1 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=1 error=0 session_error=0\n");
	expect_allocation_log("N71_PCIE_MSI_ALLOCATION_RESULT action=release error=0 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=1 operation_error=0; no IRQ delivery or DMA\n");
	assert(cleanup_ops.set("msi-hold",NULL)==-EALREADY && !session->primary_error && mock.msi_allocations==1);
	assert(cleanup_ops.set("cleanup",NULL)==0 && mock.msi_vector_releases==1 && mock.bus_removals==1 && !mock.refs);
	expect_allocation("ready=0 held=0 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=0 session_error=0\n");
	finish(&p); cases++;

	/* Mutations killed: bypass retained power/reset/bus/provider guards or poison a refused request. */
	p=setup_iommu(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
	host=&mock.bridge.private;
	for (index=0;index<15;index++) {
		int expected=index<3 ? -ENODEV : index<12 ? -EBUSY : -EACCES;
		saved_state=*session; saved_host=*host; bus=mock.bridge.bus;
		running=mock.dart.lease.running; device=mock.dart.device;
		switch(index) {
		case 0: session->scan_bridge=NULL; break;
		case 1: mock.bridge.bus=NULL; break;
		case 2: host->bus_held=false; break;
		case 3: session->attached=3; break;
		case 4: session->powered=3; break;
		case 5: session->power_put_pending=true; break;
		case 6: session->reset_pending=false; break;
		case 7: session->module_retained=false; break;
		case 8: session->primary_error=-ENOLINK; break;
		case 9: session->cleanup_error=-ETIMEDOUT; break;
		case 10: host->msi_allocation.vector=320; break;
		case 11: host->msi_config.phase=N71_MSI_CONFIG_ACTIVE; break;
		case 12: session->dart=NULL; break;
		case 13: mock.dart.lease.running=false; break;
		default: mock.dart.device=NULL; break;
		}
		assert(cleanup_ops.set("msi-hold",NULL)==expected && mock.refs==1 && !mock.msi_allocations);
		assert(session->primary_error==saved_state.primary_error || index==8);
		assert(!mock.msi_release_calls && !mock.consumer_calls && !mock.resets && !mock.puts);
		*session=saved_state; *host=saved_host; mock.bridge.bus=bus;
		mock.dart.lease.running=running; mock.dart.device=device; cases++;
	}
	assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.msi_release_calls);
	finish(&p);

	/* Mutations killed: hide an allocator failure after host removal or allocate again after failure. */
	p=setup_iommu(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
	mock.allocation_early_error=-EACCES;
	assert(cleanup_ops.set("msi-hold",NULL)==-EACCES && mock.refs==1 && !mock.msi_allocations);
	assert(cleanup_ops.set("msi-hold",NULL)==-EBUSY && !mock.msi_allocations);
	expect_allocation("ready=1 held=1 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=-13 session_error=0\n");
	assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs && !mock.msi_release_calls);
	expect_allocation("ready=0 held=0 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=-13 session_error=0\n");
	finish(&p); cases++;

	/* Mutations killed: free consumers/providers/power before stop and restore; ignore retained ownership. */
	for (index=0;index<4;index++) {
		int expected=index==3 ? -EBUSY : -EIO;
		p=setup_iommu(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
		if (index==2) mock.allocation_error=-EACCES;
		assert(cleanup_ops.set("msi-hold",NULL)==(index==2 ? -EACCES : 0));
		if (index==2)
			expect_allocation_log("N71_PCIE_MSI_ALLOCATION_RESULT action=hold error=-13 owner=1 phase=1 vector=320 default_irq=19 software_enabled=1 slots=1 mappings=1 child=1 operation_error=-13; no IRQ delivery or DMA\n");
		if (index<3) mock.vector_release_error=-EIO;
		if (index==1) mock.vector_release_stopped=true;
		if (index==3) mock.vector_release_pending=true;
		assert(cleanup_ops.set("msi-release",NULL)==expected && mock.refs==1 && !mock.msi_vector_releases);
		assert(cleanup_ops.set("cleanup",NULL)==expected && session->cleanup_error==expected);
		if (index==3)
			expect_allocation_log("N71_PCIE_MSI_ALLOCATION_RESULT action=cleanup error=-16 owner=1 phase=1 vector=320 default_irq=19 software_enabled=1 slots=1 mappings=1 child=1 operation_error=0; no IRQ delivery or DMA\n");
		assert(mock.bridge.bus && host==&mock.bridge.private && mock.dart.lease.running && session->module_retained);
		assert(!mock.consumer_calls && !mock.dart_releases && !mock.resets && !mock.puts);
		if (index==1)
			expect_allocation("ready=1 held=1 owner=1 phase=2 vector=320 default_irq=19 software_enabled=0 slots=0 mappings=0 child=1 error=-5 session_error=-5\n");
		if (index==2)
			expect_allocation("ready=1 held=1 owner=1 phase=1 vector=320 default_irq=19 software_enabled=1 slots=1 mappings=1 child=1 error=-13 session_error=-5\n");
		assert(cleanup_ops.set("msi-hold",NULL)==-EBUSY && mock.msi_allocations==1);
		mock.vector_release_error=0; mock.vector_release_pending=false;
		/* Release remains possible with prior errors and a provider already stopped. */
		mock.dart.lease.running=false;
		assert(cleanup_ops.set("msi-release",NULL)==0 && mock.msi_vector_releases==1 && mock.refs==1);
		assert(session->primary_error==(index==2 ? -EACCES : 0));
		mock.dart.lease.running=true;
		assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs && mock.bus_removals==1);
		assert(mock.dart_releases==1 && mock.puts==4 && mock.msi_allocations==1);
		finish(&p); cases++;
	}

	/* Mutations killed: omit any residual lease field from the cleanup predicate. */
	for (index=0;index<4;index++) {
		p=setup_iommu(); assert(n71_probe(&p)==0);
		host=&mock.bridge.private;
		if (index==0) host->msi_allocation.endpoint=&mock.msi_endpoint;
		if (index==1) host->msi_allocation.vector=320;
		if (index==2) host->msi_allocation.default_irq=19;
		if (index==3) host->msi_config.phase=N71_MSI_CONFIG_STOPPED;
		mock.vector_release_pending=true;
		assert(cleanup_ops.set("cleanup",NULL)==-EBUSY && mock.msi_release_calls==1 && mock.refs==1);
		assert(!mock.consumer_calls && !mock.dart_releases && !mock.resets && !mock.puts && mock.bridge.bus);
		memset(&host->msi_allocation,0,sizeof(host->msi_allocation)); host->msi_config.phase=N71_MSI_CONFIG_EMPTY;
		mock.vector_release_pending=false;
		assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs && mock.msi_release_calls==1);
		finish(&p); cases++;
	}

	/* Mutations killed: getter reads stale owners, ignores error precedence or hides cleanup after removal. */
	p=setup_iommu(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
	host=&mock.bridge.private;
	host->config.error=-EACCES; host->io_error=-EIO;
	expect_allocation("ready=1 held=1 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=-13 session_error=0\n");
	host->config.error=0;
	expect_allocation("ready=1 held=1 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=-5 session_error=0\n");
	host->io_error=0;
	assert(cleanup_ops.set("msi-hold",NULL)==0);
	saved_host=*host; bus=mock.bridge.bus;
	host->msi.native.domain=NULL; host->msi.native.child=NULL; mock.bridge.bus=NULL;
	expect_allocation("ready=1 held=0 owner=1 phase=1 vector=320 default_irq=19 software_enabled=1 slots=1 mappings=0 child=0 error=0 session_error=0\n");
	*host=saved_host; mock.bridge.bus=bus;
	mock.fault=RESET_READ;
	assert(cleanup_ops.set("cleanup",NULL)==-EIO && !session->scan_bridge && mock.refs==1);
	expect_allocation_log("N71_PCIE_MSI_ALLOCATION_RESULT action=cleanup error=0 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=1 operation_error=0; no IRQ delivery or DMA\n");
	expect_allocation("ready=0 held=0 owner=0 phase=0 vector=0 default_irq=0 software_enabled=0 slots=0 mappings=0 child=0 error=0 session_error=-5\n");
	mock.fault=NONE;
	assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs && mock.msi_vector_releases==1);
	finish(&p); cases++;
	return cases;
}
