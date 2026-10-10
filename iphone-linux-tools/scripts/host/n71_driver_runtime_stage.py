"""Journal native driver actions; an interrupted intent is never replayed."""
import re
import n71_driver_runtime_result as result
import n71_session_history

ACTIONS = ('prepare', 'publish', 'release')
BOOT = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'
EXIT = 'N71_DRIVER_ACTION_EXIT '


def require(condition, message):
    if not condition:
        raise ValueError(message)


def state_text(state):
    return (result.MARKER + ' '.join(f'{name}={state[name]}' for name in result.FIELDS)
            + '\n' + result.PARAMETER + ('Y' if state['requested'] else 'N') + '\n')


def stage(index, action):
    require(type(index) is int and 0 <= index < 10000 and action in ACTIONS, 'Driver proof identity differs')
    return f'driver-runtime-{index:04d}-{action}'


def precondition(action, before, previous):
    require(action in ACTIONS and before['requested'] == before['ready'] == before['held'] == 1,
            'Driver action requires the selected live held host')
    if action == 'prepare':
        require(previous is None and not before['pending'] and not before['published'] and not before['error'],
                'Driver prepare requires a clean first intent')
    elif action == 'publish':
        require(previous is not None and previous['action'] == 'prepare' and previous['completion'] is not None
                and previous['completion']['native']['error'] == 0 and not before['published']
                and not before['error'] and all(before[name] == 1 for name in result.OWNERS),
                'Driver publication requires complete proved preparation')
    else:
        require(previous is not None and previous['completion'] is not None,
                'Driver release requires a proved preceding action')
        require(previous['action'] != 'release' or previous['completion']['native']['error'] < 0,
                'Successful driver release must not be repeated')


def ledger(session, data):
    selected = result.capable(session)
    require(data.get('driver_runtime', False) is selected, 'Saved driver selection changed')
    entries = data.get('driver_runtime_journal', [])
    require(isinstance(entries, list) and len(entries) <= 10000 and (selected or not entries),
            'Driver ledger scope or budget differs')
    previous = None
    for index, entry in enumerate(entries):
        require(isinstance(entry, dict) and set(entry) == {'action', 'before', 'history', 'completion'},
                'Driver intent schema differs')
        before = entry['before']
        require(isinstance(before, dict) and set(before) == set(result.FIELDS)
                and all(type(value) is int for value in before.values()), 'Driver intent state differs')
        result.live(state_text(before), required=True)
        history = entry['history']
        require(isinstance(history, list) and all(isinstance(line, str) for line in history)
                and sum(len(line) + 1 for line in history) <= 2 * 1024 * 1024
                and n71_session_history.kernel_lines('\n'.join(history)) == history,
                'Driver intent history differs')
        precondition(entry['action'], before, previous)
        completion = entry['completion']
        if completion is None:
            require(index == len(entries) - 1, 'Unproved driver intent precedes another effect')
        else:
            require(isinstance(completion, dict) and set(completion) == {'mode', 'shell_exit', 'native', 'state'}
                    and completion['mode'] in ('direct', 'observed'), 'Driver completion schema differs')
            require((type(completion['shell_exit']) is int and 0 <= completion['shell_exit'] <= 255)
                    if completion['mode'] == 'direct' else completion['shell_exit'] is None,
                    'Driver completion invented a shell exit')
            for values, names in ((completion['state'], result.FIELDS), (completion['native'], result.ACTION_FIELDS)):
                require(isinstance(values, dict) and set(values) == set(names)
                        and all(type(value) is int for value in values.values()), 'Driver completion state differs')
            result.live(state_text(completion['state']), required=True)
            native_text = result.ACTION_MARKER + 'action=' + entry['action'] + ' ' + ' '.join(
                f'{name}={completion["native"][name]}' for name in result.ACTION_FIELDS) + result.SUFFIX
            result.action(native_text, entry['action'])
        if previous is not None:
            result.resume(session, state_text(before), state_text(previous['completion']['state']))
        previous = entry
    return entries


def fields(session):
    data = {'driver_runtime': result.capable(session),
            'driver_runtime_journal': getattr(session, 'driver_runtime_journal', [])}
    ledger(session, data)
    return data


def extra_proofs(session, data):
    return tuple(stage(index, entry['action']) for index, entry in enumerate(ledger(session, data)))


def live(session, text, boot):
    require(re.fullmatch(BOOT, boot or '') and re.findall(r'^N71_BOOT_ID (' + BOOT + ')$', text, re.M) == [boot],
            'Driver proof belongs to another boot')
    state = result.live(text, required=True)
    result.immutable(session, text, state)
    require(state['ready'] == state['held'] == 1, 'Driver proof lost its held host')
    return state


def completion(session, entry, observation):
    text = observation['text']
    state = live(session, text, observation['boot'])
    history = n71_session_history.kernel_lines(text)
    before = entry['history']
    require(history[:len(before)] == before, 'Driver action history prefix changed')
    native = result.action('\n'.join(history[len(before):]), entry['action'])
    require(all(native[name] == state[name] for name in ('pending', 'published') + result.OWNERS),
            'Driver native result and getter owners disagree')
    require(state['reads'] >= entry['before']['reads'], 'Driver action counter moved backwards')
    for old, new in ((entry['before']['operation_error'], state['operation_error']),
                     (entry['before']['error'], state['error']), (native['operation_error'], state['operation_error'])):
        require(old == 0 or old == new, 'Driver action discarded an existing first cause')
    mode = observation['mode']
    require(mode in ('direct', 'observed'), 'Driver proof mode differs')
    if mode == 'direct':
        rows = re.findall('^' + EXIT + 'action=' + entry['action'] + r' exit=([0-9]{1,3})$', text, re.M)
        require(len(rows) == text.count(EXIT) == 1 and rows[0] == str(int(rows[0]))
                and int(rows[0]) == observation['shell_exit'] and 0 <= int(rows[0]) <= 255
                and (int(rows[0]) == 0) == (native['error'] == 0), 'Driver native/shell/SSH exit disagree')
    else:
        require(observation['shell_exit'] is None and EXIT not in text, 'Observed proof cannot claim a shell exit')
    return {'mode': mode, 'shell_exit': observation['shell_exit'], 'native': native, 'state': state}


def load_source(session, data, proofs):
    entries = ledger(session, data)
    previous_history = []
    for index, entry in enumerate(entries):
        require(entry['history'][:len(previous_history)] == previous_history,
                'Driver intent omitted a preceding action proof')
        name = stage(index, entry['action'])
        if name not in proofs:
            require(entry['completion'] is None, 'Completed driver action lacks its proof')
            continue
        saved = entry['completion']
        if saved is None:
            rows = re.findall(r'^' + EXIT + r'action=\w+ exit=([0-9]{1,3})$', proofs[name], re.M)
            require(len(rows) == int(EXIT in proofs[name]), 'Interrupted driver proof has an incomplete shell result')
            mode, shell_exit = ('direct', int(rows[0])) if rows else ('observed', None)
        else:
            mode, shell_exit = saved['mode'], saved['shell_exit']
        proved = completion(session, entry, {'text': proofs[name], 'boot': data['result']['boot_id'],
                                            'mode': mode, 'shell_exit': shell_exit})
        require(saved is None or saved == proved, 'Saved driver result differs from its proof')
        entry['completion'] = proved
        previous_history = n71_session_history.kernel_lines(proofs[name])
    session.driver_runtime_journal = entries


def command(session, action):
    require(result.capable(session) and action in ACTIONS and re.fullmatch(BOOT, session.result.get('boot_id', ''))
            and session.release == '7.2.0-iphone6s-dart-serdev-power2', 'Driver action selection/ABI/boot differs')
    return ('set -e; test "$(uname -r)" = "' + session.release + '"; '
            'test "$(cat /proc/sys/kernel/random/boot_id)" = "' + session.result['boot_id'] + '"; '
            'test "$(cat ' + result.PCIE + 'driver_runtime)" = Y; '
            'test "$(cat ' + result.PCIE + 'held)" = "held=1"; '
            'if printf "driver-' + action + '\\n" > ' + result.PCIE + 'action; '
            'then action_exit=0; else action_exit=$?; fi; '
            'printf "' + EXIT + 'action=' + action + ' exit=%s\\n" "$action_exit"; '
            'printf "N71_BOOT_ID "; cat /proc/sys/kernel/random/boot_id; '
            + result.getter() + 'dmesg; exit "$action_exit"')


def act(session, journal, request):
    require(result.capable(session), 'Driver action requires explicit selection')
    entries = ledger(session, fields(session))
    require(not entries or entries[-1]['completion'] is not None, 'Interrupted intent must be reconciled, never replayed')
    before = live(session, request['live'], session.result['boot_id'])
    previous = entries[-1] if entries else None
    precondition(request['action'], before, previous)
    if previous:
        result.resume(session, state_text(before), state_text(previous['completion']['state']))
        name = stage(len(entries) - 1, previous['action'])
        require(name in journal.proofs, 'Driver next effect lacks its preceding proof')
        proved_history = n71_session_history.kernel_lines(n71_session_history.read_private(
            session.output, name + '-proof-private.log'))
        require(n71_session_history.kernel_lines(request['live'])[:len(proved_history)] == proved_history,
                'Driver next effect omitted its preceding history')
    entry = {'action': request['action'], 'before': before,
             'history': n71_session_history.kernel_lines(request['live']), 'completion': None}
    entries.append(entry)
    session.driver_runtime_journal = entries
    journal.save()
    name = stage(len(entries) - 1, entry['action'])
    process = session.capture(name, command(session, entry['action']))
    text = n71_session_history.read_private(session.output, name + '-private.log')
    proved = completion(session, entry, {'text': text, 'boot': session.result['boot_id'],
                                        'mode': 'direct', 'shell_exit': process.returncode})
    journal.proof(name, text)
    entry['completion'] = proved
    journal.save()
    return proved


def reconcile(session, journal, text):
    entries = ledger(session, fields(session))
    require(entries and entries[-1]['completion'] is None, 'No interrupted driver intent to reconcile')
    entry = entries[-1]
    proved = completion(session, entry, {'text': text, 'boot': session.result['boot_id'],
                                        'mode': 'observed', 'shell_exit': None})
    journal.proof(stage(len(entries) - 1, entry['action']), text)
    entry['completion'] = proved
    journal.save()
    return proved
