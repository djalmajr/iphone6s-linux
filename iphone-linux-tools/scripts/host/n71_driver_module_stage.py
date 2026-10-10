"""Journal WCC ownership and reconcile remote receipts without replaying commands."""
import re
import n71_driver_modules as modules
import n71_driver_runtime_stage as driver
import n71_session_history as history

SSH_EXIT = 'N71_WLAN_SSH_EXIT '


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selected(session):
    records = getattr(session, 'driver_modules', None)
    if records is not None:
        require(driver.result.capable(session), 'WCC module selection requires driver runtime')
        modules.manifest(records)
    return records


def state_text(records, state):
    require(isinstance(state, dict) and set(state) == {'boot', 'directory', 'registered', 'states'}
            and type(state['registered']) is int and state['registered'] in (0, 1)
            and isinstance(state['boot'], str) and re.fullmatch(driver.BOOT, state['boot'])
            and isinstance(state['states'], dict) and set(state['states']) == set(modules.OBSERVED),
            'WCC journal snapshot differs')
    modules.directory(state['directory'])
    text = modules.IDENTITY + 'release=' + modules.RELEASE + ' boot=' + state['boot'] + '\n'
    for record in records:
        text += modules.FILE + f"name={record['name']} sha256={record['sha256']} bytes={record['bytes']}\n"
    for name in modules.OBSERVED:
        value = state['states'][name]
        require(isinstance(value, dict) and set(value) == {'present', 'state', 'refs', 'holders'}
                and type(value['present']) is int and type(value['refs']) is int
                and isinstance(value['holders'], list) and all(isinstance(x, str) for x in value['holders'])
                and isinstance(value['state'], str), 'WCC journal module fields differ')
        text += (modules.MODULE + f"name={name} present={value['present']} state={value['state']} refs={value['refs']} "
                 + 'holders=' + (','.join(value['holders']) or '-') + '\n')
    return text + 'N71_WLAN_REGISTERED=' + str(state['registered']) + '\n'


def snapshot(records, state):
    parsed = modules.live(state_text(records, state), {'manifest': records,
                          'directory': state['directory'], 'boot': state['boot']})
    require(parsed == state, 'WCC journal snapshot is not canonical')


def operation(session, index, entry):
    return {'action': entry['action'], 'name': entry['name'], 'index': index,
            'boot': entry['before']['boot'], 'directory': entry['before']['directory'],
            'release': session.release, 'before': entry['before']}


def driver_continuation(session, observation):
    before, after = observation['before'], observation['after']
    if not before['published'] and after['published']:
        entries = observation.get('native')
        if entries is None:
            entries = driver.ledger(session, driver.fields(session))
        published = [entry for entry in entries if entry['action'] == 'publish' and entry['completion'] is not None]
        require(len(published) == 1, 'WCC ownership changed without proved publication')
        entry = published[0]; lines = observation['history']
        require(lines[:len(entry['history'])] == entry['history'], 'WCC publication history changed')
        require(driver.result.action('\n'.join(lines[len(entry['history']):]), 'publish')
                == entry['completion']['native'], 'WCC publication result differs')
        driver.result.resume(session, driver.state_text(entry['before']), driver.state_text(before))
        before = entry['completion']['state']
    driver.result.resume(session, driver.state_text(after), driver.state_text(before))


def outcome(records, entry, completion):
    require(isinstance(completion, dict) and set(completion) == {'mode', 'shell_exit', 'operation_exit', 'applied', 'after', 'driver_after'}
            and completion['mode'] in ('direct', 'observed') and type(completion['applied']) is bool,
            'WCC module completion differs')
    operation_exit = completion['operation_exit']
    require(operation_exit is None or (type(operation_exit) is int and 0 <= operation_exit <= 255),
            'WCC operation exit is not canonical')
    require((type(completion['shell_exit']) is int and completion['shell_exit'] == operation_exit)
            if completion['mode'] == 'direct' else completion['shell_exit'] is None,
            'WCC transport result was invented')
    require(completion['applied'] == (operation_exit == 0) if operation_exit is not None else completion['applied'],
            'WCC operation result and ownership differ')
    before, after = entry['before'], completion['after']; snapshot(records, after)
    require(before['boot'] == after['boot'] and before['directory'] == after['directory'], 'WCC completion scope changed')
    for name in modules.OBSERVED:
        expected = (int(entry['action'] == 'load') if name == entry['name'] and completion['applied']
                    else before['states'][name]['present'])
        require(after['states'][name]['present'] == expected, 'WCC completion changed another owner')
    require(all(state['state'] == 'live' for state in after['states'].values() if state['present'])
            and after['registered'] == after['states']['brcmfmac']['present'], 'WCC completion is not stable')


def ledger(session, data):
    records = selected(session)
    require(data.get('driver_module_manifest') == records, 'Saved WCC manifest changed')
    entries = data.get('driver_module_journal', [])
    require(isinstance(entries, list) and len(entries) <= 10000 and (records is not None or not entries),
            'WCC ledger scope or budget differs')
    previous = None; unloading = False
    for index, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {'action', 'name', 'before', 'driver_before', 'history', 'completion'},
                'WCC intent schema differs')
        snapshot(records, entry['before'])
        scope = data.get('result', session.result)
        require(entry['before']['boot'] == scope.get('boot_id')
                and entry['before']['directory'] == data.get('module_directory', session.module_directory),
                'WCC intent belongs to another boot or directory')
        require(previous is not None or (entry['action'] == 'load' and entry['name'] == modules.NAMES[0]),
                'WCC ownership must start with an empty stack')
        request = operation(session, index, entry); modules.precondition(records, request)
        require(not unloading or entry['action'] == 'unload', 'WCC loads cannot resume after unloading begins')
        unloading |= entry['action'] == 'unload'
        require(isinstance(entry['history'], list) and all(isinstance(line, str) for line in entry['history'])
                and sum(len(line) + 1 for line in entry['history']) <= 2 * 1024 * 1024
                and history.kernel_lines('\n'.join(entry['history'])) == entry['history'], 'WCC intent history differs')
        require(isinstance(entry['driver_before'], dict) and set(entry['driver_before']) == set(driver.result.FIELDS)
                and all(type(value) is int for value in entry['driver_before'].values()), 'WCC driver intent state differs')
        driver.result.live(driver.state_text(entry['driver_before']), required=True)
        if previous is not None:
            prior = previous['completion']
            require(prior is not None and all(entry['before']['states'][name]['present'] == prior['after']['states'][name]['present']
                    for name in modules.OBSERVED), 'WCC next intent lost a preceding owner')
            native = driver.ledger(session, data) if 'driver_runtime_journal' in data else None
            driver_continuation(session, {'after': entry['driver_before'], 'before': prior['driver_after'],
                                'history': entry['history'], 'native': native})
        completion = entry['completion']
        if completion is None:
            require(index == len(entries) - 1, 'Unproved WCC intent precedes another effect')
        else:
            outcome(records, entry, completion)
            require(isinstance(completion['driver_after'], dict) and set(completion['driver_after']) == set(driver.result.FIELDS)
                    and all(type(value) is int for value in completion['driver_after'].values()), 'WCC driver completion differs')
            driver.result.resume(session, driver.state_text(completion['driver_after']), driver.state_text(entry['driver_before']))
        previous = entry
    return entries


def fields(session):
    data = {'driver_module_manifest': selected(session),
            'driver_module_journal': getattr(session, 'driver_module_journal', [])}
    ledger(session, data)
    return data


def extra_proofs(session, data):
    return tuple(modules.tag(operation(session, index, entry)) for index, entry in enumerate(ledger(session, data)))


def getter(session):
    records = selected(session)
    if records is None:
        return ''
    entries = ledger(session, fields(session))
    receipt = operation(session, len(entries) - 1, entries[-1]) if entries else None
    return modules.getter(records, session.module_directory, receipt)


def resume(session, text, *, context=None):
    records = selected(session)
    if records is None:
        return
    entries = ledger(session, fields(session))
    current = modules.live(text, {'manifest': records, 'directory': session.module_directory, 'boot': session.result['boot_id']})
    require(not entries or entries[-1]['completion'] is not None, 'WCC resume has an unobserved intent')
    before = entries[-1]['completion']['after'] if entries else None
    require(all(value['present'] == (before['states'][name]['present'] if before else 0)
                and (not value['present'] or value['state'] == 'live')
                for name, value in current['states'].items()), 'WCC live ownership changed without an intent')
    native = driver.fields(session)['driver_runtime_journal']
    state = driver.result.live(text, required=False)
    if state is None or not state['ready']:
        import n71_driver_runtime_lifetime
        require(context is not None, 'Removed WCC lifetime requires its proof context')
        n71_driver_runtime_lifetime.removed(session, text, context)
    elif native and native[-1]['action'] == 'release':
        import n71_driver_runtime_lifetime
        require(context is not None and not any(value['present'] for value in current['states'].values()),
                'WCC release bridge still owns modules or lacks context')
        n71_driver_runtime_lifetime.release_bridge(session, text, {
            'before': entries[-1]['completion']['driver_after'] if entries else native[-1]['before'], 'proofs': context['proofs']})
    elif entries:
        driver_continuation(session, {'after': driver.live(session, text, session.result['boot_id']),
                            'before': entries[-1]['completion']['driver_after'], 'history': history.kernel_lines(text)})


def completion(session, entry, observation):
    records = selected(session); text = observation['text']; request = operation(session, observation['index'], entry)
    current = modules.live(text, {'manifest': records, 'directory': request['directory'], 'boot': request['boot']})
    receipt = modules.receipt(text, records, request)
    require(receipt is not None, 'WCC intent lacks its remote receipt')
    current_driver = driver.live(session, text, request['boot'])
    require(history.kernel_lines(text)[:len(entry['history'])] == entry['history'], 'WCC operation history prefix changed')
    applied = current['states'][entry['name']]['present'] != entry['before']['states'][entry['name']]['present']
    result = {'mode': observation['mode'], 'shell_exit': observation['shell_exit'],
              'operation_exit': receipt['operation_exit'], 'applied': applied, 'after': current, 'driver_after': current_driver}
    marker = SSH_EXIT + 'tag=' + modules.tag(request) + ' exit='
    rows = re.findall('^' + re.escape(marker) + r'(0|[1-9][0-9]{0,2})$', text, re.M)
    require((len(rows) == text.count(SSH_EXIT) == 1 and int(rows[0]) == observation['shell_exit'])
            if observation['mode'] == 'direct' else SSH_EXIT not in text, 'WCC proof transport marker differs')
    outcome(records, entry, result)
    driver.result.resume(session, driver.state_text(current_driver), driver.state_text(entry['driver_before']))
    return result


def load_source(session, data, proofs):
    entries = ledger(session, data); previous_history = []
    for index, entry in enumerate(entries):
        require(entry['history'][:len(previous_history)] == previous_history, 'WCC intent omitted its previous proof')
        name = modules.tag(operation(session, index, entry)); saved = entry['completion']
        if name not in proofs:
            require(saved is None, 'Completed WCC operation lacks its registered proof')
            continue
        rows = re.findall('^' + SSH_EXIT + r'tag=\S+ exit=(0|[1-9][0-9]{0,2})$', proofs[name], re.M)
        mode, shell_exit = (saved['mode'], saved['shell_exit']) if saved else (('direct', int(rows[0])) if rows else ('observed', None))
        proved = completion(session, entry, {'text': proofs[name], 'index': index, 'mode': mode, 'shell_exit': shell_exit})
        require(saved is None or saved == proved, 'Saved WCC completion differs from proof')
        entry['completion'] = proved; previous_history = history.kernel_lines(proofs[name])
    session.driver_module_journal = entries


def act(session, journal, request):
    records = selected(session); require(records is not None, 'WCC effects require an explicit manifest')
    entries = ledger(session, fields(session))
    require(not entries or entries[-1]['completion'] is not None, 'Interrupted WCC intent must be observed, never replayed')
    before = modules.live(request['live'], {'manifest': records, 'directory': session.module_directory, 'boot': session.result['boot_id']})
    entry = {'action': request['action'], 'name': request['name'], 'before': before,
             'driver_before': driver.live(session, request['live'], session.result['boot_id']),
             'history': history.kernel_lines(request['live']), 'completion': None}
    native_entries = driver.ledger(session, driver.fields(session))
    require(native_entries and native_entries[-1]['completion'] is not None
            and native_entries[-1]['action'] in ('prepare', 'publish'), 'WCC operation lacks a proved native lifetime')
    native_name = driver.stage(len(native_entries) - 1, native_entries[-1]['action'])
    require(native_name in journal.proofs, 'WCC operation lacks its registered native proof')
    native_history = history.kernel_lines(history.read_private(session.output, native_name + '-proof-private.log'))
    require(entry['history'][:len(native_history)] == native_history, 'WCC operation omitted its native history')
    driver.result.resume(session, driver.state_text(entry['driver_before']),
                         driver.state_text(native_entries[-1]['completion']['state']))
    if request['action'] == 'load':
        state = entry['driver_before']
        require(native_entries[-1]['action'] == 'prepare' and not state['published'] and not state['error']
                and not state['operation_error'] and all(state[name] == 1 for name in driver.result.OWNERS),
                'WCC load requires proved healthy preparation before publication')
    if entries:
        previous = modules.tag(operation(session, len(entries) - 1, entries[-1]))
        require(previous in journal.proofs, 'WCC operation lacks its preceding registered proof')
        known = history.kernel_lines(history.read_private(session.output, previous + '-proof-private.log'))
        require(entry['history'][:len(known)] == known, 'WCC next operation omitted its preceding history')
    pending = operation(session, len(entries), entry)
    command = modules.command(records, pending)
    entries.append(entry); session.driver_module_journal = entries
    ledger(session, fields(session)); journal.save()
    name = modules.tag(pending); process = session.capture(name, command)
    raw = history.read_private(session.output, name + '-private.log')
    receipt = modules.receipt(raw, records, pending)
    require(receipt is not None and receipt['operation_exit'] == process.returncode, 'WCC operation/SSH exit disagree')
    text, _ = request['snapshot'](session, name + '-after')
    text = SSH_EXIT + 'tag=' + name + ' exit=' + str(process.returncode) + '\n' + text
    proved = completion(session, entry, {'text': text, 'index': len(entries) - 1, 'mode': 'direct', 'shell_exit': process.returncode})
    journal.proof(name, text); entry['completion'] = proved; journal.save()
    return proved


def reconcile(session, journal, text):
    entries = ledger(session, fields(session))
    require(entries and entries[-1]['completion'] is None, 'No pending WCC intent to reconcile')
    index = len(entries) - 1; entry = entries[index]
    proved = completion(session, entry, {'text': text, 'index': index, 'mode': 'observed', 'shell_exit': None})
    journal.proof(modules.tag(operation(session, index, entry)), text)
    entry['completion'] = proved; journal.save()
    return proved
