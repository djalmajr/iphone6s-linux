"""Prepare one qualified I2C trace with independent cleanup before WLAN."""
import os
import re
import n71_dma_observation as dma
import n71_pmd_observer_build as observers
import n71_pmd_runtime_build as pmd

CLEAN = 'ready=1 active=0 attached=0 cleanup_pending=0 usage_held=0 module_retained=0 cleanup_error=0'
CONFIGURATION = 'pins_pending=0 pins_selected=0 pins_error=0 controller_pending=0 controller_error=0 controller_claimed=0 transfer_pending=0 transfer_error=0'
MODULE = 'n71-i2c-power-diagnostic.ko'


def script(boot, record):
    dma.identity(boot)
    dma.require(record.get('path') == 'sources/phone/kernel/' + MODULE
        and type(record.get('bytes')) is int and record['bytes'] == 52904
        and isinstance(record.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', record['sha256']),
        'I2C observer module identity differs')
    return f'''set -eu
test "$(id -u)" = 0
test "$(uname -r)" = {dma.RELEASE}
test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}
test ! -d /sys/module/n71_i2c_power_diagnostic
test ! -d /sys/module/n71_pcie_diagnostic
test ! -d /sys/module/n71_wlan_power_diagnostic
module=/tmp/n71-i2c-trace-{boot}/n71-i2c-power-diagnostic.ko
test -f "$module"; test ! -L "$module"
size=$(wc -c < "$module"); test "$size" -eq {record['bytes']}
printf '%s  %s\\n' {record['sha256']} "$module" | sha256sum -c -
printf 'N71_I2C_TRACE_BEGIN boot=%s release=%s\\n' {boot} {dma.RELEASE}
report() {{ dmesg | grep -E 'N71_I2C_(RESET_TRACE|HDQ_CONTROL|HDQ_TRACE|CONFIGURATION_STAGE|POWER_ACTION|POWER_READY|CONFIGURE|CONTROLLER)' || true; }}
trap report EXIT
insmod "$module" run=1
base=/sys/module/n71_i2c_power_diagnostic/parameters
is_clean() {{
    test "$(cat "$base/status")" = '{CLEAN}' &&
    test "$(cat "$base/configuration_status")" = '{CONFIGURATION}'
}}
for action in inspect configure read-hdq-control; do
    test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}
    primary=0
    printf '%s\\n' "$action" > "$base/action" || primary=$?
    printf 'HDQ_ACTION action=%s exit=%s\\n' "$action" "$primary"
    cat "$base/status"; cat "$base/configuration_status"
    if ! is_clean; then printf 'cleanup\\n' > "$base/action" || true; fi
    cat "$base/status"; cat "$base/configuration_status"
    if ! is_clean; then
        printf 'HDQ_RETAINED_OWNERSHIP; no forced unload\\n'
        exit 1
    fi
    if test "$primary" -ne 0; then break; fi
done
rmmod n71_i2c_power_diagnostic
test ! -d /sys/module/n71_i2c_power_diagnostic
test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}
printf 'N71_I2C_TRACE_DONE boot=%s cleanup=verified\\n' {boot}
'''


def prepare(root, boot):
    dma.require(os.environ.get(observers.ENV) == observers.VARIANT, 'Explicit observer variant required for I2C trace')
    _, modules, _ = pmd.snapshot(root, release=pmd.RELEASE)
    record = modules['n71_i2c_power_diagnostic']
    return {'command': script(boot, record), 'sha256': record['sha256'], 'bytes': record['bytes'],
            'directory': '/tmp/n71-i2c-trace-' + boot, 'module': MODULE}
