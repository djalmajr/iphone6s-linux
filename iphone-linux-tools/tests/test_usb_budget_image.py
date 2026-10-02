"""Init-only repack preserves full cpio records and protected identities."""
import importlib.util
import os
from pathlib import Path
import stat
import unittest
from test_device_profile import entry
from test_kernel_integration import archive_chunks

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('USB_BUDGET_SCRIPT', ROOT / 'scripts/build/rebuild-usb-budget.py'))
spec = importlib.util.spec_from_file_location('budget_image', SCRIPT)
image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image)


class ImageBudget(unittest.TestCase):
    def archive(self, init):
        members = [
            {'name': 'root', 'mode': stat.S_IFDIR | 0o700},
            {'name': 'root/.ssh', 'mode': stat.S_IFDIR | 0o700},
            {'name': 'root/.ssh/authorized_keys', 'mode': stat.S_IFREG | 0o600, 'body': b'client identity'},
            {'name': 'etc/dropbear/dropbear_ed25519_host_key', 'mode': stat.S_IFREG | 0o600, 'body': b'server identity'},
            {'name': 'init', 'mode': stat.S_IFREG | 0o755, 'body': init},
            {'name': '.init', 'mode': stat.S_IFREG | 0o644, 'body': b'UNRELATED_INIT_NAME'},
            {'name': 'srv/data/keep', 'mode': stat.S_IFREG | 0o600, 'body': b'KEEP_CONTENT_AND_METADATA'},
        ]
        return b''.join(entry(m) for m in members) + entry({'name': 'TRAILER!!!'})

    def initial(self):
        return b'#!/bin/sh\n' + image.ANCHOR + image.OLD_UDC + b'/usr/local/sbin/start-terminal\n'

    def test_only_init_record_changes_and_keeps_metadata(self):
        old = self.archive(self.initial())
        new = image.patch(old)
        before, after = archive_chunks(old), archive_chunks(new)
        self.assertEqual(set(before), set(after))
        self.assertEqual([n for n in before if before[n] != after[n]], ['init'])
        self.assertEqual(before['init'][:54], after['init'][:54])
        self.assertEqual(before['init'][62:110], after['init'][62:110])
        parsed = image.profile_image.records(new)
        self.assertIn(image.BUDGET + image.ANCHOR, parsed['init'])
        self.assertIn(image.NEW_UDC, parsed['init'])
        self.assertEqual(parsed['root/.ssh/authorized_keys'], b'client identity')
        self.assertEqual(parsed['etc/dropbear/dropbear_ed25519_host_key'], b'server identity')

    def test_missing_anchor_refused(self):
        with self.assertRaises(ValueError):
            image.patch(self.archive(self.initial().replace(image.ANCHOR, b'')))

    def test_duplicate_anchor_refused(self):
        with self.assertRaises(ValueError):
            image.patch(self.archive(self.initial() + image.ANCHOR))

    def test_existing_budget_refused(self):
        with self.assertRaises(ValueError):
            image.patch(self.archive(image.BUDGET + self.initial()))

    def test_truncated_archive_refused(self):
        with self.assertRaises(ValueError):
            image.patch(self.archive(self.initial())[:120])


if __name__ == '__main__':
    unittest.main()
