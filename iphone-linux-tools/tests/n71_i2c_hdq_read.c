/* SPDX-License-Identifier: GPL-2.0-only */
/* Real headers; register effects are fixtures, never SN2400 or gauge proof. */
#define main controller_baseline_main
#include "n71_i2c_controller.c"
#undef main

static struct n71_i2c_controller hdq_controller;
static struct n71_i2c_power_state hdq_power;
static struct n71_i2c_controller_request hdq_ownership;
static unsigned int commands, rx_reads, acknowledgements, poll_reads;
static u32 rx_value, completion_error;
static bool never_complete, keep_busy, status_all_ones, ack_stuck, reset_stuck;
static bool foreign_completion, busy_after_poll;

static u32 hdq_ioread32(void *address)
{
	if (address==memory+0x04) {
		assert(hdq_controller.transfer_pending && commands==4 && !rx_reads);
		rx_reads++;
		if (!(rx_value & ~0xffU)) registers[1]&=~(1U<<19);
		return rx_value;
	}
	if (address==memory+0x14 && commands==4) {
		u32 observed;

		poll_reads++;
		if (status_all_ones) return ~0U;
		observed=ioread32(address);
		if (busy_after_poll && poll_reads==2) registers[1]|=1U<<28;
		return observed;
	}
	return ioread32(address);
}

static void hdq_iowrite32(u32 value, void *address)
{
	assert(hdq_controller.transfer_pending);
	if (address==memory+0x00) {
		const u32 expected[]={0x1ea,0x1d,0x1eb,0x601};
		assert(mapped && claimed && clock_handle.enables==2 && clock_handle.protects==1);
		assert(commands<4 && value==expected[commands]);
		commands++;
		if (commands==4) {
			registers[1]=0x00010100;
			if (!never_complete) registers[1]|=(1U<<27)|(1U<<19)|completion_error;
			if (keep_busy) registers[1]|=1U<<28;
			if (foreign_completion) registers[1]|=1U<<5;
		}
		return;
	}
	if (address==memory+0x14) {
		assert(hdq_controller.status_acknowledged && value && !(value & ~0x0ae00040U));
		acknowledgements++;
		if (!ack_stuck) registers[1]&=~value;
		return;
	}
	assert(address==memory+0x1c && value==0x70f && !(registers[1] & 0x11000000U));
	iowrite32(value,address);
	if (!reset_stuck) {
		registers[1]&=~(1U<<19);
		registers[1]|=1U<<16;
	}
}

#define ioread32 hdq_ioread32
#define iowrite32 hdq_iowrite32
#include "n71-i2c-hdq-read.h"
#undef ioread32
#undef iowrite32

static struct n71_i2c_hdq_read_request hdq_request;
static struct n71_i2c_hdq_read_state hdq_state;

static void begin(bool completion_baseline)
{
	reset_fixture();
	hdq_controller=(struct n71_i2c_controller){0};
	hdq_state=(struct n71_i2c_hdq_read_state){0};
	hdq_power=(struct n71_i2c_power_state){.active=true,.attached=true,.usage_held=true,.cleanup_pending=true};
	hdq_ownership=(struct n71_i2c_controller_request){.consumer=&consumer,.pin_context=&consumer,.power=&hdq_power,.verify_pins=verify_pins};
	hdq_request=(struct n71_i2c_hdq_read_request){.controller=&hdq_controller,.ownership=&hdq_ownership};
	commands=rx_reads=acknowledgements=poll_reads=0;
	rx_value=0x20; completion_error=0;
	never_complete=keep_busy=status_all_ones=ack_stuck=reset_stuck=foreign_completion=busy_after_poll=false;
	if (!completion_baseline) registers[1]&=~(1U<<27);
	assert(n71_i2c_controller_acquire(&hdq_ownership,&hdq_controller)==0);
}

static void finish(void)
{
	assert(!hdq_state.cleanup_pending && !hdq_state.controller && !hdq_state.cleanup_error);
	assert(!hdq_controller.transfer_pending);
	assert(n71_i2c_controller_release(&hdq_ownership,&hdq_controller)==0);
	assert_clean(&hdq_controller);
}

static void retained(void)
{
	assert(hdq_state.cleanup_pending && hdq_state.controller==&hdq_controller && hdq_state.cleanup_error);
	assert(hdq_controller.transfer_pending && mapped && claimed && clock_handle.enables==2);
	assert(n71_i2c_controller_release(&hdq_ownership,&hdq_controller)==-EBUSY && !restores);
}

int main(void)
{
	u32 output;
	unsigned int cases=0;
	/* Mutation captured: missing fixed address/register/count/STOP or RX-byte validation. */
	for (unsigned int i=0;i<4;i++) {
		begin(i!=3); rx_value=i==0 ? 0 : i==1 ? 0xff : 0x20; output=0x1234;
		assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==0);
		assert(output==rx_value && commands==4 && rx_reads==1 && acknowledgements==(i==3 ? 1U : 2U));
		assert(registers[1]==0x00010100 && hdq_controller.saved[N71_I2C_SMSTA]==(i==3 ? 0x00010100U : 0x08010100U));
		finish(); cases++;
	}
	/* Mutation captured: bypassed ownership, clock, scope, baseline or fresh pin check. */
	for (unsigned int i=0;i<15;i++) {
		begin(true); output=0x1234;
		int expected=-EINVAL;
		if (i==0) hdq_power.usage_held=false;
		if (i==1) hdq_power.active=false;
		if (i==2) hdq_controller.clock_enabled=false;
		if (i==3) hdq_controller.clock_protected=false;
		if (i==4) hdq_controller.claimed=false;
		if (i==5) { clock_rate=25000000; expected=-ERANGE; }
		if (i==6) { pin_fail_from=4; expected=-EACCES; }
		if (i==7) { registers[0]=6; expected=-EUCLEAN; }
		if (i==8) { registers[3]=1; expected=-EUCLEAN; }
		if (i==9) { registers[2]=1; expected=-EUCLEAN; }
		if (i==10) { registers[4]=0x80f; expected=-EUCLEAN; }
		if (i==11) { registers[1]|=1U<<5; expected=-EUCLEAN; }
		if (i==12) { registers[1]|=1U<<19; expected=-EBUSY; }
		if (i==13) { registers[1]|=1U<<28; expected=-EBUSY; }
		if (i==14) { registers[1]&=~(1U<<27); expected=-EBUSY; }
		assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==expected);
		assert(output==0x1234 && !commands && !acknowledgements && !hdq_state.cleanup_pending);
		hdq_power.usage_held=hdq_power.active=true;
		hdq_controller.clock_enabled=hdq_controller.clock_protected=hdq_controller.claimed=true;
		clock_rate=24000000; pin_fail_from=0;
		registers[0]=2; registers[1]=0x08010100; registers[2]=registers[3]=0; registers[4]=0x70f;
		finish(); cases++;
	}
	/* Mutation captured: dropped error decoding, recovery/reset, RX validation or primary error. */
	for (unsigned int i=0;i<10;i++) {
		begin(true); output=0x1234;
		int expected=-EIO;
		if (i==0) { completion_error=1U<<21; expected=-ENXIO; }
		if (i==1) { completion_error=1U<<22; expected=-EBUSY; }
		if (i==2) { completion_error=1U<<23; expected=-ETIME; }
		if (i==3) completion_error=1U<<6;
		if (i==4) completion_error=1U<<25;
		if (i==5) { rx_value=0x100; expected=-ENODATA; }
		if (i==6) { rx_value=0x200; expected=-EUCLEAN; }
		if (i==7) { rx_value=~0U; expected=-ENODEV; }
		if (i==8) { never_complete=true; expected=-ETIMEDOUT; }
		if (i==9) { completion_error=(1U<<23)|(1U<<21); expected=-ETIME; }
		assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==expected && output==0x1234);
		assert(!hdq_state.cleanup_pending && (i==8 ? delays==100 && !rx_reads : resets==2));
		finish(); cases++;
	}
	/* Mutation captured: discarded cleanup obligation, early output commit or premature controller release. */
	for (unsigned int i=0;i<7;i++) {
		begin(true); output=0x1234;
		int expected=-EACCES;
		if (i==0) pin_fail_from=5;
		if (i==1) { pin_fail_from=5; completion_error=1U<<21; expected=-ENXIO; }
		if (i==2) { status_all_ones=true; expected=-ENODEV; }
		if (i==3) { ack_stuck=true; expected=-EUCLEAN; }
		if (i==4) { foreign_completion=true; expected=-EUCLEAN; }
		if (i==5) { never_complete=keep_busy=true; expected=-ETIMEDOUT; }
		if (i==6) { rx_value=0x100; reset_stuck=true; expected=-ENODATA; }
		assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==expected && output==0x1234);
		retained();
		assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==(pin_fail_from ? -EACCES : -EBUSY));
		pin_fail_from=0; status_all_ones=ack_stuck=reset_stuck=false;
		registers[1]=0x00010100;
		assert(n71_i2c_hdq_read_cleanup(&hdq_request,&hdq_state)==0);
		assert(n71_i2c_hdq_read_cleanup(&hdq_request,&hdq_state)==0);
		finish(); cases++;
	}
	/* Mutation captured: resetting a bus that became busy after the idle poll. */
	begin(true); rx_value=0x100; busy_after_poll=true; output=0x1234;
	assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==-ENODATA && output==0x1234);
	retained(); assert(resets==1);
	busy_after_poll=false; registers[1]=0x00010100;
	assert(n71_i2c_hdq_read_cleanup(&hdq_request,&hdq_state)==0); finish(); cases++;
	/* Mutation captured: treating consumed XEN as a reason to reboot before another read. */
	begin(true); output=0x1234;
	assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==0 && output==0x20);
	commands=rx_reads=acknowledgements=poll_reads=0; rx_value=0x06;
	assert(n71_i2c_read_hdq_control(&hdq_request,&hdq_state,&output)==0 && output==0x06);
	assert(commands==4 && rx_reads==1 && acknowledgements==1 && mapped && claimed);
	finish(); cases++;
	printf("N71_I2C_HDQ_READ_OK cases=%u\n",cases);
	return 0;
}
