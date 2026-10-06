"""Persist a qualified held session and release its owners in the same boot."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import device_profile
import n71_scan_held_result
import n71_scan_target_result
import n71_session_history
import n71_resource_stage
import n71_held_history

REG = '/sys/module/n71_wlan_power_diagnostic/parameters/'
PCIE = '/sys/module/n71_pcie_diagnostic/parameters/'
MODULES = ('n71-pcie-diagnostic.ko', 'n71-wlan-power-diagnostic.ko')
TRUE_PARAMETERS = ('run', 'enumerate', 'config_inventory', 'host_scan', 'scan_pme_disable', 'scan_hold')
FALSE_PARAMETERS = ('bar_sizing', 'chip_id', 'dart_observe', 'dart_cycle')
PROOFS = ('pcie-cleanup', 'pcie-unload', 'restore', 'reg-unload')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(profile_path, profile, modules):
    device_profile.protected(profile_path)
    require([record['module'] for record, _ in modules] == list(MODULES), 'Held module set differs')
    return {'deployment_sha256': hashlib.sha256(profile_path.read_bytes()).hexdigest(),
            'payload_sha256': profile['sha256'], 'initramfs_sha256': profile['initramfs_sha256'],
            'modules': {record['module']: record['sha256'] for record, _ in modules}}


def one(text, marker, pattern):
    rows = re.findall(pattern, text, re.M)
    require(len(rows) == text.count(marker) == 1, 'Unique complete ' + marker + ' required')
    return rows[0]


def snapshot_command(session):
    directory = session.module_directory
    require(re.fullmatch(r'/run/n71-link-[0-9a-f]{24}', directory), 'Exclusive held module directory required')
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', session.result.get('boot_id', '')),
            'Canonical held boot identity required')
    command = ('set -e; test "$(uname -r)" = "' + session.release + '"; '
               'printf "N71_BOOT_ID "; cat /proc/sys/kernel/random/boot_id; '
               'printf "N71_PCIE_CMDLINE "; cat /proc/cmdline; '
               'dmesg | grep -F "PCIe ASPM is disabled" >/dev/null; '
               'test ! -e /sys/bus/platform/drivers/n71-pcie-diagnostic/bind; '
               'test ! -e /sys/bus/platform/drivers/n71-pcie-diagnostic/unbind; '
               'test ! -e /sys/bus/i2c/drivers/n71-wlan-power-diagnostic/bind; '
               'test ! -e /sys/bus/i2c/drivers/n71-wlan-power-diagnostic/unbind; ')
    for record, _ in session.modules:
        command += 'sha256sum ' + directory + '/' + record['module'] + '; '
    command += ('if [ -d /sys/module/n71_pcie_diagnostic ]; then echo N71_HELD_PCIE_PRESENT=1; '
                'printf "N71_PCIE_HELD "; cat ' + PCIE + 'held; '
                'printf "N71_PCIE_STATUS "; cat ' + PCIE + 'status; ')
    for name in TRUE_PARAMETERS + FALSE_PARAMETERS:
        command += 'printf "N71_HELD_PARAM ' + name + '="; cat ' + PCIE + name + '; '
    command += n71_resource_stage.getter(session)
    command += ('else echo N71_HELD_PCIE_PRESENT=0; fi; '
                'if [ -d /sys/module/n71_wlan_power_diagnostic ]; then echo N71_HELD_REG_PRESENT=1; '
                'cat ' + REG + 'state; cat ' + REG + 'control; '
                'else echo N71_HELD_REG_PRESENT=0; fi; '
                'test -d /sys/bus/pci/devices; '
                'if [ -z "$(ls /sys/bus/pci/devices)" ]; then echo N71_HELD_PCI_EMPTY=1; '
                'else echo N71_HELD_PCI_EMPTY=0; fi; dmesg')
    return command


def snapshot(session, stage):
    process = session.capture(stage, snapshot_command(session))
    require(process.returncode == 0, 'Live held identity/owners unavailable')
    raw = n71_session_history.read_private(session.output, stage + '-private.log')
    boot = one(raw, 'N71_BOOT_ID ', r'^N71_BOOT_ID ([0-9a-f-]{36})$')
    require(boot == session.result['boot_id'], 'Held boot identity changed')
    cmdline = one(raw, 'N71_PCIE_CMDLINE ', r'^N71_PCIE_CMDLINE (.*)$')
    require([arg for arg in cmdline.split() if arg.startswith('pcie_aspm=')] == ['pcie_aspm=off'],
            'Held ASPM selection changed')
    for record, _ in session.modules:
        target = session.module_directory + '/' + record['module']
        require(re.findall(r'^([0-9a-f]{64})  ' + re.escape(target) + r'$', raw, re.M) == [record['sha256']],
                'Held staged module hash changed')
    pcie = int(one(raw, 'N71_HELD_PCIE_PRESENT=', r'^N71_HELD_PCIE_PRESENT=([01])$'))
    reg = int(one(raw, 'N71_HELD_REG_PRESENT=', r'^N71_HELD_REG_PRESENT=([01])$'))
    empty = int(one(raw, 'N71_HELD_PCI_EMPTY=', r'^N71_HELD_PCI_EMPTY=([01])$'))
    if pcie:
        for name in TRUE_PARAMETERS + FALSE_PARAMETERS:
            value = one(raw, 'N71_HELD_PARAM ' + name + '=', '^N71_HELD_PARAM ' + name + r'=([YN])$')
            require(value == ('Y' if name in TRUE_PARAMETERS else 'N'), 'Held immutable parameter changed')
        n71_scan_held_result.live_held(raw)
        n71_scan_target_result.live_status(raw)
    n71_resource_stage.snapshot(session, raw, pcie)
    if reg:
        one(raw, 'bound=', r'^(bound=1 active=[01] restore_pending=[01] original=[0-9a-f]{2})$')
        one(raw, 'N71_REG_ON_CONTROL_READBACK ', r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$')
    return raw, (pcie, reg, empty)


class Baseline:
    def __init__(self, lines):
        require(isinstance(lines, list) and all(isinstance(line, str) for line in lines), 'Invalid held baseline')
        self.known = frozenset(lines)

    def fresh(self, text):
        return '\n'.join(line for line in text.splitlines() if line not in self.known) + '\n'


class Journal:
    def __init__(self, session, selected_identity):
        self.session = session
        self.path = session.output / 'held-state-private.json'
        self.selected_identity = selected_identity
        self.proofs = {}
        self.baseline = []
        self.checkpoint = None
        with self.path.open('x') as stream:
            stream.write('{}\n')
        self.path.chmod(0o600)
        self.save()

    def save(self):
        session = self.session
        state = {'format': 1, 'identity': self.selected_identity,
                 'module_directory': session.module_directory, 'result': session.result,
                 'reg_attempted': session.reg_attempted, 'activation_attempted': session.activation_attempted,
                 'pcie_attempted': session.pcie_attempted, 'baseline': self.baseline,
                 'proofs': self.proofs, 'checkpoint': self.checkpoint,
                 **n71_resource_stage.fields(session)}
        temporary = self.path.with_name('.held-state-' + secrets.token_hex(12))
        try:
            with temporary.open('x') as stream:
                os.chmod(temporary, 0o600)
                json.dump(state, stream)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def proof(self, stage, text):
        path = self.session.output / (stage + '-proof-private.log')
        with path.open('x') as stream:
            stream.write(text)
        path.chmod(0o600)
        self.proofs[stage] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save()

    def finish(self):
        stage = 'held-checkpoint-' + secrets.token_hex(6)
        text, presence = snapshot(self.session, stage)
        self.checkpoint = {'name': stage + '-private.log',
                           'sha256': hashlib.sha256((self.session.output / (stage + '-private.log')).read_bytes()).hexdigest()}
        self.save()
        return text, presence


def load_source(session, root, directory, selected_identity):
    directory = Path(directory).absolute()
    require(directory.parent == root / 'runtime', 'Held source must be directly under runtime')
    device_profile.protected(directory.parent, directory=True)
    device_profile.protected(directory, directory=True)
    data = json.loads(n71_session_history.read_private(directory, 'held-state-private.json'))
    require(type(data.get('format')) is int and data.get('format') == 1
            and data.get('identity') == selected_identity, 'Held profile or module identity differs')
    require(isinstance(data.get('module_directory'), str)
            and re.fullmatch(r'/run/n71-link-[0-9a-f]{24}', data['module_directory']),
            'Held remote directory differs')
    result = data.get('result')
    require(isinstance(result, dict) and result.get('kernel_release') == session.release
            and isinstance(result.get('boot_id'), str)
            and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', result['boot_id']),
            'Held result ABI or boot identity differs')
    require(all(type(data.get(name)) is bool for name in ('reg_attempted', 'activation_attempted', 'pcie_attempted')),
            'Held attempt state differs')
    record = data.get('checkpoint')
    require(isinstance(record, dict) and set(record) == {'name', 'sha256'}
            and isinstance(record['name'], str)
            and re.fullmatch(r'held-checkpoint-[0-9a-f]{12}-private\.log', record['name']),
            'Held checkpoint selection differs')
    checkpoint = directory / record['name']
    text = n71_session_history.read_private(directory, checkpoint.name)
    require(hashlib.sha256(checkpoint.read_bytes()).hexdigest() == record['sha256'],
            'Held checkpoint integrity differs')
    require(one(text, 'N71_BOOT_ID ', r'^N71_BOOT_ID ([0-9a-f-]{36})$') == result['boot_id'],
            'Held checkpoint boot differs')
    baseline = Baseline(data.get('baseline'))
    require(n71_session_history.kernel_lines(text)[:len(data['baseline'])] == data['baseline'], 'Held baseline differs')
    proofs = data.get('proofs')
    require(isinstance(proofs, dict) and set(proofs).issubset(PROOFS + n71_resource_stage.extra_proofs(session)), 'Held cleanup proof set differs')
    verified = {}
    for stage, expected in proofs.items():
        path = directory / (stage + '-proof-private.log')
        proof = n71_session_history.read_private(directory, path.name)
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, 'Held cleanup proof integrity differs')
        require(n71_session_history.kernel_lines(proof) ==
                [line for line in n71_session_history.kernel_lines(text) if line not in baseline.known]
                [:len(n71_session_history.kernel_lines(proof))], 'Held cleanup history differs')
        verified[stage] = proof
    n71_resource_stage.load_source(session, data, verified)
    if 'pcie-unload' in verified:
        require('pcie-cleanup' in verified, 'PCI unload lacks cleanup proof')
        if n71_resource_stage.capable(session):
            n71_resource_stage.cleanup(session, verified['pcie-cleanup'])
        else:
            n71_scan_held_result.cleanup(verified['pcie-cleanup'])
        require(verified['pcie-unload'].splitlines().count('N71_PCIE_UNLOADED') == 1, 'Held PCI unload not proved')
    if 'reg-unload' in verified:
        require('pcie-unload' in verified and 'restore' in verified, 'REG_ON unload precedes PCI cleanup')
        require(verified['reg-unload'].splitlines().count('N71_REG_UNLOADED') == 1
                and 'N71_REG_ON_REMOVE error=0 restore_pending=0' in verified['reg-unload'],
                'Held REG_ON unload not proved')
    session.module_directory = data['module_directory']
    session.result = dict(result, cleanup_verified=False, cleanup_errors=[])
    for name in ('held_error', 'checkpoint_error'):
        if name in session.result:
            session.result['previous_' + name] = session.result.pop(name)
    session.history = baseline
    for name in ('reg_attempted', 'activation_attempted', 'pcie_attempted'):
        setattr(session, name, data[name])
    return data, text, verified


def release(session, journal, presence, live_text):
    pcie, reg, empty = presence
    if session.pcie_attempted and 'pcie-unload' not in journal.proofs:
        require(pcie == 1, 'PCI module absent without verified cleanup/unload')
        fresh = session.history.fresh(live_text)
        if n71_scan_target_result.is_clean(n71_scan_target_result.live_status(fresh)):
            proof = fresh
        else:
            process = session.capture('held-cleanup', 'set -e; '
                                      'test "$(cat /proc/sys/kernel/random/boot_id)" = "' + session.result['boot_id'] + '"; '
                                      'if printf "cleanup\n" > ' + PCIE + 'action; then cleanup_exit=0; else cleanup_exit=$?; fi; '
                                      'printf "N71_PCIE_HELD "; cat ' + PCIE + 'held; '
                                      'printf "N71_PCIE_STATUS "; cat ' + PCIE + 'status; '
                                      + n71_resource_stage.getter(session) + 'dmesg; exit "$cleanup_exit"')
            require(process.returncode == 0, 'Held cleanup pending; retain REG_ON and module')
            proof = process.stdout
        if n71_resource_stage.capable(session):
            cleanup = n71_resource_stage.cleanup(session, proof)
        else:
            cleanup = n71_scan_held_result.cleanup(proof)
        session.result['stop_error'] = cleanup['stop_error']
        if 'pcie-cleanup' not in journal.proofs:
            journal.proof('pcie-cleanup', proof)
        process = session.capture('held-pci-empty', 'set -e; test -d /sys/bus/pci/devices; '
                                  'test -z "$(ls /sys/bus/pci/devices)"; echo N71_PCI_CLEANUP_EMPTY')
        require(process.returncode == 0, 'PCI devices remain; retain owners')
        process = session.capture('held-pcie-unload', 'set -e; rmmod n71_pcie_diagnostic; '
                                  'test ! -d /sys/module/n71_pcie_diagnostic; echo N71_PCIE_UNLOADED; dmesg')
        require(process.returncode == 0 and process.stdout.splitlines().count('N71_PCIE_UNLOADED') == 1,
                'Held PCI unload not proved')
        journal.proof('pcie-unload', process.stdout)
        pcie, empty = 0, 1
    require(pcie == 0 and empty == 1, 'PCI owners remain; retain REG_ON')
    if session.reg_attempted and 'reg-unload' not in journal.proofs:
        require(reg == 1, 'REG_ON module absent without verified restoration/unload')
        process = session.capture('held-restore', 'set -e; '
                                  'test "$(cat /proc/sys/kernel/random/boot_id)" = "' + session.result['boot_id'] + '"; '
                                  + ('printf "0\n" > ' + REG + 'power; '
                                     if session.activation_attempted and 'restore' not in journal.proofs else '')
                                  + 'cat ' + REG + 'state; cat ' + REG + 'control; dmesg')
        require(process.returncode == 0 and 'bound=1 active=0 restore_pending=0' in process.stdout
                and 'N71_REG_ON_CONTROL_READBACK value=80' in process.stdout, 'Held REG_ON restore pending')
        if 'restore' not in journal.proofs:
            journal.proof('restore', process.stdout)
        process = session.capture('held-reg-unload', 'set -e; rmmod n71_wlan_power_diagnostic; '
                                  'test ! -d /sys/module/n71_wlan_power_diagnostic; echo N71_REG_UNLOADED; dmesg')
        require(process.returncode == 0 and process.stdout.splitlines().count('N71_REG_UNLOADED') == 1
                and 'N71_REG_ON_REMOVE error=0 restore_pending=0' in process.stdout, 'Held REG_ON unload not proved')
        journal.proof('reg-unload', process.stdout)
        reg = 0
    require(reg == 0, 'REG_ON owner remains')
    session.result.update(held_verified=False, cleanup_verified=True, cleanup_errors=[])


def run(session, selected_identity, *, root, source=None, assign=False):
    journal = None
    try:
        require(type(assign) is bool and (not assign or (source is not None and n71_resource_stage.capable(session))),
                'Assignment requires an explicit saved resource-capable held session')
        if source:
            data, prior, verified = load_source(session, root, source, selected_identity)
            live, presence = snapshot(session, 'held-resume-live')
            n71_held_history.verify(live, prior, reg_present=presence[1])
            expected = (int(session.pcie_attempted and 'pcie-unload' not in verified),
                        int(session.reg_attempted and 'reg-unload' not in verified))
            require(presence[:2] == expected, 'Held module ownership changed; no cleanup attempted')
            n71_resource_stage.resume(session, live, prior)
            if presence[1]:
                require(one(live, 'bound=', r'^(bound=1 active=[01] restore_pending=[01] original=[0-9a-f]{2})$') ==
                        one(prior, 'bound=', r'^(bound=1 active=[01] restore_pending=[01] original=[0-9a-f]{2})$')
                        and one(live, 'N71_REG_ON_CONTROL_READBACK ', r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$') ==
                        one(prior, 'N71_REG_ON_CONTROL_READBACK ', r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$'),
                        'Held REG_ON ownership changed; no cleanup attempted')
            if presence[0]:
                fresh = session.history.fresh(live)
                require(n71_scan_target_result.live_status(live) == n71_scan_target_result.live_status(prior)
                        and n71_scan_held_result.live_held(live) == n71_scan_held_result.live_held(prior),
                        'Held live PCI ownership changed; no cleanup attempted')
                if 'N71_PCIE_SCAN_HELD ' in fresh:
                    n71_scan_held_result.acquisition(fresh)
                else:
                    require('previous_held_error' in session.result
                            and any(int(value) < 0 for value in re.findall(
                                r'N71_PCIE_(?:LINK|INVENTORY|SCAN)_RESULT error=(-?\d+)', fresh)),
                            'Held acquisition or negative diagnostic proof missing')
            journal = Journal(session, selected_identity)
            journal.baseline = data['baseline']
            for stage, proof in verified.items():
                journal.proof(stage, proof)
            if assign:
                require(presence == (1, 1, 0), 'Assignment requires live held owners')
                n71_resource_stage.assign(session, journal, live)
            else:
                release(session, journal, presence, live)
        else:
            journal = Journal(session, selected_identity)
            session.before_effect = journal.save
            session.experiment()
            preflight = n71_session_history.read_private(session.output, 'preflight-private.log')
            journal.baseline = n71_session_history.kernel_lines(preflight)
            live, presence = snapshot(session, 'held-acquire-live')
            require(presence == (1, 1, 0), 'Held modules and PCI bus not live')
            n71_resource_stage.retained(session, Baseline(journal.baseline).fresh(live))
            require('bound=1 active=1 restore_pending=1 original=80\n' in live
                    and 'N71_REG_ON_CONTROL_READBACK value=81\n' in live, 'Held REG_ON ownership changed')
            session.result['held_verified'] = True
        final, presence = journal.finish()
        require((presence == (0, 0, 1) if source and not assign else presence == (1, 1, 0)), 'Held final ownership differs')
        if not source or assign:
            n71_resource_stage.retained(session, Baseline(journal.baseline).fresh(final))
            require('bound=1 active=1 restore_pending=1 original=80\n' in final
                    and 'N71_REG_ON_CONTROL_READBACK value=81\n' in final, 'Final held REG_ON ownership changed')
    except (ValueError, OSError, KeyError, KeyboardInterrupt) as error:
        session.result['held_error'] = str(error)
        if journal:
            session.result.update(cleanup_verified=False, cleanup_errors=[str(error)])
            if not source and session.reg_attempted and 'boot_id' in session.result:
                try:
                    preflight = n71_session_history.read_private(session.output, 'preflight-private.log')
                    journal.baseline = n71_session_history.kernel_lines(preflight)
                    session.history = Baseline(journal.baseline)
                    live, presence = snapshot(session, 'held-failure-live')
                    release(session, journal, presence, live)
                except (ValueError, OSError, KeyError) as cleanup_error:
                    session.result['cleanup_errors'] = [str(cleanup_error)]
            try:
                journal.finish()
            except (ValueError, OSError, KeyError) as checkpoint_error:
                journal.checkpoint = None
                session.result['checkpoint_error'] = str(checkpoint_error)
            journal.save()
    with (session.output / 'result-private.json').open('x') as stream:
        os.chmod(session.output / 'result-private.json', 0o600)
        json.dump(session.result, stream, indent=2)
        stream.write('\n')
    print('N71_SESSION_RESULT', json.dumps(session.result), flush=True)
    return 0 if 'held_error' not in session.result and session.result.get('stop_error', 0) == 0 and n71_resource_stage.success(session) else 1
