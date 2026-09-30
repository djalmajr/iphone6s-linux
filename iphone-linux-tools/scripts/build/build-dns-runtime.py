#!/usr/bin/env python3
"""Extract an authenticated Ubuntu DNS executable and its existing VM libraries."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

SIGNER = 'F6ECB3762474EDA9D21B7022871920D1991BC93C'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(options):
    inputs = options.inputs.resolve()
    options.output.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='iphone-dns-build-') as temporary:
        work = Path(temporary)
        release_path = work / 'Release'
        verified = subprocess.run([
            'gpgv', '--keyring', '/usr/share/keyrings/ubuntu-archive-keyring.gpg',
            '--status-fd', '1', '--output', str(release_path),
            str(inputs / 'InRelease'),
        ], capture_output=True, text=True, check=True)
        require(f'VALIDSIG {SIGNER} ' in verified.stdout, 'Unexpected Ubuntu signer')
        release = release_path.read_text()
        fields = dict(line.split(': ', 1) for line in release.splitlines() if ': ' in line)
        require(fields.get('Origin') == 'Ubuntu' and fields.get('Suite') == 'noble-security',
                'Wrong package suite or origin')
        hashes = release.split('SHA256:\n', 1)[1].split('SHA512:', 1)[0]
        records = [line.split() for line in hashes.splitlines()]
        expected = [entry for entry in records if len(entry) == 3 and
                    entry[2] == 'main/binary-arm64/Packages.xz']
        require(len(expected) == 1, 'Missing or duplicate ARM64 package index')
        index = inputs / 'Packages.xz'
        require(index.stat().st_size == int(expected[0][1]) and
                digest(index) == expected[0][0], 'Package index integrity failed')
        candidates = []
        for block in lzma.decompress(index.read_bytes()).decode().split('\n\n'):
            if not block.startswith('Package: dnsmasq-base\n'):
                continue
            entry = dict(line.split(': ', 1) for line in block.splitlines()
                         if ': ' in line and not line.startswith(' '))
            if entry.get('Architecture') == 'arm64':
                candidates.append(entry)
        require(len(candidates) == 1, 'DNS ARM64 package is not unique')
        package = candidates[0]
        require(package['Filename'].startswith('pool/main/d/dnsmasq/') and
                '..' not in Path(package['Filename']).parts, 'Unexpected package path')
        archive = inputs / 'dnsmasq.deb'
        require(archive.stat().st_size == int(package['Size']) and
                digest(archive) == package['SHA256'], 'DNS package integrity failed')
        extracted = work / 'extracted'
        # dpkg-deb extracts data only; package maintainer scripts are not run.
        subprocess.run(['dpkg-deb', '-x', str(archive), str(extracted)], check=True)
        binary = extracted / 'usr/sbin/dnsmasq'
        linkage = subprocess.check_output(['ldd', str(binary)], text=True)
        require('not found' not in linkage, 'Required library missing from dedicated VM')
        libraries = sorted(set(re.findall(r'/[^\s()]+', linkage)))
        root = work / 'srv/data/dns/runtime'
        (root / 'bin').mkdir(parents=True)
        (root / 'lib').mkdir()
        shutil.copyfile(binary, root / 'bin/dnsmasq')
        (root / 'bin/dnsmasq').chmod(0o755)
        names = set()
        library_report = []
        for source in libraries:
            path = Path(source)
            require(path.name not in names, 'Conflicting library basename')
            names.add(path.name)
            target = root / 'lib' / path.name
            shutil.copyfile(path, target, follow_symlinks=True)
            target.chmod(0o755)
            library_report.append({'name': path.name, 'sha256': digest(target)})
        notice = extracted / 'usr/share/doc/dnsmasq-base/copyright'
        shutil.copyfile(notice, root / 'COPYRIGHT')
        report = {'architecture': package['Architecture'],
                  'binary_sha256': digest(binary), 'index_sha256': expected[0][0],
                  'libraries': library_report, 'origin': fields['Origin'],
                  'package_sha256': package['SHA256'], 'package_version': package['Version'],
                  'release_date': fields['Date'], 'signer': SIGNER, 'suite': fields['Suite']}
        (root / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
        target = options.output / 'iphone6s-dns-runtime.tar.gz'
        require(not target.exists(), 'Output already exists; preserve the previous bundle')
        with tarfile.open(target, 'w:gz') as output:
            for item in sorted(work.glob('srv/**/*')):
                if not item.is_file():
                    continue
                info = output.gettarinfo(str(item), arcname=str(item.relative_to(work)))
                info.uid = info.gid = 0
                info.uname = info.gname = 'root'
                with item.open('rb') as stream:
                    output.addfile(info, stream)
        target.chmod(0o600)
        report.update({'bundle_sha256': digest(target), 'bundle_bytes': target.stat().st_size})
        (options.output / 'dns-provenance.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path)
    try:
        build(parser.parse_args())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
