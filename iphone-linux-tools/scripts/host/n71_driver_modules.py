"""Observe and operate the qualified WCC stack without force, unbind or autoload."""
import json
import re
from pathlib import Path
import n71_driver_runtime_stage
import n71_scan_held_result

RELEASE = n71_scan_held_result.RELEASE
BOOT = n71_driver_runtime_stage.BOOT
MODULE_PATHS = ('module-rfkill/rfkill.ko', 'module-cfg80211/cfg80211.ko',
                'module-brcmutil/brcmutil.ko', 'module-brcmfmac/brcmfmac.ko',
                'module-brcmfmac/wcc/brcmfmac-wcc.ko')
NAMES = ('rfkill', 'cfg80211', 'brcmutil', 'brcmfmac', 'brcmfmac_wcc')
FOREIGN = ('rfkill_gpio', 'brcmfmac_bca', 'brcmfmac_cyw')
OBSERVED = NAMES + FOREIGN
DEPENDS = ([], ['rfkill'], [], ['brcmutil', 'cfg80211'], ['brcmfmac'])
IDENTITY = 'N71_WLAN_ID '
MODULE = 'N71_WLAN_MODULE '
FILE = 'N71_WLAN_FILE '
STARTED = 'N71_WLAN_STARTED '
EXIT = 'N71_WLAN_EXIT '


def require(condition, message):
    if not condition:
        raise ValueError(message)


def manifest(records):
    require(isinstance(records, list) and len(records) == len(NAMES), 'Exact WCC module stack required')
    for record, name, depends in zip(records, NAMES, DEPENDS):
        require(isinstance(record, dict) and set(record) == {'name', 'module', 'bytes', 'sha256', 'vermagic', 'depends'}
                and record['name'] == name and record['module'] == name.replace('_', '-') + '.ko'
                and record['depends'] == depends, 'WCC module identity or dependency order differs')
        require(type(record['bytes']) is int and 0 < record['bytes'] <= 2 * 1024 * 1024
                and isinstance(record['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', record['sha256'])
                and record['vermagic'] == RELEASE + ' SMP preempt mod_unload aarch64', 'WCC module bytes/SHA/ABI differ')
    return records


def qualified(root):
    path = Path(root) / 'docs/evidence/n71-brcmfmac-pcie-modules-qualified.json'
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 65536,
            'Qualified PCIe module evidence is unavailable')
    proof = json.loads(path.read_text())
    require(isinstance(proof, dict) and type(proof.get('format')) is int and proof['format'] == 1 and proof.get('qualified') is True
            and proof.get('mac_bytes_elf_and_hash_audit') is True and proof.get('source_and_baseline_preserved') is True
            and proof.get('module_count') == 8 and isinstance(proof.get('modules'), dict) and len(proof['modules']) == 8,
            'PCIe module build/audit is not qualified')
    require(proof.get('variant_config_changes') == {'CONFIG_BRCMFMAC_PCIE': ['n', 'y'],
            'CONFIG_BRCMFMAC_PROTO_MSGBUF': ['n', 'y']}, 'PCIe module variant widened its configuration')
    records = []
    for path, name in zip(MODULE_PATHS, NAMES):
        record = proof['modules'].get(path)
        require(isinstance(record, dict) and all(field in record for field in ('bytes', 'sha256', 'vermagic', 'depends'))
                and record.get('imports_verified') is True
                and (name != 'brcmfmac' or record.get('endpoint_pci_alias_verified') is True),
                'WCC module imports or endpoint alias are unproved')
        records.append({'name': name, 'module': path.rsplit('/', 1)[-1],
                        **{field: record[field] for field in ('bytes', 'sha256', 'vermagic', 'depends')}})
    return manifest(records)


def directory(value):
    require(isinstance(value, str) and re.fullmatch(r'/run/n71-link-[0-9a-f]{24}', value),
            'WCC modules require the exclusive held directory')
    return value


def tag(operation):
    require(type(operation['index']) is int and 0 <= operation['index'] < 10000
            and operation['action'] in ('load', 'unload') and operation['name'] in NAMES,
            'WCC operation identity differs')
    return f"wlan-module-{operation['index']:04d}-{operation['action']}-{operation['name']}"


def receipt_path(operation):
    return directory(operation['directory']) + '/' + tag(operation) + '-receipt-private.log'


def receipt(text, records, operation):
    manifest(records); tag(operation)
    require(isinstance(text, str) and len(text) <= 2 * 1024 * 1024, 'WCC receipt exceeds budget')
    if 'N71_WLAN_RECEIPT_MISSING' in text:
        require(text.splitlines().count('N71_WLAN_RECEIPT_MISSING') == 1 and STARTED not in text and EXIT not in text,
                'Missing WCC receipt includes an operation result')
        return None
    rows = re.findall('^' + STARTED + r'index=(0|[1-9][0-9]{0,3}) action=(load|unload) '
                      r'name=(\w+) boot=(' + BOOT + ') sha256=([0-9a-f]{64})$', text, re.M)
    expected = (str(operation['index']), operation['action'], operation['name'], operation['boot'],
                records[NAMES.index(operation['name'])]['sha256'])
    require(len(rows) == text.count(STARTED) == 1 and rows[0] == expected, 'WCC receipt identity differs')
    exits = re.findall('^' + EXIT + r'index=(0|[1-9][0-9]{0,3}) action=(load|unload) '
                       r'name=(\w+) exit=(0|[1-9][0-9]{0,2})$', text, re.M)
    require(len(exits) == text.count(EXIT) <= 1
            and all(row[:3] == expected[:3] and int(row[3]) <= 255 for row in exits), 'WCC operation exit differs')
    return {'operation_exit': int(exits[0][3]) if exits else None}


def getter(records, target, receipt=None):
    manifest(records); directory(target)
    command = ('LC_ALL=C; export LC_ALL; printf "' + IDENTITY + 'release=%s boot=%s\\n" '
               '"$(uname -r)" "$(cat /proc/sys/kernel/random/boot_id)"; ')
    for record in records:
        path = target + '/' + record['module']
        command += ('wlan_hash=$(sha256sum ' + path + '); wlan_hash=${wlan_hash%% *}; '
                    'printf "' + FILE + 'name=' + record['name'] + ' sha256=%s bytes=%d\\n" '
                    '"$wlan_hash" "$(wc -c < ' + path + ')"; ')
    for name in OBSERVED:
        base = '/sys/module/' + name
        command += ('if test -d ' + base + '; then wlan_holders=; '
                    'for wlan_holder in ' + base + '/holders/*; do '
                    'test -e "$wlan_holder" || continue; wlan_holders="${wlan_holders:+$wlan_holders,}${wlan_holder##*/}"; done; '
                    'printf "' + MODULE + 'name=' + name + ' present=1 state=%s refs=%s holders=%s\\n" '
                    '"$(cat ' + base + '/initstate)" "$(cat ' + base + '/refcnt)" "${wlan_holders:--}"; '
                    'else printf "' + MODULE + 'name=' + name + ' present=0 state=- refs=0 holders=-\\n"; fi; ')
    command += ('if test -d /sys/bus/pci/drivers/brcmfmac; then echo N71_WLAN_REGISTERED=1; '
                'else echo N71_WLAN_REGISTERED=0; fi; ')
    if receipt is not None:
        path = receipt_path(receipt)
        command += ('if test -e ' + path + '; then cat ' + path + '; else echo N71_WLAN_RECEIPT_MISSING; fi; ')
    return command


def live(text, expected):
    require(isinstance(text, str) and len(text) <= 2 * 1024 * 1024, 'WCC observation exceeds budget')
    records = manifest(expected['manifest']); target = directory(expected['directory'])
    identity = re.findall('^' + IDENTITY + r'release=(\S+) boot=(' + BOOT + ')$', text, re.M)
    require(len(identity) == text.count(IDENTITY) == 1 and identity[0] == (RELEASE, expected['boot']),
            'WCC observation belongs to another ABI or boot')
    files = re.findall('^' + FILE + r'name=(\w+) sha256=([0-9a-f]{64}) bytes=([1-9][0-9]{0,9})$', text, re.M)
    require(len(files) == text.count(FILE) == len(records)
            and files == [(record['name'], record['sha256'], str(record['bytes'])) for record in records],
            'WCC staged file identity differs')
    rows = re.findall('^' + MODULE + r'name=(\w+) present=([01]) state=(-|live|coming|going) '
                      r'refs=(0|[1-9][0-9]{0,9}) holders=(-|[a-z0-9_]+(?:,[a-z0-9_]+)*)$', text, re.M)
    require(len(rows) == text.count(MODULE) == len(OBSERVED) and tuple(row[0] for row in rows) == OBSERVED,
            'Complete ordered WCC module inventory required')
    states = {}
    for name, present, state, refs, holders in rows:
        holding = [] if holders == '-' else holders.split(',')
        require(holding == sorted(set(holding)) and all(holder in OBSERVED for holder in holding)
                and 0 <= int(refs) <= 2147483647 and int(refs) >= len(holding), 'WCC references or holders differ')
        require((present == '0' and state == '-' and refs == '0' and not holding)
                or (present == '1' and state != '-'), 'Absent WCC module retains state')
        states[name] = {'present': int(present), 'state': state, 'refs': int(refs), 'holders': holding}
    registered = re.findall(r'^N71_WLAN_REGISTERED=([01])$', text, re.M)
    require(len(registered) == text.count('N71_WLAN_REGISTERED=') == 1, 'Unique PCI driver registration required')
    return {'boot': expected['boot'], 'directory': target, 'registered': int(registered[0]), 'states': states}


def precondition(records, operation):
    manifest(records); tag(operation)
    before = operation['before']; states = before['states']; index = NAMES.index(operation['name'])
    count = index if operation['action'] == 'load' else index + 1
    require(before['boot'] == operation['boot'] and before['directory'] == operation['directory'],
            'WCC operation lost its boot or directory')
    require(all(states[name]['present'] == int(position < count) for position, name in enumerate(NAMES))
            and all(not states[name]['present'] for name in FOREIGN), 'WCC stack order or ownership differs')
    require(all(state['state'] == 'live' for state in states.values() if state['present'])
            and before['registered'] == int(count >= 4), 'WCC stack or PCI driver is not live')
    for name, state in states.items():
        holders = sorted(record['name'] for record in records
                         if states[record['name']]['present'] and name in record['depends'])
        require(state['holders'] == holders, 'WCC dependency holders changed')
    if operation['action'] == 'unload':
        require(states[operation['name']]['refs'] == 0, 'WCC target remains pinned')
        if operation['name'] == 'brcmfmac_wcc':
            require(states['brcmfmac']['refs'] == 1, 'Firmware or another client still pins brcmfmac')


def command(records, operation):
    require(operation['release'] == RELEASE and re.fullmatch(BOOT, operation['boot']), 'WCC operation ABI/boot differs')
    directory(operation['directory']); precondition(records, operation)
    action, name = operation['action'], operation['name']
    target = operation['directory']; receipt = receipt_path(operation)
    command = ('set -e; umask 077; test "$(uname -r)" = "' + RELEASE + '"; '
               'test "$(cat /proc/sys/kernel/random/boot_id)" = "' + operation['boot'] + '"; '
               'test "$(cat ' + n71_driver_runtime_stage.result.PCIE + 'driver_runtime)" = Y; '
               'test "$(cat ' + n71_driver_runtime_stage.result.PCIE + 'held)" = "held=1"; ')
    for record in records:
        path = target + '/' + record['module']
        command += ('test "$(sha256sum ' + path + ')" = "' + record['sha256'] + '  ' + path + '"; '
                    'test "$(wc -c < ' + path + ')" -eq ' + str(record['bytes']) + '; ')
    for current in OBSERVED:
        command += ('test ' + ('' if operation['before']['states'][current]['present'] else '! ') + '-d /sys/module/' + current + '; ')
    if action == 'load':
        command += ('wlan_driver=$(cat ' + n71_driver_runtime_stage.result.PCIE + 'driver_runtime_status); '
                    'case "$wlan_driver" in "requested=1 ready=1 held=1 pending=1 active=1 published=0 root=1 endpoint=1 pm=1 root_override=1 endpoint_override=1 "*) ;; *) exit 1;; esac; '
                    'case "$wlan_driver" in *" operation_error=0 error=0 session_error=0") ;; *) exit 1;; esac; ')
    else:
        command += ('test "$(cat /sys/module/' + name + '/refcnt)" -eq 0; '
                    'test -z "$(ls /sys/module/' + name + '/holders)"; ')
        if name == 'brcmfmac_wcc':
            command += ('test "$(cat /sys/module/brcmfmac/refcnt)" -eq 1; '
                        'test "$(ls /sys/module/brcmfmac/holders)" = brcmfmac_wcc; ')
    command += ('(set -C; printf "' + STARTED + 'index=' + str(operation['index']) + ' action=' + action
                + ' name=' + name + ' boot=' + operation['boot'] + ' sha256=' + records[NAMES.index(name)]['sha256']
                + '\\n" > ' + receipt + '); ')
    effect = ('insmod ' + target + '/' + records[NAMES.index(name)]['module']) if action == 'load' else 'rmmod ' + name
    command += ('if ' + effect + '; then wlan_exit=0; else wlan_exit=$?; fi; '
                'printf "' + EXIT + 'index=' + str(operation['index']) + ' action=' + action + ' name=' + name
                + ' exit=%s\\n" "$wlan_exit" >> ' + receipt + '; '
                + getter(records, target, operation) + 'exit "$wlan_exit"')
    return command
