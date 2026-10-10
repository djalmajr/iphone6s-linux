"""Own firmware data and a reversible loader path in one proved runtime boot."""
import copy
import hashlib
import re
import secrets
import n71_driver_firmware as firmware
import n71_driver_modules as wlan

PARAMETER = '/sys/module/firmware_class/parameters/path'
KEY = 'firmware_package'
BOOT = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def records():
    return [{'path': name, 'bytes': size, 'sha256': digest} for name, size, digest in firmware.CATALOG]


def configure(session, request):
    require(isinstance(request, dict) and set(request) == {'root', 'directory'}
        and getattr(session, 'firmware_data', None) is None, 'Firmware configuration must be new and explicit')
    require(session.driver_runtime is True and session.release == firmware.RELEASE
        and all(getattr(session, key, None) is True for key in ('scan_hold', 'resource_capable', 'iommu_parent')),
        'Firmware configuration requires its selected runtime')
    session.firmware_data = firmware.select(request['root'], {'directory': request['directory'], 'release': session.release})


def applicable(session):
    return getattr(session, 'firmware_data', None) is not None or KEY in session.result


def context(session):
    require(session.driver_runtime is True and session.release == firmware.RELEASE
        and all(getattr(session, key, None) is True for key in ('scan_hold', 'resource_capable', 'iommu_parent')),
        'Firmware effect requires its selected runtime')
    directory = wlan.directory(session.module_directory) + '/firmware'
    boot = session.result.get('boot_id')
    require(isinstance(boot, str) and re.fullmatch(BOOT, boot), 'Firmware effect requires a proved boot')
    return directory, boot


def selected(session):
    pairs = getattr(session, 'firmware_data', None)
    require(isinstance(pairs, list) and len(pairs) == len(records()), 'Exact owned firmware data required')
    for pair, expected in zip(pairs, records()):
        require(isinstance(pair, tuple) and len(pair) == 2 and type(pair[0]) is dict and pair[0] == expected
            and all(type(pair[0][key]) is type(expected[key]) for key in expected)
            and type(pair[1]) is bytes and len(pair[1]) == expected['bytes']
            and hashlib.sha256(pair[1]).hexdigest() == expected['sha256'], 'Pinned firmware bytes changed')
    return pairs


def state(session):
    directory, boot = context(session)
    value = session.result.get(KEY)
    require(isinstance(value, dict) and set(value) == {'format', 'boot_id', 'directory', 'manifest', 'status', 'path'}
        and type(value['format']) is int and value['format'] == 1 and value['boot_id'] == boot
        and value['directory'] == directory and value['manifest'] == records()
        and value['status'] in ('intent', 'ready') and value['path'] in ('idle', 'binding', 'bound', 'restoring', 'restored')
        and (value['status'] == 'ready' or value['path'] in ('idle', 'restored')),
        'Firmware saved ownership differs')
    return value


def header(session):
    directory, boot = context(session)
    parent = directory.rsplit('/', 1)[0]
    return ('set -e; test "$(uname -r)" = "' + session.release + '"; '
        'test "$(cat /proc/sys/kernel/random/boot_id)" = "' + boot + '"; '
        'test -d /run; test ! -L /run; test -d ' + parent + '; test ! -L ' + parent + '; '
        'test "$(stat -c %a:%u ' + parent + ')" = 700:0; '
        'test -f ' + PARAMETER + '; test ! -L ' + PARAMETER + '; '
        'test "$(stat -c %a:%u ' + PARAMETER + ')" = 644:0; ')


def empty_stack():
    return ''.join('test ! -d /sys/module/' + name + '; ' for name in wlan.OBSERVED) + 'test ! -d /sys/bus/pci/drivers/brcmfmac; '


def path_hex():
    return 'od -An -tx1 -v ' + PARAMETER + ' | tr -d " \\n"'


def path_test(hex_value):
    return 'test "$(' + path_hex() + ')" = ' + hex_value + '; '


def directories(session):
    directory = state(session)['directory']; command = ''
    for path in (directory, directory + '/brcm'):
        command += 'test -d ' + path + '; test ! -L ' + path + '; test "$(stat -c %a:%u ' + path + ')" = 700:0; '
    return command


def readback(session):
    value = state(session); directory = value['directory']
    command = header(session) + directories(session)
    command += ('test "$(LC_ALL=C ls -A ' + directory + ')" = "$(printf \'brcm\\nregulatory.db\\nregulatory.db.p7s\')"; '
        'test "$(ls -A ' + directory + '/brcm)" = brcmfmac4350-pcie.bin; ')
    for record in records():
        path = directory + '/' + record['path']
        command += ('test -f ' + path + '; test ! -L ' + path + '; '
            'test "$(stat -c %a:%u:%h ' + path + ')" = 600:0:1; '
            'test "$(wc -c < ' + path + ')" -eq ' + str(record['bytes']) + '; '
            'printf "%s\\n" "' + record['sha256'] + '  ' + path + '" | sha256sum -c -; ')
    return (command + 'printf "N71_FW_PATH "; ' + path_hex() + '; printf "\\n"; '
        'echo N71_FW_DATA_OK ' + value['boot_id'] + ' ' + directory)


def parsed(session, process):
    value = state(session)
    expected = 'N71_FW_DATA_OK ' + value['boot_id'] + ' ' + value['directory']
    require(process.returncode == 0 and isinstance(process.stdout, str) and len(process.stdout) <= 4096
        and process.stdout.splitlines().count(expected) == 1, 'Firmware data readback failed')
    rows = re.findall(r'^N71_FW_PATH ([a-f0-9]+)$', process.stdout, re.M)
    require(len(rows) == process.stdout.count('N71_FW_PATH ') == 1
        and rows[0] in ('0a', value['directory'].encode().hex() + '0a'), 'Firmware path is foreign or malformed')
    return rows[0]


def observe(session, tag):
    return parsed(session, session.capture(tag + '-' + secrets.token_hex(6), readback(session)))


def check_journal(session, journal):
    require(getattr(journal, 'session', None) is session, 'Firmware journal belongs to another session')


def save(session, journal):
    check_journal(session, journal)
    journal.save()


def stage(session):
    if not applicable(session):
        return
    pairs = selected(session); directory, boot = context(session)
    require(KEY not in session.result, 'Firmware transfer intent must not be replayed')
    journal = getattr(session.before_effect, '__self__', None)
    require(getattr(journal, 'session', None) is session, 'Firmware transfer requires its durable journal')
    session.result[KEY] = {'format': 1, 'boot_id': boot, 'directory': directory,
        'manifest': copy.deepcopy(records()), 'status': 'intent', 'path': 'idle'}
    save(session, journal)
    guard = header(session) + empty_stack() + path_test('0a')
    guard += 'test -d /lib; test ! -L /lib; test ! -e /lib/firmware; test ! -L /lib/firmware; '
    process = session.capture('firmware-directory', guard + 'umask 077; mkdir -m 700 ' + directory + '; mkdir -m 700 ' + directory + '/brcm')
    require(process.returncode == 0, 'Exclusive firmware directory was not created')
    for index, (record, raw) in enumerate(pairs):
        command = guard + directories(session) + 'umask 077; set -C; cat > ' + directory + '/' + record['path']
        process = session.capture('firmware-transfer-' + str(index), command, raw)
        require(process.returncode == 0, 'Firmware transfer incomplete; retain intent')
    require(observe(session, 'firmware-staged') == '0a', 'Firmware path changed during staging')
    session.result[KEY]['status'] = 'ready'; save(session, journal)


def verify(session, journal=None):
    if not applicable(session):
        return
    if journal is not None:
        check_journal(session, journal)
    value = state(session)
    require(value['status'] == 'ready', 'Firmware staging is incomplete')
    current = observe(session, 'firmware-current')
    owned = value['directory'].encode().hex() + '0a'
    if value['path'] == 'binding':
        require(current == owned and journal is not None, 'Interrupted firmware binding must be observed, never replayed')
        value['path'] = 'bound'; save(session, journal)
    require(current == (owned if value['path'] == 'bound' else '0a')
        and value['path'] in ('idle', 'bound', 'restored'), 'Firmware path ownership changed')


def bind(session, journal):
    if not applicable(session):
        return
    check_journal(session, journal); verify(session, journal); value = state(session)
    if value['path'] == 'bound':
        return
    require(value['path'] == 'idle', 'Restored firmware cannot be rebound in a stopped session')
    value['path'] = 'binding'; save(session, journal)
    command = header(session) + empty_stack() + path_test('0a')
    command += 'printf %s ' + value['directory'] + ' > ' + PARAMETER + '; ' + readback(session)
    process = session.capture('firmware-bind', command)
    owned = value['directory'].encode().hex() + '0a'
    require(parsed(session, process) == owned,
        'Firmware binding did not complete; retain intent')
    value['path'] = 'bound'; save(session, journal)


def restore(session, journal):
    if not applicable(session):
        return
    check_journal(session, journal); value = state(session)
    command = header(session) + empty_stack()
    process = session.capture('firmware-restore-current', command + 'printf "N71_FW_PATH "; ' + path_hex() + '; printf "\\n"')
    rows = re.findall(r'^N71_FW_PATH ([a-f0-9]+)$', process.stdout, re.M)
    owned = value['directory'].encode().hex() + '0a'
    require(process.returncode == 0 and len(rows) == process.stdout.count('N71_FW_PATH ') == 1
        and rows[0] in ('0a', owned), 'Firmware restoration lacks its empty stack or owned path')
    if rows[0] == '0a':
        value['path'] = 'restored'; save(session, journal)
        return
    require(value['status'] == 'ready' and value['path'] in ('binding', 'bound', 'restoring'),
        'Firmware restoration cannot claim an unowned path')
    value['path'] = 'restoring'; save(session, journal)
    command += path_test(owned) + "printf '\\000' > " + PARAMETER + '; ' + path_test('0a') + 'echo N71_FW_PATH_RESTORED'
    process = session.capture('firmware-restore', command)
    require(process.returncode == 0 and process.stdout.splitlines().count('N71_FW_PATH_RESTORED') == 1,
        'Firmware restoration incomplete; retain ownership')
    value['path'] = 'restored'; save(session, journal)
