/* SPDX-License-Identifier: GPL-2.0-only */
/* Reuse probe I/O coverage and inject failures in the Kernel API backends. */
struct device_node;
struct generic_pm_domain;
static int provider_failure, foreign_provider;
static unsigned int cleanup_count, delete_count;
static int test_provider_add(struct device_node *, struct generic_pm_domain *);
static int test_domain_remove(struct generic_pm_domain *);
static void test_provider_del(struct device_node *);

#define of_genpd_add_provider_simple reference_provider_add
#define pm_genpd_remove reference_domain_remove
#define of_genpd_del_provider reference_provider_del
#define main reference_probe_main
#include "n71_pmgr_probe.c"
#undef main

static int test_provider_add(struct device_node *selected, struct generic_pm_domain *domain)
{
	assert(selected == &node && domain == &allocated.genpd && genpd_count == 1);
	if (provider_failure) return provider_failure;
	return reference_provider_add(selected, domain);
}

static int test_domain_remove(struct generic_pm_domain *domain)
{
	int error;
	assert(domain == &allocated.genpd && genpd_count == 1 && provider_count == 0);
	cleanup_count++;
	error = reference_domain_remove(domain);
	if (!error) genpd_count = 0;
	return error;
}

static void test_provider_del(struct device_node *selected)
{
	delete_count++;
	if (provider_count) provider_count--;
	else foreign_provider = 0;
	reference_provider_del(selected);
}

int main(void)
{
	struct platform_device device = {{&node}};
	const int errors[] = {-ENOMEM, -EIO, -EINVAL, -EEXIST, -EPROBE_DEFER};
	unsigned int ei, minimum, on, active, foreign, cases = 3138;
	assert(reference_probe_main() == 0);

	/* Kills skipped/duplicated/wrong-scope cleanup and deletion of another provider. */
	for (ei = 0; ei < 5; ei++)
	for (minimum = 0; minimum < 3; minimum++)
	for (on = 0; on < 2; on++)
	for (active = 0; active < 2; active++)
	for (foreign = 0; foreign < 2; foreign++) {
		u32 seed = active ? 0xa05503f0U : 0xa0550340U, expected = seed;
		min_kind = minimum; always_on = on;
		prepare(seed, 0, 0, 0);
		provider_failure = errors[ei]; foreign_provider = foreign;
		cleanup_count = delete_count = 0;
		if (minimum == 1) expected = (expected & ~0xf0300U) | 0x40000;
		if (on && !active) expected = (expected & ~0x100003ffU) | 0x100000ffU;
		if (active || on) expected = (expected & ~0x300U) | 0x10000000U;
		assert(apple_pmgr_ps_probe(&device) == provider_failure);
		assert(!genpd_count && !provider_count && !reset_count);
		assert(cleanup_count == 1 && delete_count == 0 && foreign_provider == (int)foreign);
		/* Cleanup removes registrations; successful earlier hardware writes remain. */
		assert(map.word == expected);
		cases++;
	}
	printf("N71_PMGR_PROVIDER_FAILURE_OK cases=%u\n", cases);
	return 0;
}
