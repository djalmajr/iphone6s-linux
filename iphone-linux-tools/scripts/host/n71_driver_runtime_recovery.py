"""Recover a driver intent by fresh observation, preserving the interrupted source."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import device_profile
import n71_driver_runtime_stage as stage
import n71_iommu_result
import n71_resource_stage
import n71_session_history as history
import n71_driver_module_stage


def require(condition, message):
    if not condition:
        raise ValueError(message)


def private_record(directory, record):
    require(isinstance(record, dict) and set(record) == {'name', 'sha256'}
            and isinstance(record['name'], str)
            and re.fullmatch(r'held-checkpoint-[0-9a-f]{12}-private\.log', record['name']),
            'Runtime checkpoint selection differs')
    text = history.read_private(directory, record['name'])
    require(hashlib.sha256((directory / record['name']).read_bytes()).hexdigest() == record['sha256'],
            'Runtime checkpoint integrity differs')
    return text


def validate_source(session, request):
    directory = Path(request['source']).absolute()
    require(directory.parent == request['root'] / 'runtime', 'Runtime source must be directly under runtime')
    device_profile.protected(directory.parent, directory=True)
    device_profile.protected(directory, directory=True)
    data = json.loads(history.read_private(directory, 'held-state-private.json'))
    require(type(data.get('format')) is int and data['format'] == 1
            and data.get('identity') == request['identity'], 'Runtime profile identity differs')
    require(isinstance(data.get('module_directory'), str)
            and re.fullmatch(r'/run/n71-link-[0-9a-f]{24}', data['module_directory']), 'Runtime directory differs')
    result = data.get('result')
    require(isinstance(result, dict) and result.get('kernel_release') == session.release
            and isinstance(result.get('boot_id'), str) and re.fullmatch(stage.BOOT, result['boot_id']),
            'Runtime source ABI or boot differs')
    require(all(type(data.get(name)) is bool for name in ('reg_attempted', 'activation_attempted', 'pcie_attempted')),
            'Runtime source attempts differ')
    require(data.get('iommu_parent', False) is n71_iommu_result.capable(session)
            and data.get('resource_capable', False) is n71_resource_stage.capable(session),
            'Runtime source capabilities differ')
    baseline = data.get('baseline')
    require(isinstance(baseline, list) and all(isinstance(line, str) for line in baseline)
            and history.kernel_lines('\n'.join(baseline)) == baseline, 'Runtime baseline differs')
    entries = stage.ledger(session, data)
    driver_names = stage.extra_proofs(session, data)
    module_names = n71_driver_module_stage.extra_proofs(session, data)
    hashes = data.get('proofs')
    require(isinstance(hashes, dict) and set(hashes).issubset(tuple(request['allowed_proofs'])
            + n71_resource_stage.extra_proofs(session) + driver_names + module_names),
            'Runtime proof scope differs')
    proofs = {}
    for name, expected in hashes.items():
        text = history.read_private(directory, name + '-proof-private.log')
        require(hashlib.sha256((directory / (name + '-proof-private.log')).read_bytes()).hexdigest() == expected,
                'Runtime registered proof integrity differs')
        proofs[name] = text
    checkpoint = private_record(directory, data['checkpoint']) if data.get('checkpoint') is not None else None
    if checkpoint is not None:
        require(re.findall(r'^N71_BOOT_ID (' + stage.BOOT + ')$', checkpoint, re.M) == [result['boot_id']],
                'Runtime source checkpoint boot differs')
    return directory, data, entries, proofs, checkpoint


def continuation(text, request):
    current = history.kernel_lines(text)
    module_entries = n71_driver_module_stage.ledger(request['session'], request['data'])
    anchors = [request['data']['baseline']] + [entry['history'] for entry in request['entries'] + module_entries]
    driver_names = stage.extra_proofs(request['session'], request['data']) + n71_driver_module_stage.extra_proofs(request['session'], request['data'])
    for name, proof in request['proofs'].items():
        lines = history.kernel_lines(proof)
        anchors.append(lines if name in driver_names else request['data']['baseline'] + lines)
    proved = max(anchors, key=len)
    if request['checkpoint'] is not None:
        anchors.append(history.kernel_lines(request['checkpoint']))
    require(all(current[:len(anchor)] == anchor for anchor in anchors), 'Runtime recovery history prefix changed')
    pending = request['entries'][-1]['completion'] is None
    anchor = request['entries'][-1]['history'] if pending else proved
    module_pending = bool(module_entries and module_entries[-1]['completion'] is None)
    require(not (pending and module_pending), 'Runtime has two interrupted effects')
    if module_pending:
        anchor = module_entries[-1]['history']
    extra = current[len(anchor):]
    values = re.findall(r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$', text, re.M)
    require(len(values) == text.count('N71_REG_ON_CONTROL_READBACK ') == 1, 'Runtime REG_ON readback differs')
    readback = r'\[\s*\d+\.\d+\] N71_REG_ON_READ error=0 value_valid=1 value=' + values[0]
    action = request['entries'][-1]['action']
    native = [line for line in extra if stage.result.ACTION_MARKER + 'action=' + action + ' ' in line]
    require(len(native) == int(pending) and all(line in native or re.fullmatch(readback, line) for line in extra),
            'Runtime recovery includes an unproved operation')


def write_private(directory, name, body):
    with (directory / name).open('xb') as stream:
        os.chmod(directory / name, 0o600)
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def load(session, request):
    require(stage.result.capable(session), 'Runtime recovery requires explicit selection')
    directory, data, entries, proofs, prior = validate_source(session, request)
    if not entries:
        return request['loader'](session, request['root'], directory, request['identity'])
    n71_resource_stage.load_source(session, data, proofs)
    stage.load_source(session, data, proofs)
    n71_driver_module_stage.load_source(session, data, proofs)
    module_entries = n71_driver_module_stage.ledger(session, data)
    if prior is not None and all(entry['completion'] is not None for entry in entries + module_entries):
        known = history.kernel_lines(prior)
        if all(history.kernel_lines(proof) == known[:len(history.kernel_lines(proof))]
               for name, proof in proofs.items() if name in stage.extra_proofs(session, data)
               + n71_driver_module_stage.extra_proofs(session, data)):
            session.module_directory = data['module_directory']; session.result = dict(data['result'])
            n71_driver_module_stage.resume(session, prior)
            return request['loader'](session, request['root'], directory, request['identity'])
    session.module_directory = data['module_directory']
    session.result = dict(data['result'])
    live, presence = request['snapshot'](session, 'held-runtime-recovery-live')
    require(presence == (1, 1, 0), 'Runtime recovery requires its retained modules and bus')
    require(re.findall(r'^N71_BOOT_ID (' + stage.BOOT + ')$', live, re.M) == [session.result['boot_id']],
            'Runtime recovery belongs to another boot')
    continuation(live, {'session': session, 'data': data, 'entries': entries, 'proofs': proofs, 'checkpoint': prior})
    pending = entries[-1]['completion'] is None; observed = set()
    if pending:
        entries[-1]['completion'] = stage.completion(session, entries[-1], {
            'text': live, 'boot': session.result['boot_id'], 'mode': 'observed', 'shell_exit': None})
        name = stage.stage(len(entries) - 1, entries[-1]['action'])
        proofs[name] = live
        data['proofs'][name] = hashlib.sha256(live.encode()).hexdigest()
        observed.add(name)
    else:
        stage.result.resume(session, live, stage.state_text(entries[-1]['completion']['state']))
    module_pending = bool(module_entries and module_entries[-1]['completion'] is None)
    if module_pending:
        index = len(module_entries) - 1; entry = module_entries[-1]
        entry['completion'] = n71_driver_module_stage.completion(session, entry, {
            'text': live, 'index': index, 'mode': 'observed', 'shell_exit': None})
        name = n71_driver_module_stage.modules.tag(n71_driver_module_stage.operation(session, index, entry))
        proofs[name] = live; data['proofs'][name] = hashlib.sha256(live.encode()).hexdigest(); observed.add(name)
    n71_driver_module_stage.resume(session, live)
    fork = request['root'] / 'runtime' / ('n71-driver-recovered-' + secrets.token_hex(12))
    fork.mkdir(mode=0o700)
    for name, proof in proofs.items():
        body = proof.encode() if name in observed \
            else (directory / (name + '-proof-private.log')).read_bytes()
        write_private(fork, name + '-proof-private.log', body)
    name = 'held-checkpoint-' + secrets.token_hex(6) + '-private.log'
    write_private(fork, name, live.encode())
    data['checkpoint'] = {'name': name, 'sha256': hashlib.sha256(live.encode()).hexdigest()}
    write_private(fork, 'held-state-private.json', (json.dumps(data) + '\n').encode())
    loaded = request['loader'](session, request['root'], fork, request['identity'])
    session.result['runtime_recovery_source'] = str(fork)
    session.result['driver_intent_reconciled'] = pending
    session.result['driver_module_intent_reconciled'] = module_pending
    return loaded
