"""Synthetic data fixtures exercise bounds, overlapping references and checksums."""
import importlib.util
from pathlib import Path
import struct
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('apple_kernel_format', ROOT / 'scripts/research/apple_kernel_format.py')
format_reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(format_reader)


def der(tag, value):
    count = max(1, (len(value).bit_length() + 7) // 8)
    size = bytes((len(value),)) if len(value) < 128 else bytes((128 + count,)) + len(value).to_bytes(count, 'big')
    return bytes((tag,)) + size + value


def image(payload):
    return der(0x30, der(0x16, b'IM4P') + der(0x16, b'krnl') + der(0x16, b'test') + der(4, payload))


def reference():
    raw = b'\xcf\xfa\xed\xfe\x0c\0\0\x01' + b'synthetic'
    compressed = b''.join(bytes((255,)) + raw[index:index + 8] for index in range(0, len(raw), 8))
    payload = struct.pack('>6I', 0x636f6d70, 0x6c7a7373, zlib.adler32(raw), len(raw), len(compressed), 1)
    return raw, payload + b'\0' * 360 + compressed


class AppleKernelFormat(unittest.TestCase):
    def test_literal_image_and_uninterpreted_suffix(self):
        raw, payload = reference()
        result, report = format_reader.decode(image(payload + b'uninterpreted'))
        self.assertEqual(result, raw)
        self.assertTrue(report['lzss_adler32_verified'])
        self.assertEqual(report['suffix_not_executed_or_decoded'], 13)

    def test_overlapping_ring_reference_and_seed(self):
        # Literal A enters index 4078; match at 4078 copies its own new bytes.
        self.assertEqual(format_reader.lzss(b'\x01A\xee\xf2', 6), b'AAAAAA')
        self.assertEqual(format_reader.lzss(b'\x00\x00\x00', 3), b'   ')
        self.assertEqual(format_reader.lzss(b'\x00\xf0\xf0', 3), b'\0\0\0')

    def test_token_truncation_and_output_bounds(self):
        for source, size in ((b'\x00', 1), (b'\x00\x00', 3), (b'\x01A', 2),
                             (b'\x01A\xee\xf2', 5), (b'\x03AB', 1), (b'\x01A', 0)):
            with self.subTest(source=source, size=size), self.assertRaises(ValueError):
                format_reader.lzss(source, size)
        with self.assertRaises(ValueError):
            format_reader.lzss(b'\x01A', format_reader.MAX_OUTPUT + 1)

    def test_checksum_and_header_rejection(self):
        _, payload = reference()
        for position in (0, 8, 23):
            modified = bytearray(payload)
            modified[position] ^= 1
            with self.subTest(position=position), self.assertRaises(ValueError):
                format_reader.decode(image(bytes(modified)))
        with self.assertRaises(ValueError):
            format_reader.decode(image(payload[:-1]))

    def test_der_envelope_type_lengths_and_field_bound(self):
        _, payload = reference()
        valid = image(payload)
        for blob in (b'', b'\x30\x80', b'\x30\x85\0\0\0\0\0', valid[:-1], valid + b'x',
                     valid.replace(b'krnl', b'dtre', 1), der(0x30, der(0x16, b'IM4P') * 9)):
            with self.subTest(size=len(blob)), self.assertRaises(ValueError):
                format_reader.im4p_payload(blob)


if __name__ == '__main__':
    unittest.main()
