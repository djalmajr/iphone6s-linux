#!/bin/bash
set -euo pipefail

# Run only inside the isolated Ubuntu Multipass VM.
root=/home/ubuntu/iphone6s-rootfs
mkdir -p "$root"/{bin,dev,etc,lib/modules,proc,sys,run,tmp,var/run}
cp /usr/bin/busybox "$root/bin/busybox"
cp /home/ubuntu/init-iphone6s "$root/init"
cp /home/ubuntu/iphone6s-modules/usb_f_ncm.ko "$root/lib/modules/usb_f_ncm.ko"
chmod 755 "$root/init"
if [ ! -e "$root/dev/console" ]; then sudo mknod "$root/dev/console" c 5 1; fi
if [ ! -e "$root/dev/null" ]; then sudo mknod "$root/dev/null" c 1 3; fi
cd "$root"
# Keep the output owned by the VM user; sudo is only needed to read the rootfs.
# shellcheck disable=SC2024
sudo sh -c 'find . -print0 | cpio --null -o -H newc 2>/dev/null' > /home/ubuntu/iphone6s-initramfs.cpio
gzip -9 -c /home/ubuntu/iphone6s-initramfs.cpio > /home/ubuntu/iphone6s-initramfs.gz
file /home/ubuntu/iphone6s-initramfs.gz
