"""Weaken builder gates in disposable copies, with no native build or device access."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'scripts/build/build-n71-wifi-modules.py'
MUTATIONS = {
    'core-config': ("values.get(name, 'n') == value", 'True'),
    'macro-scope': ('set(paths) == MACRO_FILES', 'MACRO_FILES <= set(paths)'),
    'warning-errors': ("'KCFLAGS=-Werror'", "'KCFLAGS='"),
    'bundle-exports': ("'KBUILD_EXTRA_SYMBOLS=' + ' '.join(map(str, exports))", "'KBUILD_EXTRA_SYMBOLS='"),
    'pcie-object': ("'CONFIG_BRCMFMAC_PCIE=y'", "'CONFIG_BRCMFMAC_PCIE=n'"),
    'machine': ("struct.unpack_from('<HH', raw, 16) == (1, 183)", 'True'),
    'vermagic': ('raw.count(magic) == 1', 'raw.count(magic) >= 1'),
    'output-exists': ('not path.exists() and not path.is_symlink()', 'not path.is_symlink()'),
    'source-boundary': ('source not in path.parents', 'True'),
    'device-class-alias': ('require(ALIAS in aliases,', 'require(bool(aliases),'),
    'preserved-hash': ('hashlib.sha256(raw).hexdigest() == expected', 'True'),
    'release': ("(output / 'include/config/kernel.release').read_text().strip() == RELEASE", 'True'),
    'space-budget': ('shutil.disk_usage(parent).free >= 1024 * 1024 * 1024',
                     'shutil.disk_usage(parent).free >= 1024 * 1024 * 1024 - 1'),
}


def main():
    text = SOURCE.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-wifi-module-mutations-') as directory:
        for name, (before, after) in MUTATIONS.items():
            if text.count(before) != 1:
                raise SystemExit('Mutation anchor differs: ' + name)
            mutated = Path(directory) / (name + '.py')
            mutated.write_text(text.replace(before, after))
            env = dict(os.environ, N71_WIFI_MODULES_SCRIPT=str(mutated), PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'tests'),
                                      '-p', 'test_n71_wifi_modules.py'], env=env, capture_output=True,
                                     text=True, timeout=30)
            output = process.stdout + process.stderr
            if process.returncode == 0 or 'AssertionError' not in output or 'ERROR:' in output:
                raise SystemExit('Mutation not killed by assertion: ' + name)
            print('N71_WIFI_MODULE_MUTATION_KILLED', name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
