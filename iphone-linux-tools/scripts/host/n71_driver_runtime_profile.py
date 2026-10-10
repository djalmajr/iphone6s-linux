"""Bind owned module bytes to an explicit runtime Session before any SSH effect."""
import copy
import hashlib
import n71_driver_modules as wlan
import n71_driver_runtime_build as build
import n71_driver_runtime_result as runtime


def require(condition, message):
    if not condition:
        raise ValueError(message)


def blobs(pairs, records):
    require(isinstance(pairs, list) and len(pairs) == len(records), 'Runtime module byte set differs')
    owned = []
    for pair, expected in zip(pairs, records):
        require(isinstance(pair, tuple) and len(pair) == 2 and isinstance(pair[0], dict) and pair[0] == expected
            and all(type(pair[0][key]) is type(expected[key]) for key in expected), 'Runtime module record differs')
        raw = pair[1]
        require(type(raw) is bytes and len(raw) == expected['bytes']
            and hashlib.sha256(raw).hexdigest() == expected['sha256'], 'Runtime module bytes or SHA differ')
        owned.append((copy.deepcopy(expected), raw))
    return owned


def selection(session, root):
    require(all(getattr(session, name, None) is True for name in ('scan_hold', 'resource_capable', 'iommu_parent'))
        and session.release == wlan.RELEASE, 'Runtime Session requires explicit held resource/IOMMU power2 mode')
    pairs = session.modules
    require(isinstance(pairs, list) and len(pairs) == 2 and isinstance(pairs[0], tuple)
        and len(pairs[0]) == 2 and isinstance(pairs[0][0], dict), 'Runtime diagnostic selection is incomplete')
    return build.select(root, {'release': session.release, 'pcie_sha256': pairs[0][0].get('sha256')})


def configure(session, request):
    require(isinstance(request, dict) and set(request) == {'root', 'modules'} and not runtime.capable(session),
        'Runtime Session configuration must be new and explicit')
    selected = selection(session, request['root'])
    diagnostics = blobs(session.modules, selected['diagnostics']); drivers = blobs(request['modules'], selected['drivers'])
    session.modules = diagnostics
    session.driver_runtime = True
    session.driver_module_data = drivers
    session.driver_modules = [record for record, _ in drivers]
    session.driver_runtime_journal = []; session.driver_module_journal = []


def selected(session, root):
    if not runtime.capable(session):
        return
    expected = selection(session, root)
    blobs(session.modules, expected['diagnostics'])
    require(wlan.manifest(session.driver_modules) == expected['drivers'], 'Runtime Session WCC manifest changed')
    blobs(session.driver_module_data, expected['drivers'])


def staged(session):
    if not runtime.capable(session):
        return []
    return blobs(session.driver_module_data, wlan.manifest(session.driver_modules))


def preflight_command():
    return ('set -e; ' + ''.join('test ! -d /sys/module/' + name + '; ' for name in wlan.OBSERVED)
        + 'test ! -d /sys/bus/pci/drivers/brcmfmac; echo N71_RUNTIME_STACK_EMPTY')
