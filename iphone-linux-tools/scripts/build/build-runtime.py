#!/usr/bin/env python3
"""Assemble the phone's runtime inside the isolated Ubuntu ARM64 VM."""

import pathlib
import re
import shutil
import subprocess
import tarfile

BASE = pathlib.Path('/home/ubuntu')
ROOT = BASE / 'iphone6s-runtime'
ROOT.mkdir(exist_ok=True)


def copy(source, destination=None):
    target = ROOT / (destination or source).lstrip('/')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target, follow_symlinks=True)


for source, destination in [('/bin/bash', '/bin/bash'),
                            ('/usr/sbin/dropbear', '/usr/sbin/dropbear'),
                            ('/usr/bin/dropbearkey', '/usr/bin/dropbearkey'),
                            ('/usr/bin/script', '/usr/bin/script')]:
    copy(source, destination)
    dependencies = subprocess.check_output(['ldd', source], text=True)
    for dependency in re.findall(r'(/[^\s()]+)', dependencies):
        copy(dependency)
copy(str(BASE / 'herdr-linux-aarch64'), '/usr/local/bin/herdr')
shutil.copytree('/usr/share/terminfo', ROOT / 'usr/share/terminfo', dirs_exist_ok=True)
for directory in ['sbin', 'usr/bin', 'usr/sbin', 'etc/dropbear', 'root/.ssh', 'run', 'var/run', 'usr/local/sbin']:
    (ROOT / directory).mkdir(parents=True, exist_ok=True)
(ROOT / 'etc/passwd').write_text('root:x:0:0:Linux operator:/root:/bin/bash\n')
(ROOT / 'etc/group').write_text('root:x:0:\n')
(ROOT / 'etc/shadow').write_text('root:*:20000:0:99999:7:::\n')
(ROOT / 'etc/shadow').chmod(0o600)
(ROOT / 'etc/shells').write_text('/bin/sh\n/bin/bash\n')
(ROOT / 'etc/nsswitch.conf').write_text('passwd: files\ngroup: files\nshadow: files\nhosts: files dns\n')
(ROOT / 'etc/hosts').write_text('127.0.0.1 localhost iphone6s-linux\n172.16.42.1 iphone6s-linux\n')
(ROOT / 'root/.bashrc').write_text('export PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin\nexport LANG=C.UTF-8\nexport SHELL=/bin/bash\nexport PS1="\\u@\\h:\\w\\$ "\n')
(ROOT / 'root/.bash_profile').write_text('source ~/.bashrc\n')
copy(str(BASE / 'iphone_ed25519.pub'), '/root/.ssh/authorized_keys')
(ROOT / 'root').chmod(0o700)
(ROOT / 'root/.ssh').chmod(0o700)
(ROOT / 'root/.ssh/authorized_keys').chmod(0o600)
key = ROOT / 'etc/dropbear/dropbear_ed25519_host_key'
if not key.exists():
    subprocess.run(['dropbearkey', '-t', 'ed25519', '-f', str(key)], check=True, stdout=subprocess.DEVNULL)
public = subprocess.check_output(['dropbearkey', '-y', '-f', str(key)], text=True)
(BASE / 'iphone-host-public.txt').write_text(public)
start = ROOT / 'usr/local/sbin/start-terminal'
start.write_text('''#!/bin/sh
export PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin
export SHELL=/bin/bash
mkdir -p /sbin /usr/bin /usr/sbin
/bin/busybox --install -s
hostname iphone6s-linux
mkdir -p /run /var/run /root/.ssh
chmod 700 /root /root/.ssh
chmod 600 /root/.ssh/authorized_keys /etc/dropbear/dropbear_ed25519_host_key
chown -R 0:0 /root/.ssh
if [ ! -f /var/run/dropbear.pid ] || ! kill -0 "$(cat /var/run/dropbear.pid)" 2>/dev/null; then
    /usr/sbin/dropbear -s -p 172.16.42.1:22 -r /etc/dropbear/dropbear_ed25519_host_key
fi
''')
start.chmod(0o755)
console = ROOT / 'usr/local/sbin/start-console'
console.write_text(r"""#!/bin/sh
export PATH=/usr/local/bin:/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin
if [ ! -c /dev/fb0 ] || [ ! -c /dev/tty1 ]; then
    echo "Framebuffer console unavailable" >&2
    exit 1
fi
echo 0 > /sys/class/graphics/fb0/blank || exit 1
# Writing the VT triggers deferred fbcon takeover in this kernel.
{
    printf '\033[2J\033[HiPhone 6s Linux - console\n\n'
    uname -a
    printf '\n'
    uptime
    printf '\n'
    free -m
    printf '\nSSH: 172.16.42.1\nHTTP: http://172.16.42.1:8080/cgi-bin/status\n'
    printf '\nUse o Mac para digitar; o toque nao e necessario.\n'
} > /dev/tty1
chvt 1
""")
console.chmod(0o755)
def root_owner(info):
    info.uid = info.gid = 0
    info.uname = info.gname = 'root'
    return info


with tarfile.open(BASE / 'iphone6s-runtime.tar.gz', 'w:gz') as archive:
    for item in sorted(ROOT.iterdir()):
        archive.add(item, arcname=item.name, filter=root_owner)
print('Runtime archive ready; private client key was not included.')
