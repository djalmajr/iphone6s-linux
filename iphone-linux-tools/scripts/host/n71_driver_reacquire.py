"""Prepare a fresh host cycle from immutable same-boot teardown evidence."""
import hashlib
import json
from pathlib import Path
import re
import device_profile
import n71_driver_firmware_session as firmware
import n71_driver_runtime_session as coordinator
import n71_held_session as held
import n71_session_history as history


def require(condition, message):
    if not condition:
        raise ValueError(message)


class StoppedHistory:
    def __init__(self, source, evidence, text):
        self.source = source
        self.evidence = dict(evidence)
        self.lines = history.kernel_lines(text)
        self.known = frozenset(self.lines)
        self.boot_id = held.one(text, 'N71_BOOT_ID ', r'^N71_BOOT_ID ([0-9a-f-]{36})$')

    def verify_source(self):
        device_profile.protected(self.source.parent, directory=True)
        device_profile.protected(self.source, directory=True)
        for name, expected in self.evidence.items():
            path = self.source / name
            device_profile.protected(path)
            require(path.stat().st_size <= 2 * 1024 * 1024
                and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                'Stopped source bytes changed')

    def verify_live(self, text):
        self.verify_source()
        require(re.findall(r'^N71_BOOT_ID ([0-9a-f-]{36})$', text, re.M) == [self.boot_id],
            'Reacquisition boot identity changed')
        require(history.kernel_lines(text) == self.lines, 'Stopped kernel history changed')

    def fresh(self, text):
        return '\n'.join(line for line in text.splitlines() if line not in self.known) + '\n'


def selection(session, request):
    require(isinstance(request, dict) and set(request) == {'root', 'source', 'identity', 'check'}
        and type(request['check']) is bool, 'Reacquisition request differs')
    root, source = request['root'], request['source']
    require(isinstance(root, Path) and root == root.absolute()
        and isinstance(source, Path) and source.is_absolute() and source.parent == root / 'runtime',
        'Reacquisition source must be private and directly under runtime')
    device_profile.protected(source.parent, directory=True)
    device_profile.protected(source, directory=True)
    require(all(getattr(session, name, None) is True
        for name in ('driver_runtime', 'scan_hold', 'resource_capable', 'iommu_parent'))
        and session.release == firmware.firmware.RELEASE, 'Reacquisition requires explicit held power2 runtime')
    require(all(getattr(session, name, None) is False for name in
        ('reg_attempted', 'activation_attempted', 'pcie_attempted', 'resource_attempted'))
        and getattr(session, 'resource_assignment', None) is None
        and getattr(session, 'history', None) is None
        and session.driver_runtime_journal == [] and session.driver_module_journal == []
        and session.result.get('kernel_release') == session.release
        and not any(name in session.result for name in ('boot_id', firmware.KEY, 'driver_coordinator', 'reacquire_lineage')),
        'Reacquisition requires a fresh session without owners or history')
    firmware.wlan.directory(session.module_directory)
    output = session.output
    require(isinstance(output, Path) and output.is_absolute() and output != source
        and (output.parent == root / 'runtime' or request['check'] and output == root / 'runtime'),
        'Reacquisition output must be new and distinct from source')
    if not request['check']:
        device_profile.protected(output, directory=True)
        require(not any(output.iterdir()), 'Reacquisition output must be empty')


def evidence(source):
    path = source / 'held-state-private.json'
    device_profile.protected(path)
    require(path.stat().st_size <= 2 * 1024 * 1024, 'Stopped state exceeds budget')
    raw = path.read_bytes()
    data = json.loads(raw)
    require(isinstance(data, dict) and isinstance(data.get('checkpoint'), dict)
        and isinstance(data.get('proofs'), dict), 'Stopped source lacks its evidence manifest')
    records = {'held-state-private.json': hashlib.sha256(raw).hexdigest()}
    records[data['checkpoint'].get('name')] = data['checkpoint'].get('sha256')
    records.update({name + '-proof-private.log': digest for name, digest in data['proofs'].items()})
    return records


def prepare(session, request):
    selection(session, request)
    source = request['source']; records = evidence(source)
    initial = dict(session.__dict__)
    try:
        data, text, proofs = held.load_source(session, request['root'], source, request['identity'])
        require(data['result'].get('cleanup_verified') is True and data['result'].get('cleanup_errors') == []
            and set(held.PROOFS).issubset(proofs), 'Stopped source lacks complete provider cleanup')
        require(session.module_directory != initial['module_directory'], 'Reacquisition remote directory must be new')
        value = {'baseline': data['baseline'], 'checkpoint': text, 'proofs': proofs}
        primary = coordinator.validate(session, {'text': text, 'presence': (0, 0, 1), 'context': value})
        summary = data['result'].get('driver_coordinator')
        require(isinstance(summary, dict) and set(summary) == {'action', 'phase', 'primary_error', 'successful'}
            and summary['action'] in ('stop', 'observe') and summary['phase'] == 'stopped'
            and type(summary['primary_error']) is int and summary['primary_error'] == primary
            and summary['successful'] is (primary == 0), 'Stopped summary differs from teardown proof')
        if firmware.KEY in session.result:
            require(firmware.state(session)['path'] == 'restored', 'Previous firmware path was not restored')
            firmware.selected(session)
        stopped = StoppedHistory(source, records, text)
        stopped.verify_source()
        if not request['check']:
            live, presence = held.snapshot(session, 'reacquire-stopped-current')
            require(presence == (0, 0, 1), 'Stopped providers reappeared')
            require(coordinator.validate(session, {'text': live, 'presence': presence, 'context': value}) == primary,
                'Stopped cleanup cause changed')
            stopped.verify_live(live)
            command = firmware.header(session) + firmware.empty_stack() + firmware.path_test('0a')
            process = session.capture('reacquire-empty', command + 'echo N71_REACQUIRE_EMPTY')
            require(process.returncode == 0 and process.stdout.splitlines().count('N71_REACQUIRE_EMPTY') == 1,
                'Stopped firmware path or stack is not empty')
        stopped.verify_source()
        lineage = {'source': str(source), 'state_sha256': records['held-state-private.json'],
            'previous_boot_id': data['result']['boot_id'], 'previous_module_directory': data['module_directory'],
            'previous_primary_error': primary}
    finally:
        session.__dict__.clear()
        session.__dict__.update(initial)
    if not request['check']:
        session.history = stopped
        session.result['reacquire_lineage'] = lineage
    return lineage
