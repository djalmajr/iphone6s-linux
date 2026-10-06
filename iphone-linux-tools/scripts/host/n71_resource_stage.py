"""Retain one PCI assignment with durable intent, proof and same-boot cleanup."""
import re
import n71_resource_result
import n71_scan_held_result

PCIE = '/sys/module/n71_pcie_diagnostic/parameters/'
REG = '/sys/module/n71_wlan_power_diagnostic/parameters/'
PROOF = 'resource-assignment'
INITIAL = dict(ready=1, attempted=0, assigned=0, pending=0, claimed=0, active=0, error=0)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def capable(session):
    selected = getattr(session, 'resource_capable', False)
    require(type(selected) is bool, 'Resource capability must be an exact boolean')
    return selected


def getter(session):
    return 'printf "N71_PCIE_RESOURCES "; cat ' + PCIE + 'resources; ' if capable(session) else ''


def snapshot(session, text, pcie):
    if capable(session) and pcie:
        n71_resource_result.live_status(text)


def fields(session):
    attempted = getattr(session, 'resource_attempted', False)
    require(type(attempted) is bool and (not attempted or capable(session)), 'Resource intent scope differs')
    return {'resource_capable': capable(session), 'resource_attempted': attempted}


def extra_proofs(session):
    return (PROOF,) if capable(session) else ()


def load_source(session, data, proofs):
    require(data.get('resource_capable', False) is capable(session), 'Held resource mode changed')
    attempted = data.get('resource_attempted', False)
    require(type(attempted) is bool and (not attempted or capable(session)), 'Saved resource intent differs')
    require(attempted == (PROOF in proofs), 'Resource intent lacks its complete proof')
    assignment = n71_resource_result.outcome(proofs[PROOF]) if attempted else None
    require(data['result'].get('resource_assignment') == assignment, 'Saved assignment summary differs from proof')
    session.resource_attempted = attempted
    session.resource_assignment = assignment


def resume(session, live, prior):
    if not capable(session):
        return
    if 'N71_PCIE_RESOURCES ' in live or 'N71_PCIE_RESOURCES ' in prior:
        require(n71_resource_result.live_status(live) == n71_resource_result.live_status(prior),
                'Live resource ownership changed')
    fresh = session.history.fresh(live)
    assignment = getattr(session, 'resource_assignment', None)
    require(n71_resource_result.event(fresh) == (assignment['event'] if assignment else None),
            'Live assignment history differs from proof')
    markers = re.findall(r'N71_PCIE_RESOURCE_\S+', fresh)
    allowed = {'N71_PCIE_RESOURCE_RESULT', 'N71_PCIE_RESOURCE_RESTORED', 'N71_PCIE_RESOURCE_WINDOW_RELEASED'}
    require(all(marker in allowed for marker in markers) and (assignment is not None or not markers),
            'Unproved resource operation in checkpoint')
    restored = n71_resource_result.rows(fresh, 'N71_PCIE_RESOURCE_RESTORED ',
                                       r'N71_PCIE_RESOURCE_RESTORED error=(-?\d+) pending=([01])')
    released = n71_resource_result.rows(fresh, 'N71_PCIE_RESOURCE_WINDOW_RELEASED ',
                                       r'N71_PCIE_RESOURCE_WINDOW_RELEASED claimed=0')
    event = assignment['event'] if assignment else None
    require(not restored or (event and event['pending'] == 1
            and all(-4095 <= int(row.group(1)) < 0 and row.group(2) == '1' for row in restored[:-1])
            and (restored[-1].groups() == ('0', '0')
                 or (-4095 <= int(restored[-1].group(1)) < 0 and restored[-1].group(2) == '1'))),
            'Checkpoint extra restore state differs')
    removed = n71_resource_result.rows(fresh, 'N71_PCIE_SCAN_BUS_REMOVED ',
                                      r'N71_PCIE_SCAN_BUS_REMOVED bus-null=1 stop-error=(-?\d+)')
    require(not restored or (len(removed) == 1 and removed[0].start() < restored[0].start()),
            'Checkpoint restore precedes bus removal')
    config = n71_resource_result.rows(fresh, 'N71_PCIE_SCAN_CONFIG_RESTORED ',
                                     r'N71_PCIE_SCAN_CONFIG_RESTORED error=(-?\d+); decode/readback checked')
    require(not released or (len(released) == 1 and event and event['claimed'] == 1
            and config and config[-1].group(1) == '0' and config[-1].start() < released[0].start()
            and (not event['pending'] or (restored and restored[-1].groups() == ('0', '0')
                                         and restored[-1].start() < config[0].start()))),
            'Checkpoint window release precedes proved restoration')
    if 'N71_PCIE_RESOURCES ' in live:
        state = n71_resource_result.live_status(live)
        if removed:
            require(n71_scan_held_result.live_held(live) == 0 and state['assigned'] == 0,
                    'Removed bus cannot retain a live assignment')
            require(not restored or not state['ready'] or state['pending'] == int(restored[-1].group(2)),
                    'Live extra rollback differs from its last restore')
            require(not released or state['claimed'] == 0, 'Released window is still claimed')
        else:
            retained(session, fresh)


def retained(session, text):
    if not capable(session):
        n71_scan_held_result.parse(text)
        return
    assignment = getattr(session, 'resource_assignment', None)
    error = assignment['error'] if assignment else 0
    n71_scan_held_result.parse(text, primary_error=error)
    state = n71_resource_result.live_status(text)
    event = assignment['event'] if assignment else None
    expected = (dict(ready=1, attempted=int(event is not None), assigned=int(error == 0),
                     pending=event['pending'] if event else 0, claimed=event['claimed'] if event else 0,
                     active=0, error=error) if assignment else INITIAL)
    require(state == expected and n71_resource_result.event(text) == event,
            'Retained resource getter and assignment differ')
    require(text.count('N71_PCIE_RESOURCE_') == int(event is not None), 'Resource operation already cleaned up')


def command(session):
    require(capable(session), 'Assignment command requires explicit resource capability')
    require(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', session.result.get('boot_id', '')),
            'Canonical assignment boot required')
    require(session.release == '7.2.0-iphone6s-dart-serdev-power2', 'Assignment requires power2 ABI')
    initial = ' '.join(name + '=' + str(INITIAL[name]) for name in n71_resource_result.FIELDS)
    return ('set -e; test "$(uname -r)" = "' + session.release + '"; '
            'test "$(cat /proc/sys/kernel/random/boot_id)" = "' + session.result['boot_id'] + '"; '
            'test "$(cat ' + PCIE + 'held)" = "held=1"; '
            'test "$(cat ' + REG + 'state)" = "bound=1 active=1 restore_pending=1 original=80"; '
            'test "$(cat ' + REG + 'control)" = "N71_REG_ON_CONTROL_READBACK value=81"; '
            'test "$(cat ' + PCIE + 'resources)" = "' + initial + '"; '
            'if printf "assign\n" > ' + PCIE + 'action; then action_exit=0; else action_exit=$?; fi; '
            'printf "N71_PCIE_RESOURCE_ACTION exit=%s\n" "$action_exit"; ' + getter(session)
            + 'printf "N71_PCIE_HELD "; cat ' + PCIE + 'held; '
            'printf "N71_PCIE_STATUS "; cat ' + PCIE + 'status; dmesg; exit "$action_exit"')


def assign(session, journal, live):
    require(capable(session), 'Assignment requires the resource-capable held profile')
    retained(session, session.history.fresh(live))
    if session.resource_attempted:
        require(PROOF in journal.proofs and session.resource_assignment is not None,
                'Assignment intent without a reusable proof')
        session.result['resource_assignment_reused'] = True
        return
    session.resource_attempted = True
    journal.save()
    process = session.capture('held-assign', command(session))
    assignment = n71_resource_result.outcome(process.stdout)
    require(process.returncode == assignment['action_exit'], 'SSH exit differs from assignment action')
    session.resource_assignment = assignment
    session.result['resource_assignment'] = assignment
    session.result['resource_assignment_reused'] = False
    journal.proof(PROOF, process.stdout)


def cleanup(session, proof):
    require(not session.resource_attempted or session.resource_assignment is not None,
            'Cannot clean up an unproved assignment intent')
    return n71_resource_result.cleanup(proof, session.resource_assignment)


def success(session):
    assignment = getattr(session, 'resource_assignment', None)
    return assignment is None or assignment['error'] == 0
