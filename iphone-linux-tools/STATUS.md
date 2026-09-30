# iPhone 6s Linux experiment — updated 2026-09-29

## Current result: Linux, Bash, SSH, HTTP and Herdr verified

Bash 5.2.21, key-only Dropbear SSH and Herdr 0.9.1/protocol 22 were verified on the phone. The Herdr pane survived disconnecting the SSH client. Bootstrap Telnet is now stopped. The runtime and candidate image contain a private SSH server key and remain local. The integrated console image booted successfully through a fresh DFU cycle, with SSH/HTTP available before any runtime transfer; the complete updated cold-boot wrapper remains untested. The dedicated build VM was stopped after recording package versions. See `docs/REPRODUCAO.md` for the full chronology and public evidence.

## File persistence — verified 2026-09-29

Private snapshots on the Mac now cover `/srv/data` and work files in `/root`. Restore checks integrity/scope and captures a pre-restore snapshot before overwriting. Real phone tests recovered file contents and permissions, retained extra files, and blocked symlink/hardlink targets; six local tests passed. HTTP and Herdr remained running. Identity SSH and Herdr live-session state are excluded. This is explicit file backup, not continuous storage or automatic restore; recovery after a fresh DFU remains untested. See `docs/PERSISTENCIA.md`.

## Display console — verified 2026-09-29

`simpledrm` exposed fb0 at 750 × 1334. Unblanking, writing tty1 and switching VT activated fbcon. The user confirmed both the initial console text and commands typed through an SSH Bash mirrored by util-linux `script`. The `console` helper is tested. The integrated image booted and the user confirmed the console appeared automatically; see `docs/CONSOLE.md`.

## Earlier result: Linux and USB HTTP server running

- On 2026-09-29 the user replaced the cable with a genuine **USB-A-to-Lightning** cable connected to a rear Mac port. The first guided attempt with that cable succeeded: palera1n reported `Device entered DFU mode successfully`, `Checkmate!`, and `Booting PongoOS...`. `ioreg` confirmed `PongoOS USB Device`.
- `pongoterm` uploaded the verified 11,700,549-byte combined payload and ran `bootm`. The Mac subsequently detected `iPhone 6s Linux probe` and its NCM network interface `en12`.
- A temporary `172.16.42.2/24` alias was added only to `en12`, using the macOS administrator dialog. The phone is `172.16.42.1`; `route -n get 172.16.42.1` confirmed `en12`.
- A real shell returned `Linux (none) 7.0.12 #1-postmarketOS SMP PREEMPT Fri Jun 12 10:53:24 UTC 2026 aarch64 GNU/Linux`, model `Apple iPhone 6s (Samsung)`, two processors, and 1,973 MiB RAM. The interactive shell was also tested with `uname -a` and `exit`. Evidence: `linux-boot-proof.txt`.
- BusyBox HTTP serves a live status page at **http://172.16.42.1:8080/cgi-bin/status**, bound to the USB address only. The real HTTP response was saved to `linux-http-proof.html`. Repeated `serve` completed successfully without launching another HTTP server.
- `/sys/block` exposed only loop devices and zram; no internal-storage block device appeared. `/sys/class/power_supply` was empty. Persistent internal storage and battery/charging monitoring are therefore **not established** in this session.
- The screen is black, as reported by the user; the shell and HTTP service work independently of it. This is an experimental **RAM session**, requiring Mac-assisted boot and physical DFU buttons after a restart. It is not an autonomous or unattended server installation.
- `iphone-linux.sh` provides `status`, `shell`, `serve`, `connect`, `disconnect`, and a prepared `boot` wrapper. `status`, interactive `shell`, and repeated `serve` were verified against the phone. The assembled `boot` wrapper has not been rerun from a fresh restart; its individual DFU/Pongo/upload stages were used successfully in this session.
- The visual guide and pongoterm processes were stopped after use. The phone's Linux/HTTP session and the dedicated Mac USB IP alias remain intentionally active. No Mac package was installed and no remote account/service was changed.

## Earlier diagnostics and preparation

## Device and findings

- iPhone 6s (`iPhone8,1`, `N71AP`, Samsung A9 S8000), 32 GB. The official Finder recovery-mode **Update** completed on 2026-09-27; `ideviceinfo -k ProductVersion` confirmed **iOS 15.8.8** after reboot. It was previously on iOS 15.7.5.
- Mac USB pairing validates. After the update, the phone requested a PIN to continue installation; the user entered it, and iOS finished setup before the Linux boot test.
- Battery reported 1,462 cycles in an earlier diagnostic; its runtime is poor.
- The touch panel generates phantom touches even with Lightning disconnected. A video shows calculator keys activating without contact and a row of display artifacts near the bottom of the 0 key. This points to the screen assembly or its connection, but does not isolate the exact component.
- Home responds to a long press by opening Siri. Siri did not execute a spoken command, and Wi-Fi connectivity is uncertain.
- Recovery mode worked. Multiple DFU attempts with a direct USB-C-to-Lightning cable ended in an Apple logo followed by Recovery, and palera1n reported `Whoops, device did not enter DFU mode`.
- The USB-C-to-Lightning cable was moved from the Mac Studio M2 Max front USB-C port to a rear USB-C port. `ioreg -p IOUSB -w0` then showed the iPhone directly under `AppleT8112USBXHCI@03000000`, instead of behind the front path's ASMedia USB2 hub. `ideviceinfo -k ProductVersion` still returned 15.8.8.
- A synchronized visual DFU attempt on the rear USB-C port ran through palera1n's 4-second Power+Home and 10-second Home stages. The tool reported `Whoops, device did not enter DFU mode`; `ioreg` showed `Apple Mobile Device (Recovery Mode)`, not DFU. The guide process was stopped, the browser page closed, and `palera1n -n` exited recovery. `ioreg` then showed a normal `iPhone`, and `ideviceinfo -k ProductVersion` returned 15.8.8. No Linux payload was uploaded.
- The user confirmed that phantom touches still occur after the official iOS 15.8.8 update. Whether display artifacts also recur after the update is awaiting observation. The artifacts were absent on black screens and during the Apple logo before the update; this does not alone identify a software or hardware cause.

## Prepared local files

- `palera1n-macos-arm64`: official v2.4 binary; SHA-256 `950c357b6ae5df36128f6e42a3c6d371e55aeb69a5afcde276f096276210d0c9` matched the official GitHub release digest. CleanMyMac classified it as jailbreak riskware. It was run from this directory only.
- `Pongo.bin`, `pongoterm`, `m1n1.bin`, `vmlinuz-apple-16k`, `s8000-n71.dtb`, and `iphone6s-initramfs.gz` are staged for an experimental RAM boot.
- `m1n1-linux-iphone6s.bin` is the combined boot payload (SHA-256 `7d81106731fa74a924c615c1f7710653a42a154703b8f7a227e389556c51b520`). It **booted successfully on 2026-09-29**.
- The local DFU countdown prototype was removed at the operator's request on 2026-09-30. `dfu_boot.py` monitors manual DFU without opening a browser or HTTP listener; its local simulated tests passed, but the replacement still needs a physical cold-boot test.
- The isolated Multipass VM `iphone6s-build` was used to build arm64 components and is stopped. Existing VMs were not modified.

## Practical limits and next test

HoolockLinux supports experimental A9 boots, but documents internal storage support only for A11. For this A9 phone, a Linux boot would be tethered and RAM based; autonomous boot after a restart is not established. The prepared initramfs exposes a temporary unauthenticated telnet shell on the USB link for **boot proof only**. It is not a production server image.

Ghost touches did return after the official update. The user chose Linux rather than any iOS-based server and asked to stop repeating the failed DFU timing approach. A full Restore has not been done. Both documented HoolockLinux methods, PongoOS and iBoot, require hardware DFU. The materially different USB-A-to-Lightning cable test **succeeded on 2026-09-29**; palera1n documents that USB-C-to-Lightning may prevent DFU. Do not use fakefs or the A11 partitioning tools on this A9. The worn battery and absence of battery-monitoring data remain limits for unattended use.

An iOS-based route using Dopamine/TrollStore avoids DFU, but installation and initial launch require working on-device interaction. TrollRestore's backup method also requires Find My disabled, which would change remote account state if currently enabled; that was not attempted. No remote accounts or services were modified.

Sources: [HoolockLinux setup](https://github.com/HoolockLinux/docs/blob/master/tutorials/SETUP_pongoOS.md), [HoolockLinux storage status](https://github.com/HoolockLinux/docs/blob/master/tools/README.md), [palera1n guide](https://ios.cfw.guide/installing-palera1n/), [Dopamine](https://github.com/opa334/Dopamine), [TrollRestore](https://github.com/JJTech0130/TrollRestore).
