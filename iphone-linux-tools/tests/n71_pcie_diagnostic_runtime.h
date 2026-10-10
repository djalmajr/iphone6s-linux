/* SPDX-License-Identifier: GPL-2.0-only */
/* Caller contract only; PCI, firmware, radio and IRQ effects are modeled. */
#ifndef N71_PCIE_DIAGNOSTIC_RUNTIME_FIXTURE_H
#define N71_PCIE_DIAGNOSTIC_RUNTIME_FIXTURE_H

static struct platform_device setup_runtime(void)
{
	struct platform_device p=setup_iommu();
	driver_runtime=true;
	return p;
}

static void expect_driver(const char *expected)
{
	char buffer[PAGE_SIZE];
	assert(driver_ops.get(buffer,NULL)>0 && !strcmp(buffer,expected));
	assert(!session_lock && !active_lock && !mock.bridge.private.lock);
}

static void runtime_finish(struct platform_device *p)
{
	int primary=session->primary_error;
	assert(cleanup_ops.set("cleanup",NULL)==0 && !mock.refs);
	assert(session->primary_error==primary);
	assert(!mock.bridge.private.lock && !mock.bridge.private.brcmfmac.active);
	finish(p);
}

static unsigned int exercise_runtime_caller(void)
{
	struct platform_device p;
	struct n71_diagnostic *state, saved_state;
	struct n71_scan_host *host=&mock.bridge.private, saved_host;
	struct n71_dart_provider saved_dart;
	unsigned int index, cases=0;
	char expected[PAGE_SIZE];
	void *bus;
	int error;

	/* Mutations: default opt-in, dependency, action dispatch, pin or getter readiness. */
	p=setup();
	expect_driver("requested=0 ready=0 held=0 pending=0 active=0 published=0 root=0 endpoint=0 pm=0 root_override=0 endpoint_override=0 reads=0 operation_error=0 error=0 session_error=0\n");
	assert(cleanup_ops.set("driver-prepare",NULL)==-EINVAL && !mock.refs);
	driver_runtime=true;
	assert(n71_init()==-EINVAL && !mock.registered && !mock.scans);
	assert(cleanup_ops.set("driver-prepare",NULL)==-EINVAL);
	scan_hold=msi_parent=iommu_parent=true;
	assert(cleanup_ops.set("driver-prepare",NULL)==-ENODEV && !mock.refs);
	assert(cleanup_ops.set("driver-publish",NULL)==-ENODEV && !mock.refs);
	assert(cleanup_ops.set("driver-release",NULL)==-ENODEV && !mock.refs);
	finish(&p); cases++;

	/* Mutations: probe activates runtime, action misses effects or retries publication. */
	p=setup_runtime();
	assert(n71_init()==0 && !mock.scans && !mock.runtime.prepares);
	assert(n71_probe(&p)==0 && mock.refs==1 && !mock.runtime.prepares && !mock.runtime.publishes);
	expect_driver("requested=1 ready=1 held=1 pending=0 active=0 published=0 root=0 endpoint=0 pm=0 root_override=0 endpoint_override=0 reads=0 operation_error=0 error=0 session_error=0\n");
	assert(cleanup_ops.set("assign",NULL)==0);
	assert(cleanup_ops.set("driver-preparejunk",NULL)==-EINVAL && !mock.runtime.prepares);
	assert(cleanup_ops.set("driver-prepare\n",NULL)==0 && mock.runtime.prepares==1 && mock.refs==1);
	assert(strstr(mock.runtime.log,"action=prepare error=0 pending=1 active=1 published=0 root=1 endpoint=1 pm=1 root_override=1 endpoint_override=1 operation_error=0; not firmware or radio proof"));
	assert(cleanup_ops.set("driver-prepare",NULL)==-EBUSY && !session->primary_error);
	assert(cleanup_ops.set("driver-publish",NULL)==0 && mock.runtime.publishes==1);
	assert(strstr(mock.runtime.log,"action=publish error=0 pending=1 active=1 published=1"));
	assert(cleanup_ops.set("driver-publish",NULL)==-EALREADY && !session->primary_error && mock.runtime.publishes==1);
	assert(!mock.puts && !mock.resets && !mock.consumer_calls && !mock.dart_releases && mock.scans==1);
	expect_driver("requested=1 ready=1 held=1 pending=1 active=1 published=1 root=1 endpoint=1 pm=1 root_override=1 endpoint_override=1 reads=0 operation_error=0 error=0 session_error=0\n");
	cases++;

	/* Mutations: manual MSI enters its adapter or changes first cause during runtime. */
	assert(cleanup_ops.set("msi-hold",NULL)==-EBUSY && !mock.msi_allocations && !session->primary_error);
	assert(cleanup_ops.set("msi-release",NULL)==-EBUSY && !mock.msi_release_calls && !mock.allocation_log[0]);
	assert(mock.refs==1 && !mock.puts && !mock.resets); cases++;

	/* Mutations: getter drops a field, latches errors, changes owners or skips host lock. */
	for (index=0;index<15;index++) {
		saved_state=*session; saved_host=*host; bus=mock.bridge.bus;
		switch(index) {
		case 0: driver_runtime=false; break;
		case 1: mock.bridge.bus=NULL; break;
		case 2: host->bus_held=false; break;
		case 3: host->brcmfmac.active=false; break;
		case 4: host->driver_published=false; break;
		case 5: host->driver_root=NULL; break;
		case 6: host->driver_endpoint=NULL; break;
		case 7: host->driver_pm=false; break;
		case 8: host->driver_root_override=false; break;
		case 9: host->driver_endpoint_override=false; break;
		case 10: host->driver_reads=5001; break;
		case 11: host->brcmfmac.error=-ENOLINK; break;
		case 12: host->brcmfmac.error=-ENOLINK; session->primary_error=-ETIMEDOUT; break;
		case 13: host->io_error=-EIO; break;
		default: session->cleanup_error=-EAGAIN; break;
		}
		struct n71_diagnostic observed_state=*session;
		snprintf(expected,sizeof(expected),
			"requested=%u ready=1 held=%u pending=1 active=%u published=%u root=%u endpoint=%u pm=%u root_override=%u endpoint_override=%u reads=%u operation_error=%d error=%d session_error=%d\n",
			index!=0,index!=1 && index!=2,index!=3,index!=4,index!=5,index!=6,index!=7,
			index!=8,index!=9,index==10 ? 5001U : 0U,index==11 || index==12 ? -ENOLINK : 0,
			index==12 ? -ETIMEDOUT : index==11 ? -ENOLINK : index==13 ? -EIO : 0,
			index==14 ? -EAGAIN : 0);
		expect_driver(expected);
		assert(!memcmp(session,&observed_state,sizeof(observed_state)) && mock.refs==1 && !mock.puts);
		*session=saved_state; *host=saved_host; mock.bridge.bus=bus; driver_runtime=true; cases++;
	}

	/* Mutations: busy release poisons first cause, release requires opt-in, or cleanup is reordered. */
	mock.runtime.release_error=-EBUSY;
	assert(cleanup_ops.set("driver-release",NULL)==-EBUSY && !session->primary_error && mock.refs==1);
	assert(cleanup_ops.set("cleanup",NULL)==-EBUSY && session->cleanup_error==-EBUSY);
	assert(!mock.consumer_calls && !mock.dart_releases && !mock.puts && !mock.resets && host->driver_pm);
	mock.runtime.release_error=0;
	driver_runtime=scan_hold=msi_parent=iommu_parent=false;
	session->primary_error=-ETIMEDOUT; host->brcmfmac.error=-ENOLINK; mock.dart.lease.running=false;
	assert(cleanup_ops.set("driver-release",NULL)==0 && !n71_scan_driver_pending(host));
	assert(strstr(mock.runtime.log,"action=release error=0 pending=0 active=0 published=1"));
	assert(session->primary_error==-ETIMEDOUT && mock.refs==1 && !mock.consumer_calls);
	scan_hold=msi_parent=iommu_parent=true;
	runtime_finish(&p); n71_exit();
	expect_driver("requested=0 ready=0 held=0 pending=0 active=0 published=0 root=0 endpoint=0 pm=0 root_override=0 endpoint_override=0 reads=0 operation_error=0 error=0 session_error=0\n");
	cases++;

	/* Mutations: omit opt-in, session, power, provider, first-cause or manual-lease gate. */
	for (index=0;index<26;index++) {
		p=setup_runtime(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
		state=session; saved_state=*state; saved_host=*host; saved_dart=mock.dart; bus=mock.bridge.bus;
		error=index<4 ? -EINVAL : index<8 ? -ENODEV : index<15 ? -EBUSY : index<18 ? -EACCES : -EBUSY;
		switch(index) {
		case 0: driver_runtime=false; break;
		case 1: scan_hold=false; break;
		case 2: msi_parent=false; break;
		case 3: iommu_parent=false; break;
		case 4: mock.live=false; break;
		case 5: session=NULL; break;
		case 6: mock.bridge.bus=NULL; break;
		case 7: host->bus_held=false; break;
		case 8: state->module_retained=false; break;
		case 9: state->reset_pending=false; break;
		case 10: state->attached=3; break;
		case 11: state->powered=3; break;
		case 12: state->power_put_pending=true; break;
		case 13: state->primary_error=-ETIMEDOUT; break;
		case 14: state->cleanup_error=-EIO; break;
		case 15: state->dart=NULL; break;
		case 16: mock.dart.lease.running=false; break;
		case 17: mock.dart.device=NULL; break;
		case 18: host->msi_allocation.endpoint=&mock.msi_endpoint; break;
		case 19: host->msi_allocation.vector=320; break;
		case 20: host->msi_allocation.default_irq=19; break;
		case 21: host->msi_config.phase=N71_MSI_CONFIG_ACTIVE; break;
		case 22: host->brcmfmac.error=-EIO; break;
		case 23: host->config.error=-EACCES; break;
		case 24: host->msi_config.error=-ETIMEDOUT; break;
		default: host->io_error=-ENOLINK; break;
		}
		assert(cleanup_ops.set("driver-prepare",NULL)==error);
		assert(cleanup_ops.set("driver-publish",NULL)==error);
		assert(!mock.runtime.prepares && !mock.runtime.publishes && mock.refs==1 && !active_lock);
		assert(!mock.puts && !mock.resets && !mock.consumer_calls && !mock.dart_releases && mock.scans==1);
		if (index>=22) assert(state->primary_error==(index==22 ? -EIO : index==23 ? -EACCES : index==24 ? -ETIMEDOUT : -ENOLINK));
		*state=saved_state; session=state; *host=saved_host; mock.dart=saved_dart; mock.bridge.bus=bus;
		driver_runtime=scan_hold=msi_parent=iommu_parent=mock.live=true;
		runtime_finish(&p); cases++;
	}

	/* Mutations: accept false-zero release, discard a partial owner, or advance provider teardown. */
	for (index=0;index<6;index++) {
		p=setup_runtime(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
		if (index==0) host->brcmfmac.active=true;
		if (index==1) host->driver_root=&mock.msi_endpoint;
		if (index==2) host->driver_endpoint=&mock.msi_endpoint;
		if (index==3) host->driver_pm=true;
		if (index==4) host->driver_root_override=true;
		if (index==5) host->driver_endpoint_override=true;
		mock.runtime.release_pending=true; driver_runtime=false;
		assert(cleanup_ops.set("msi-hold",NULL)==-EBUSY && !session->primary_error && !mock.msi_allocations);
		assert(cleanup_ops.set("msi-release",NULL)==-EBUSY && !mock.msi_release_calls && !mock.allocation_log[0]);
		assert(cleanup_ops.set("driver-release",NULL)==-EBUSY && n71_scan_driver_pending(host));
		assert(cleanup_ops.set("cleanup",NULL)==-EBUSY && n71_scan_driver_pending(host));
		assert(!mock.consumer_calls && !mock.dart_releases && !mock.puts && !mock.resets && mock.refs==1);
		assert(!session->primary_error && session->cleanup_error==-EBUSY);
		mock.runtime.release_pending=false; runtime_finish(&p); cases++;
	}

	/* Mutations: lose an async first cause before disposing host, or overwrite it with release error. */
	p=setup_runtime(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
	assert(cleanup_ops.set("driver-prepare",NULL)==0 && cleanup_ops.set("driver-publish",NULL)==0);
	host->brcmfmac.error=-ENOLINK; host->msi_config.error=-ETIMEDOUT; mock.runtime.release_error=-EIO;
	assert(!session->primary_error);
	assert(cleanup_ops.set("cleanup",NULL)==-EIO && session->primary_error==-ENOLINK && mock.refs==1);
	snprintf(expected,sizeof(expected),"operation_error=%d",-ENOLINK);
	assert(strstr(mock.runtime.log,"action=cleanup error=-5 pending=1") && strstr(mock.runtime.log,expected));
	assert(!mock.consumer_calls && !mock.dart_releases && !mock.puts && !mock.resets);
	mock.runtime.release_error=0; runtime_finish(&p);
	assert(session==NULL); cases++;

	/* Mutations: discard partial prepare/publish errors, hide them after host disposal or retry acquisition. */
	for (index=0;index<2;index++) {
		p=setup_runtime(); assert(n71_probe(&p)==0 && cleanup_ops.set("assign",NULL)==0);
		if (index==0) { mock.runtime.prepare_error=-ENOMEM; mock.runtime.prepare_pending=true; }
		else { assert(cleanup_ops.set("driver-prepare",NULL)==0); mock.runtime.publish_error=-ENOLINK; }
		error=index==0 ? -ENOMEM : -ENOLINK;
		assert(cleanup_ops.set(index==0 ? "driver-prepare" : "driver-publish",NULL)==error);
		assert(session->primary_error==error && n71_scan_driver_pending(host) && mock.refs==1);
		assert(cleanup_ops.set("driver-prepare",NULL)==-EBUSY && mock.runtime.prepares==1);
		assert(cleanup_ops.set("driver-release",NULL)==0 && session->primary_error==error);
		assert(cleanup_ops.set("cleanup",NULL)==0 && !session->scan_bridge && !mock.refs);
		snprintf(expected,sizeof(expected),"requested=1 ready=0 held=0 pending=0 active=0 published=0 root=0 endpoint=0 pm=0 root_override=0 endpoint_override=0 reads=0 operation_error=0 error=%d session_error=0\n",error);
		expect_driver(expected); finish(&p); cases++;
	}
	return cases;
}
#endif /* N71_PCIE_DIAGNOSTIC_RUNTIME_FIXTURE_H */
