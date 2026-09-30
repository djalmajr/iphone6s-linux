#!/bin/bash
set -euo pipefail
# Run only in the isolated Ubuntu ARM64 VM, after transferring the inputs.
server_root=/home/ubuntu/iphone6s-server-rootfs
mkdir -p "$server_root"
cd "$server_root"
gzip -dc /home/ubuntu/iphone6s-initramfs.gz | sudo cpio -idm --no-absolute-filenames
sudo tar -xzf /home/ubuntu/iphone6s-runtime.tar.gz -C "$server_root"
sudo cp /home/ubuntu/init-server "$server_root/init"
sudo chmod 755 "$server_root/init"
sudo mkdir -p "$server_root/srv/iphone/cgi-bin"
sudo cp /home/ubuntu/iphone-status "$server_root/srv/iphone/cgi-bin/status"
sudo chmod 755 "$server_root/srv/iphone/cgi-bin/status"
sudo chown -R 0:0 "$server_root"
sudo sh -c 'cd /home/ubuntu/iphone6s-server-rootfs && find . -print0 | cpio --null -o -H newc 2>/dev/null' > /home/ubuntu/iphone6s-server-initramfs.cpio
gzip -n -9 -c /home/ubuntu/iphone6s-server-initramfs.cpio > /home/ubuntu/iphone6s-server-initramfs.gz
chmod 600 /home/ubuntu/iphone6s-server-initramfs.gz
sha256sum /home/ubuntu/iphone6s-server-initramfs.gz
