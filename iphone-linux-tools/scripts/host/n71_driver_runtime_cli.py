"""Select a private runtime profile and dispatch explicit same-boot operations."""
import importlib.util
import json
import os
from pathlib import Path
import device_profile
import n71_driver_runtime_compose as files
import n71_driver_runtime_session as coordinator
import n71_held_session as held
import n71_iommu_build as iommu
import n71_driver_firmware_session as firmware

ACTIONS = ('acquire', 'assign', 'start', 'observe', 'stop')
TRUE_FLAGS = ('kernel_initramfs_identities_preserved', 'pcie_driver_runtime', 'pcie_aspm_off', 'pcie_scan_hold',
    'pcie_resource_capable', 'pcie_iommu_parent', 'pcie_scan_link_target', 'pcie_scan_pme_disable',
    'requires_explicit_run', 'requires_explicit_enumerate')
FALSE_FLAGS = ('pcie_scan_pme_noop', 'module_automatic_load', 'default_profile_changed')
RELEASE = '7.2.0-iphone6s-dart-serdev-power2'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def paths(root, request):
    require(isinstance(root, Path) and root == root.absolute(), 'Absolute runtime root required')
    fields = {'action', 'check', 'output', 'profile', 'source'}
    require(isinstance(request, dict) and (set(request) == {'action', 'check', 'output', 'profile', 'source'}
        or set(request) == fields | {'firmware'})
        and type(request['check']) is bool and type(request['action']) is str and request['action'] in ACTIONS,
        'Runtime CLI request differs')
    runtime = root / 'runtime'; device_profile.protected(runtime, directory=True)
    package = request.get('firmware')
    if package is not None:
        require(isinstance(package, Path) and package.is_absolute() and package.parent == runtime,
            'Firmware package must be private and directly under runtime')
        device_profile.protected(package, directory=True)
    profile, source, output = request['profile'], request['source'], request['output']
    require(isinstance(profile, Path) and profile.is_absolute() and profile.name == 'deployment.json'
        and profile.parent.parent == runtime, 'Runtime profile must be private and directly under runtime')
    device_profile.protected(profile.parent, directory=True); device_profile.protected(profile)
    require((source is None) == (request['action'] == 'acquire'), 'Only acquire omits a saved runtime source')
    if source is not None:
        require(isinstance(source, Path) and source.is_absolute() and source.parent == runtime,
            'Runtime source must be private and directly under runtime')
        device_profile.protected(source, directory=True)
    require(request['check'] or output is not None, 'Explicit effects require a new runtime output')
    if output is not None:
        require(isinstance(output, Path) and output.is_absolute() and output.parent == runtime
            and output != source and output != profile.parent and not output.exists() and not output.is_symlink(),
            'Runtime output must be new and distinct from profile/source')


def selection(root, profile):
    path = profile.parent / 'provenance.json'; device_profile.protected(path)
    require(path.stat().st_size <= 8192, 'Runtime provenance exceeds budget')
    metadata = json.loads(path.read_text())
    require(isinstance(metadata, dict) and type(metadata.get('format')) is int and metadata['format'] == 1
        and all(metadata.get(name) is True for name in TRUE_FLAGS)
        and all(metadata.get(name) is False for name in FALSE_FLAGS)
        and metadata.get('kernel_patchset') == 'n71-dart-serdev-power-v2' and metadata.get('kernel_release') == RELEASE,
        'Runtime profile requires its exact opt-in held/IOMMU power2 scope')
    selected = files.select(root, {'directory': profile.parent, 'release': RELEASE,
        'pcie_sha256': metadata.get('module_sha256')})
    require(metadata.get('driver_modules') == [record for record, _ in selected['drivers']]
        and metadata.get('reg_on_module_sha256') == selected['diagnostics'][1]['sha256'],
        'Runtime provenance module manifest or REG_ON differs')
    return metadata, selected


def link_module(root):
    path = Path(__file__).with_name('n71-link-session.py')
    spec = importlib.util.spec_from_file_location('explicit_runtime_link', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.ROOT = root
    return module


def run(root, request):
    paths(root, request); metadata, selected = selection(root, request['profile'])
    link = link_module(root)
    modules = [(record, link.module_bytes(request['profile'].parent, record, release=RELEASE))
        for record in selected['diagnostics']]
    previous = os.environ.get('IPHONE_LINUX_PROFILE'); previous_mask = os.umask(0o077)
    try:
        os.environ['IPHONE_LINUX_PROFILE'] = str(request['profile'])
        profile = device_profile.verify()
        release = link.selected_release(metadata, profile['sha256'])
        prefix = link.aspm_payload(profile, metadata)
        iommu.payload_image(root, profile, metadata, prefix_bytes=prefix, release=release)
        identity = held.identity(request['profile'], profile, modules)
        output = request['output'] if not request['check'] else root / 'runtime'
        session = link.Session(output, modules, host_scan=True, scan_link_target=True, scan_pme_disable=True,
            scan_hold=True, resource_capable=True, iommu_parent=True, release=release, runtime=selected['drivers'])
        if request.get('firmware') is not None:
            firmware.configure(session, {'root': root, 'directory': request['firmware']})
        if request['check']:
            if request['source'] is not None:
                held.load_source(session, root, request['source'], identity)
                if firmware.KEY in session.result:
                    firmware.state(session)
            print('N71_RUNTIME_LOCAL_GATE_OK; no SSH or USB action', flush=True)
            return 0
        output.mkdir(mode=0o700)
        if request['action'] in ('acquire', 'assign'):
            return held.run(session, identity, root=root, source=request['source'], assign=request['action'] == 'assign')
        result = coordinator.run(session, {'action': request['action'], 'root': root,
            'source': request['source'], 'identity': identity})
        print('N71_RUNTIME_RESULT', json.dumps(result), flush=True)
        return 0 if result['successful'] else 1
    finally:
        os.umask(previous_mask)
        if previous is None:
            os.environ.pop('IPHONE_LINUX_PROFILE', None)
        else:
            os.environ['IPHONE_LINUX_PROFILE'] = previous
