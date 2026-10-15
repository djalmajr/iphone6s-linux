"""CLI format/integrity boundaries using synthetic nonbootable Mach-O files."""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('PONGO_VERIFY_SCRIPT', ROOT / 'scripts/build/verify-pongo-build.py'))


class PongoVerifierTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix='pongo-format-synthetic-')
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.macho = self.root / 'Pongo'
        self.binary = self.root / 'Pongo.bin'
        base, file_offset, command_size = 0x100000000, 264, 232
        self.raw = b'bootm\0' + b'\xa5' * 10 + b'2.6.3-bb492b00\0'
        header = struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 5, 1, command_size, 0, 0)
        segment = struct.pack('<II16sQQQQiiII', 0x19, command_size, b'__TEXT', base,
                              0x4000, file_offset, len(self.raw), 7, 5, 2, 0)
        text = struct.pack('<16s16sQQ8I', b'__text', b'__TEXT', base, 6,
                           file_offset, 0, 0, 0, 0, 0, 0, 0)
        version = struct.pack('<16s16sQQ8I', b'__version', b'__TEXT', base + 16, 15,
                              file_offset + 16, 0, 0, 0, 0, 0, 0, 0)
        self.blob = header + segment + text + version + self.raw
        self.macho.write_bytes(self.blob)
        self.binary.write_bytes(self.raw)

    def run_cli(self):
        return subprocess.run([sys.executable, str(SCRIPT), str(self.macho), str(self.binary)],
                              capture_output=True, text=True, timeout=10)

    def test_valid_mapping_preserves_nonzero_padding_between_sections(self):
        # Mutation captured: copying sections separately drops nonzero mapped padding.
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PONGO_MACHO_MAPPING_VERIFIED', result.stdout)

    def test_wrong_cpu_and_file_type_are_rejected(self):
        # Mutation captured: accepting x86_64 or non-preload Mach-O as a phone candidate.
        for offset, value in [(4, 0x1000007), (12, 2)]:
            with self.subTest(offset=offset):
                blob = bytearray(self.blob)
                struct.pack_into('<I', blob, offset, value)
                self.macho.write_bytes(blob)
                self.assertEqual(self.run_cli().returncode, 1)

    def test_malformed_commands_and_sections_are_rejected(self):
        # Mutation captured: trusting unbounded or mismatched load/section regions.
        for offset, value in [(20, 0x100000), (36, 0), (104 + 48, 300)]:
            with self.subTest(offset=offset):
                blob = bytearray(self.blob)
                struct.pack_into('<I', blob, offset, value)
                self.macho.write_bytes(blob)
                self.assertEqual(self.run_cli().returncode, 1)

    def test_changed_raw_binary_is_rejected(self):
        # Mutation captured: omitting comparison with the independently mapped Mach-O.
        self.binary.write_bytes(self.raw[:7] + b'\x00' + self.raw[8:])
        self.assertEqual(self.run_cli().returncode, 1)

    def test_wrong_version_and_missing_bootm_are_rejected(self):
        # Mutation captured: accepting a different revision or missing bootm command.
        for before, after in [(b'bb492b00', b'00000000'), (b'bootm', b'bootx')]:
            with self.subTest(marker=before):
                self.macho.write_bytes(self.blob.replace(before, after))
                self.binary.write_bytes(self.raw.replace(before, after))
                self.assertEqual(self.run_cli().returncode, 1)

    def test_links_and_oversized_files_are_rejected(self):
        # Mutation captured: following symlinks instead of checking the input type.
        self.macho.unlink()
        source = self.root / 'source'
        source.write_bytes(self.blob)
        self.macho.symlink_to(source)
        self.assertEqual(self.run_cli().returncode, 1)
        self.macho.unlink()
        self.macho.write_bytes(self.blob)
        with self.binary.open('wb') as file:
            file.truncate(0x80001)
        self.assertEqual(self.run_cli().returncode, 1)


if __name__ == '__main__':
    unittest.main()
