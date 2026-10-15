"""Validate runtime lifetime and history without emitting a kernel command."""
import re
import n71_driver_module_stage as modules
import n71_driver_runtime_stage as driver
import n71_iommu_result as iommu
import n71_msi_allocation_result as allocation
import n71_resource_result as resources
import n71_session_history as history
import n71_scan_held_result as held
import n71_scan_target_result as caller


def require(condition, message):
    if not condition:
        raise ValueError(message)


def context(session, value):
    import n71_held_session
    import n71_resource_stage
    require(modules.selected(session) is not None, 'Runtime lifetime requires its explicit WCC manifest')
    require(isinstance(value, dict) and set(value) == {'baseline', 'checkpoint', 'proofs'}, 'Runtime proof context differs')
    baseline, proofs, checkpoint = value['baseline'], value['proofs'], value['checkpoint']
    require(isinstance(baseline, list) and all(isinstance(line, str) for line in baseline)
            and history.kernel_lines('\n'.join(baseline)) == baseline
            and sum(len(line) + 1 for line in baseline) <= 2 * 1024 * 1024, 'Runtime baseline differs')
    require(checkpoint is None or (isinstance(checkpoint, str) and len(checkpoint) <= 2 * 1024 * 1024),
            'Runtime checkpoint exceeds budget')
    native = driver.fields(session)['driver_runtime_journal']; wlan = modules.fields(session)['driver_module_journal']
    names = driver.extra_proofs(session, driver.fields(session)) + modules.extra_proofs(session, modules.fields(session))
    require(isinstance(proofs, dict) and set(proofs).issubset(names + n71_held_session.PROOFS + n71_resource_stage.extra_proofs(session))
            and all(isinstance(text, str) and len(text) <= 2 * 1024 * 1024 for text in proofs.values())
            and sum(len(text) for text in proofs.values()) <= 32 * 1024 * 1024, 'Runtime registered proof scope or budget differs')
    for index, entry in enumerate(native):
        name = driver.stage(index, entry['action']); saved = entry['completion']
        require((name in proofs) == (saved is not None), 'Runtime native completion lacks its registered proof')
        if saved is not None:
            proved = driver.completion(session, entry, {'text': proofs[name], 'boot': session.result['boot_id'],
                'mode': saved['mode'], 'shell_exit': saved['shell_exit']})
            require(proved == saved, 'Runtime native summary differs from its proof')
    for index, entry in enumerate(wlan):
        name = modules.modules.tag(modules.operation(session, index, entry)); saved = entry['completion']
        require((name in proofs) == (saved is not None), 'Runtime module completion lacks its registered proof')
        if saved is not None:
            proved = modules.completion(session, entry, {'text': proofs[name], 'index': index,
                'mode': saved['mode'], 'shell_exit': saved['shell_exit']})
            require(proved == saved, 'Runtime module summary differs from its proof')
    return native, wlan


def boot(session, text):
    require(re.findall(r'^N71_BOOT_ID (' + driver.BOOT + ')$', text, re.M) == [session.result.get('boot_id')],
            'Runtime lifetime belongs to another boot')


def refusal(line, observation):
    row = re.fullmatch(r'\[\s*\d+\.\d+\].*N71_PCIE_SCAN_WRITE_REFUSED bus=([01]) devfn=([0-9a-f]{2}) '
        r'where=([0-9a-f]{3}) size=([124]) value=([0-9a-f]{8}) error=(-[1-9][0-9]{0,3})', line)
    if row is None:
        return False
    state = observation['state']; error = int(row[6])
    require(observation['published'] and observation['callback'] and state['error'] < 0
            and -4095 <= error < 0 and str(error) == row[6]
            and error in (state['operation_error'], observation.get('action_error', 0)),
            'Runtime refusal lacks its proved driver cause')
    require(row.group(1, 2) in (('0', '08'), ('1', '00'))
            and int(row[3], 16) % int(row[4]) == 0 and int(row[3], 16) + int(row[4]) <= 4096,
            'Runtime refusal changed its endpoint or config access')
    return True


def segment(lines, observation):
    expected = observation.get('native')
    native = [line for line in lines if driver.result.ACTION_MARKER in line]
    require(len(native) == int(expected is not None), 'Runtime segment includes an unproved native action')
    if expected is not None:
        require(driver.result.action('\n'.join(native), expected['action']) == expected['result'],
                'Runtime segment native result differs')
    reads = r'\[\s*\d+\.\d+\].*N71_REG_ON_READ error=0 value_valid=1 value=' + observation['control']
    accepted = []
    for line in lines:
        require(line.count('N71_') == 1, 'Runtime line includes another operation marker')
        if line in native or re.fullmatch(reads, line):
            continue
        require(refusal(line, observation), 'Runtime history includes an unproved operation')
        accepted.append(line)
    return accepted


def timeline(session, text, value):
    native, wlan = context(session, value); boot(session, text)
    current = history.kernel_lines(text); baseline = value['baseline']
    require(current[:len(baseline)] == baseline, 'Runtime history baseline changed')
    if value['checkpoint'] is not None:
        boot(session, value['checkpoint']); prior = history.kernel_lines(value['checkpoint'])
        require(current[:len(prior)] == prior, 'Runtime checkpoint prefix changed')
    operations = [(len(entry['history']), 'native', index, entry) for index, entry in enumerate(native)]
    operations += [(len(entry['history']), 'wlan', index, entry) for index, entry in enumerate(wlan)]
    operations.sort(key=lambda row: row[0])
    proved = list(baseline); published = False; callback = False; refused = []
    assignment = value['proofs'].get('resource-assignment')
    if assignment is not None:
        require(resources.outcome(assignment) == session.resource_assignment, 'Runtime assignment differs from its proof')
        lines = history.kernel_lines(assignment)
        proved = lines if lines[:len(baseline)] == baseline else baseline + lines
        require(not any(driver.result.ACTION_MARKER in line for line in proved[len(baseline):]),
                'Runtime assignment includes an unproved driver action')
    for start, kind, index, entry in operations:
        require(start >= len(proved) and current[:start] == entry['history']
                and entry['history'][:len(proved)] == proved, 'Runtime intent or effect order changed')
        before = entry['before'] if kind == 'native' else entry['driver_before']
        observation = {'state': before, 'published': published, 'callback': callback, 'control': '81'}
        refused += segment(current[len(proved):start], observation)
        name = driver.stage(index, entry['action']) if kind == 'native' else modules.modules.tag(modules.operation(session, index, entry))
        saved = entry['completion']; proof = value['proofs'].get(name, text)
        after = history.kernel_lines(proof)
        require(after[:start] == entry['history'] and current[:len(after)] == after,
                'Runtime effect proof prefix changed')
        if kind == 'native':
            result = saved or driver.completion(session, entry, {'text': text, 'boot': session.result['boot_id'],
                'mode': 'observed', 'shell_exit': None})
            state = result['state']; action = {'action': entry['action'], 'result': result['native']}
            allowed = (published and callback) or entry['action'] == 'release' and before['published'] == 1
            if entry['action'] == 'publish':
                require(callback, 'Runtime publication lacks its owned WCC stack')
                allowed = result['native']['error'] == 0 and result['native']['published'] == 1
            observation = {'state': state, 'published': published or allowed, 'callback': allowed,
                'control': '81', 'native': action, 'action_error': result['native']['error']}
            refused += segment(after[start:], observation)
            published |= entry['action'] == 'publish' and result['native']['published'] == 1
            if entry['action'] == 'release': callback = False
        else:
            result = saved or modules.completion(session, entry, {'text': text, 'index': index, 'mode': 'observed', 'shell_exit': None})
            observation = {'state': result['driver_after'], 'published': published, 'callback': callback, 'control': '81'}
            refused += segment(after[start:], observation)
            callback = result['after']['states']['brcmfmac_wcc']['present'] == 1
        proved = after
    require(current[:len(proved)] == proved, 'Runtime registered proof prefix changed')
    return refused, proved, published, callback


def verify_history(session, text, value):
    controls = re.findall(r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$', text, re.M)
    require(controls == ['81'] and text.count('N71_REG_ON_CONTROL_READBACK ') == 1, 'Runtime REG_ON readback differs')
    refused, proved, published, callback = timeline(session, text, value)
    current = history.kernel_lines(text)
    state = driver.live(session, text, session.result['boot_id'])
    refused += segment(current[len(proved):], {'state': state, 'published': published, 'callback': callback, 'control': '81'})
    return refused


def release_bridge(session, text, value):
    entries = driver.fields(session)['driver_runtime_journal']
    require(entries and entries[-1]['action'] == 'release' and entries[-1]['completion'] is not None,
            'Runtime bridge lacks a proved release')
    entry = entries[-1]; name = driver.stage(len(entries) - 1, 'release')
    require(isinstance(value, dict) and set(value) == {'before', 'proofs'} and name in value['proofs'],
            'Runtime release bridge lacks its registered proof')
    result = driver.completion(session, entry, {'text': value['proofs'][name], 'boot': session.result['boot_id'],
        'mode': entry['completion']['mode'], 'shell_exit': entry['completion']['shell_exit']})
    require(result == entry['completion'], 'Runtime release bridge summary differs')
    driver.result.resume(session, driver.state_text(entry['before']), driver.state_text(value['before']))
    require(history.kernel_lines(text)[:len(history.kernel_lines(value['proofs'][name]))]
            == history.kernel_lines(value['proofs'][name]), 'Runtime release bridge omitted its proof history')
    driver.result.resume(session, text, driver.state_text(result['state']))


def retained(session, text, value):
    import n71_resource_stage
    native, wlan = context(session, value)
    require(n71_resource_stage.capable(session) and iommu.capable(session)
            and all(entry['completion'] is not None for entry in native + wlan), 'Runtime retained has an unproved owner')
    refused = verify_history(session, text, value)
    modules.resume(session, text, context=value)
    state = driver.live(session, text, session.result['boot_id']); status = caller.live_status(text)
    iommu.snapshot(session, text, True); providers = iommu.live(text); vector = allocation.live(text)
    require(providers['iommu'] == iommu.IOMMU_ACTIVE
            and all(providers['msi'][name] == value for name, value in iommu.MSI_ACTIVE.items() if name not in ('child', 'mappings')),
            'Runtime retained provider ownership changed')
    require(vector is not None and all(vector[name] == 0 for name in ('owner', 'phase', 'vector', 'default_irq', 'software_enabled')),
            'Runtime retained borrowed the manual MSI lease')
    published = any(entry['action'] == 'publish' and entry['completion']['native']['published'] == 1 for entry in native)
    live_modules = modules.modules.live(text, {'manifest': modules.selected(session), 'directory': session.module_directory,
        'boot': session.result['boot_id']})
    if published and state['pending'] and live_modules['states']['brcmfmac_wcc']['present']:
        require(driver.result.association(session, text, {'published': published, 'actual': providers,
            'initial': {'msi': iommu.MSI_ACTIVE, 'iommu': iommu.IOMMU_ACTIVE}}), 'Runtime retained driver lost its association')
    else:
        require(providers['msi']['mappings'] == vector['mappings'] == vector['slots'] == 0
                and providers['msi']['child'] == vector['child'] and vector['child'] in ((0, 1) if published else (0,)),
                'Runtime retained has an unproved vector or domain')
    require(status.get('cleanup_error', 0) == 0, 'Runtime retained cleanup is pending')
    primary = status.get('primary_error', 0)
    assignment = getattr(session, 'resource_assignment', None)
    require(assignment is not None and assignment['assignment_verified'] and 'resource-assignment' in value['proofs'],
            'Runtime retained lacks a completed assignment')
    cause = assignment['error'] or (native[-1]['completion']['state']['error'] if native else 0) \
        or state['operation_error'] or vector['error']
    require(not primary or primary == cause, 'Runtime retained caller lost its first cause')
    require(state['error'] == (primary or state['operation_error'] or vector['error']), 'Runtime retained cause snapshot is incoherent')
    fresh = '\n'.join(line for line in session.history.fresh(text).splitlines() if line not in refused) + '\n'
    n71_resource_stage.verify_readback(session, fresh); held.parse(fresh, primary_error=primary)
    event = assignment['event']; expected = dict(ready=1, attempted=1, assigned=int(primary == 0),
        pending=event['pending'], claimed=event['claimed'], active=0, error=primary)
    require(resources.live_status(text) == expected and resources.event(fresh) == event
            and fresh.count('N71_PCIE_RESOURCE_') == 1, 'Runtime retained resources changed without an intent')
    require(re.findall(r'^bound=1 active=1 restore_pending=1 original=80$', text, re.M) == ['bound=1 active=1 restore_pending=1 original=80']
            and re.findall(r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$', text, re.M) == ['81'],
            'Runtime retained REG_ON ownership changed')
    return {'software_ownership_retained': True, 'irq_delivery_verified': False, 'dma_translation_verified': False,
        'wifi_verified': False, 'battery_or_charging_verified': False, 'primary_error': primary}


def unassigned(session, proofs):
    return (getattr(session, 'resource_attempted', None) is False
        and getattr(session, 'resource_assignment', None) is None
        and session.result.get('resource_assignment') is None and 'resource-assignment' not in proofs)


def removed(session, text, value):
    import n71_resource_stage
    native, wlan = context(session, value); boot(session, text)
    require(all(entry['completion'] is not None for entry in native + wlan), 'Runtime removed has an unproved intent')
    require(not wlan or not any(state['present'] for state in wlan[-1]['completion']['after']['states'].values()),
            'Runtime removed lacks its proved empty module stack')
    current = modules.modules.live(text, {'manifest': modules.selected(session), 'directory': session.module_directory,
        'boot': session.result['boot_id']})
    require(not any(state['present'] for state in current['states'].values()), 'Runtime removed still owns WCC modules')
    proofs = value['proofs']; require('pcie-cleanup' in proofs, 'Runtime removed lacks its registered cleanup proof')
    names = driver.extra_proofs(session, driver.fields(session)) + modules.extra_proofs(session, modules.fields(session))
    if names:
        last = max((proofs[name] for name in names), key=lambda proof: len(history.kernel_lines(proof)))
        _, proved, _, _ = timeline(session, last, dict(value, checkpoint=None))
        require(history.kernel_lines(last) == proved, 'Runtime removed lifetime includes an unproved operation')
    else:
        assignment = getattr(session, 'resource_assignment', None)
        require(not native and not wlan and assignment is not None and 'resource-assignment' in proofs
                and resources.outcome(proofs['resource-assignment']) == assignment
                or (not native and not wlan and unassigned(session, proofs)),
                'Unprepared runtime cleanup lacks its proved assignment')
        baseline = value['baseline']
        for evidence in [text] + list(proofs.values()):
            lines = history.kernel_lines(evidence)
            fresh = lines[len(baseline):] if lines[:len(baseline)] == baseline else lines
            require(not any(driver.result.ACTION_MARKER in line for line in fresh),
                    'Unprepared runtime cleanup includes an unrecorded native action')
    cleanup = n71_resource_stage.cleanup(session, proofs['pcie-cleanup'])
    require(cleanup['resource_cleanup_verified'], 'Runtime removed resource cleanup is incomplete')
    require(re.findall(r'^N71_HELD_PCI_EMPTY=1$', text, re.M) == ['N71_HELD_PCI_EMPTY=1'], 'Runtime removed bus remains present')
    presence = re.findall(r'^N71_HELD_PCIE_PRESENT=([01])$', text, re.M)
    require(len(presence) == 1, 'Runtime removed diagnostic presence differs')
    if presence == ['0']:
        require('pcie-unload' in proofs and proofs['pcie-unload'].splitlines().count('N71_PCIE_UNLOADED') == 1,
                'Runtime removed diagnostic lacks its unload proof')
        require(driver.result.MARKER not in text and driver.result.PARAMETER not in text, 'Unloaded runtime still reports a getter')
    else:
        state = driver.result.live(text, required=True); driver.result.immutable(session, text, state)
        require(not state['ready'] and state['error'] == driver.result.live(proofs['pcie-cleanup'], required=True)['error'],
                'Runtime removed host or first cause changed')
    lines = history.kernel_lines(text)
    anchors = [value['baseline']]
    require(lines[:len(value['baseline'])] == value['baseline'], 'Runtime removed baseline changed')
    if value['checkpoint'] is not None:
        boot(session, value['checkpoint']); anchor = history.kernel_lines(value['checkpoint'])
        require(lines[:len(anchor)] == anchor, 'Runtime removed checkpoint changed')
    for proof in proofs.values():
        known = history.kernel_lines(proof)
        anchor = known if known[:len(value['baseline'])] == value['baseline'] else value['baseline'] + known
        require(lines[:len(anchor)] == anchor, 'Runtime removed omitted a registered proof')
        anchors.append(anchor)
    extra = lines[len(max(anchors, key=len)):]
    control = re.findall(r'^N71_REG_ON_CONTROL_READBACK value=([0-9a-f]{2})$', text, re.M)
    require(len(control) == text.count('N71_REG_ON_CONTROL_READBACK ') <= 1, 'Runtime removed REG_ON getter differs')
    require(not extra or (control and all(re.fullmatch(r'\[\s*\d+\.\d+\].*N71_REG_ON_READ error=0 value_valid=1 value=' + control[0], line)
                for line in extra)), 'Runtime removed includes an unproved operation')
    return cleanup
