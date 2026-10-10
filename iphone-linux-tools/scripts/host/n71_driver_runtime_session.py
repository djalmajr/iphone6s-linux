"""Start, observe and stop a proved WCC lifetime without rebooting the phone."""
import hashlib
from pathlib import Path
import device_profile
import n71_driver_module_stage as wlan
import n71_driver_runtime_lifetime as lifetime
import n71_driver_runtime_recovery as recovery
import n71_driver_runtime_stage as native
import n71_held_session as held
import n71_iommu_result as iommu
import n71_msi_allocation_result as allocation
import n71_resource_stage as resources
import n71_session_history as history


def require(condition, message):
    if not condition:
        raise ValueError(message)


def context(journal):
    return {'baseline': journal.baseline,
        'checkpoint': history.read_private(journal.session.output, journal.checkpoint['name']) if journal.checkpoint else None,
        'proofs': {name: history.read_private(journal.session.output, name + '-proof-private.log') for name in journal.proofs}}


def validate(session, observation):
    text, presence, value = observation['text'], observation['presence'], observation['context']
    entries, stack = lifetime.context(session, value)
    require(all(entry['completion'] is not None for entry in entries + stack), 'Runtime coordinator has an unproved intent')
    expected = (int(session.pcie_attempted and 'pcie-unload' not in value['proofs']),
        int(session.reg_attempted and 'reg-unload' not in value['proofs']))
    require(presence[:2] == expected, 'Runtime coordinator provider ownership changed')
    if 'pcie-cleanup' in value['proofs']:
        cleanup = lifetime.removed(session, text, value)
        return cleanup.get('cleanup_primary_error', cleanup['assignment_error'])
    require(presence == (1, 1, 0), 'Runtime coordinator lacks its retained host')
    assignment = getattr(session, 'resource_assignment', None)
    if assignment is None:
        require(not entries and not stack and lifetime.unassigned(session, value['proofs']),
            'Unassigned runtime has an assignment intent or native/module owners')
        lifetime.boot(session, text)
        prior = value['checkpoint']; require(isinstance(prior, str), 'Unassigned runtime lacks its acquired checkpoint')
        lifetime.boot(session, prior)
        lines = history.kernel_lines(text); anchor = history.kernel_lines(prior); baseline = value['baseline']
        require(lines[:len(baseline)] == baseline and lines[:len(anchor)] == anchor,
            'Unassigned runtime history or checkpoint changed')
        if lines != anchor:
            held.n71_held_history.verify(text, prior, reg_present=True)
        require(not any(native.result.ACTION_MARKER in line for line in lines[len(baseline):]),
            'Unassigned runtime has an unrecorded native action')
        wlan.resume(session, text, context=value)
        resources.retained(session, session.history.fresh(text)); iommu.retained(session, text)
        state = native.live(session, text, session.result['boot_id']); vector = allocation.live(text)
        require(all(state[name] == 0 for name in native.result.OWNERS
            + ('pending', 'published', 'operation_error', 'reads', 'error', 'session_error'))
            and vector is not None and vector['error'] == 0
            and all(vector[name] == 0 for name in allocation.FIELDS if name not in ('ready', 'held', 'error')),
            'Unassigned runtime has unrecorded native or MSI owners')
        return 0
    require(assignment is not None and 'resource-assignment' in value['proofs'], 'Runtime coordinator lacks assignment')
    if assignment['error'] == 0:
        return lifetime.retained(session, text, value)['primary_error']
    require(not entries and not stack, 'Negative assignment cannot acquire native owners')
    lifetime.verify_history(session, text, value); wlan.resume(session, text, context=value)
    resources.retained(session, session.history.fresh(text)); iommu.retained(session, text)
    state = native.live(session, text, session.result['boot_id'])
    vector = allocation.live(text)
    require(all(state[name] == 0 for name in native.result.OWNERS + ('pending', 'published', 'operation_error', 'reads'))
        and state['error'] == assignment['error'] and vector is not None
        and all(vector[name] == 0 for name in allocation.FIELDS if name not in ('ready', 'held', 'error')),
        'Unprepared negative assignment has unrecorded native or MSI owners')
    return assignment['error']


def observe(session, journal, stage):
    text, presence = held.snapshot(session, stage)
    primary = validate(session, {'text': text, 'presence': presence, 'context': context(journal)})
    return text, presence, primary


def copy_source(session, request, loaded):
    data, _, proofs = loaded
    origin = Path(request['source']).absolute()
    recovered = session.result.get('runtime_recovery_source')
    if recovered is not None and recovered != data['result'].get('runtime_recovery_source'):
        origin = Path(recovered).absolute()
    require(origin.parent == request['root'] / 'runtime' and origin != session.output, 'Runtime proof origin differs')
    device_profile.protected(origin, directory=True)
    require(set(proofs) == set(data['proofs']), 'Runtime registered proof set changed')
    journal = held.Journal(session, request['identity']); journal.baseline = list(data['baseline'])
    records = [(name + '-proof-private.log', digest) for name, digest in data['proofs'].items()]
    records.append((data['checkpoint']['name'], data['checkpoint']['sha256']))
    for name, digest in records:
        path = origin / name; device_profile.protected(path)
        require(path.stat().st_size <= 2 * 1024 * 1024, 'Runtime registered file exceeds budget')
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, 'Runtime registered file changed before copy')
        recovery.write_private(session.output, name, raw)
    journal.proofs = dict(data['proofs']); journal.checkpoint = dict(data['checkpoint']); journal.save()
    return journal


def start(session, journal, live):
    entries = native.fields(session)['driver_runtime_journal']
    require(session.resource_assignment is not None
        and session.resource_assignment['assignment_verified'] and session.resource_assignment['error'] == 0,
        'Runtime start requires a successful assignment')
    require('pcie-cleanup' not in journal.proofs, 'Runtime start cannot reuse a removed host')
    require(not entries or (entries[-1]['action'] in ('prepare', 'publish')
        and entries[-1]['completion']['native']['error'] == 0), 'Runtime start cannot repeat failed or released native actions')
    if entries and entries[-1]['action'] == 'publish':
        require(native.live(session, live, session.result['boot_id'])['published'] == 1, 'Runtime publication changed')
        return
    require(not any(entry['action'] == 'unload' for entry in wlan.fields(session)['driver_module_journal']),
        'Runtime start cannot resume after unloading begins')
    if not entries:
        proved = native.act(session, journal, {'action': 'prepare', 'live': live})
        require(proved['native']['error'] == 0, 'Runtime preparation failed; owners retained')
        live, _, _ = observe(session, journal, 'runtime-after-prepare')
    for name in wlan.modules.NAMES:
        state = wlan.modules.live(live, {'manifest': wlan.selected(session), 'directory': session.module_directory,
            'boot': session.result['boot_id']})
        if not state['states'][name]['present']:
            proved = wlan.act(session, journal, {'action': 'load', 'name': name, 'live': live, 'snapshot': held.snapshot})
            require(proved['applied'], 'Runtime WCC load failed; owners retained')
            live, _, _ = observe(session, journal, 'runtime-after-load-' + name.replace('_', '-'))
    proved = native.act(session, journal, {'action': 'publish', 'live': live})
    require(proved['native']['error'] == 0, 'Runtime publication failed; owners retained')


def stop(session, journal, observation):
    live, presence = observation
    if 'pcie-cleanup' not in journal.proofs:
        for name in reversed(wlan.modules.NAMES):
            state = wlan.modules.live(live, {'manifest': wlan.selected(session), 'directory': session.module_directory,
                'boot': session.result['boot_id']})
            if state['states'][name]['present']:
                proved = wlan.act(session, journal, {'action': 'unload', 'name': name, 'live': live, 'snapshot': held.snapshot})
                require(proved['applied'], 'Runtime WCC unload failed; providers retained')
                live, presence, _ = observe(session, journal, 'runtime-after-unload-' + name.replace('_', '-'))
        entries = native.fields(session)['driver_runtime_journal']
        if entries and not (entries[-1]['action'] == 'release' and entries[-1]['completion']['native']['error'] == 0):
            proved = native.act(session, journal, {'action': 'release', 'live': live})
            require(proved['native']['error'] == 0, 'Runtime native release failed; providers retained')
            live, presence, _ = observe(session, journal, 'runtime-after-release')
    held.release(session, journal, presence, live)


def run(session, request):
    require(isinstance(request, dict) and set(request) == {'action', 'root', 'source', 'identity'}
        and request['action'] in ('start', 'observe', 'stop'), 'Runtime coordinator request differs')
    require(wlan.selected(session) is not None and resources.capable(session) and iommu.capable(session),
        'Runtime coordinator requires explicit WCC/resource/IOMMU selection')
    root = request['root']; require(isinstance(root, Path) and root == root.absolute(), 'Runtime root must be absolute')
    require(session.output.parent == root / 'runtime' and session.output != Path(request['source']).absolute(),
        'Runtime output must be new and distinct from its source')
    device_profile.protected(session.output.parent, directory=True); device_profile.protected(session.output, directory=True)
    loaded = recovery.load(session, dict(request, allowed_proofs=held.PROOFS, loader=held.load_source, snapshot=held.snapshot))
    data, prior, proofs = loaded
    live, presence = held.snapshot(session, 'runtime-current')
    validate(session, {'text': live, 'presence': presence, 'context': {'baseline': data['baseline'], 'checkpoint': prior, 'proofs': proofs}})
    journal = copy_source(session, request, loaded)
    try:
        if request['action'] == 'start': start(session, journal, live)
        elif request['action'] == 'stop': stop(session, journal, (live, presence))
        live, presence = journal.finish()
        primary = validate(session, {'text': live, 'presence': presence, 'context': context(journal)})
        if 'pcie-cleanup' in journal.proofs:
            phase = 'stopped' if presence == (0, 0, 1) else 'cleanup_pending'
        else:
            state = native.live(session, live, session.result['boot_id'])
            phase = 'running' if state['published'] and state['pending'] else 'retained'
        require(request['action'] != 'stop' or phase == 'stopped', 'Runtime stop retained provider ownership')
        summary = {'action': request['action'], 'phase': phase, 'primary_error': primary, 'successful': primary == 0}
        session.result['cleanup_verified'] = phase == 'stopped'
        if 'driver_coordinator_error' in session.result:
            session.result['previous_driver_coordinator_error'] = session.result.pop('driver_coordinator_error')
        session.result['driver_coordinator'] = summary; journal.save()
        return summary
    except (OSError, ValueError) as error:
        session.result['driver_coordinator_error'] = str(error)
        try: journal.finish()
        except (OSError, ValueError) as checkpoint_error: session.result['checkpoint_error'] = str(checkpoint_error)
        journal.save()
        raise
