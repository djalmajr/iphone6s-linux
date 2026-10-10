"""Physical BAR evidence needs consistent masks and verified restoration."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_bar_result as result

RAW = [4, 0, 4, 0, 0, 0]
MASKS = [0xffff8004, 0xffffffff, 0xffc00004, 0xffffffff, 0, 0]
SIZES = [0x8000, 0, 0x400000, 0, 0, 0]
TEXT = (''.join(f'N71_PCIE_SIZED_BAR index={index} raw={raw:08x} mask={mask:08x} bytes={size:016x}; no MMIO\n'
                for index, (raw, mask, size) in enumerate(zip(RAW, MASKS, SIZES)))
        + 'N71_PCIE_SIZING_CONFIG_RESTORED error=0; decode/readback checked\n'
        + 'N71_PCIE_SIZING_RESULT error=0 reads=80 attempts=13 writes=10 refusals=0; no DMA or radio\n')


class BarResultTests(unittest.TestCase):
    def test_complete_sizes_and_originals(self):
        parsed = result.parse(TEXT, RAW)
        self.assertEqual([bar['bytes'] for bar in parsed['bars']], SIZES)
        self.assertEqual(parsed['attempts'], 13)

    def test_incomplete_duplicate_masks_sizes_and_inventory_refused(self):
        altered = [TEXT + TEXT, TEXT.replace('index=5', 'index=4'),
                   TEXT.replace('mask=ffff8004', 'mask=ffff7004'),
                   TEXT.replace('mask=ffff8004', 'mask=ffff8000'),
                   TEXT.replace('bytes=0000000000008000', 'bytes=0000000000004000'),
                   TEXT.replace('mask=ffffffff', 'mask=fffffffe', 1),
                   TEXT.replace('raw=00000004', 'raw=00000001', 1),
                   TEXT.replace('attempts=13', 'attempts=14'),
                   TEXT.replace('refusals=0', 'refusals=1'),
                   TEXT.replace('RESTORED error=0', 'RESTORED error=-5')]
        for text in altered:
            with self.subTest(text=text), self.assertRaises(ValueError):
                result.parse(text, RAW)
        with self.assertRaises(ValueError):
            result.parse(TEXT, [0] * 6)

    def test_failure_still_requires_restore_before_unload(self):
        failed = TEXT.replace('RESULT error=0', 'RESULT error=-5')
        result.cleanup(failed)
        with self.assertRaises(ValueError):
            result.cleanup(failed.replace('CONFIG_RESTORED', 'CONFIG_NOT_RESTORED'))
        result.cleanup('N71_PCIE_LINK_RESULT error=-110')
        with self.assertRaises(ValueError):
            result.cleanup('')

    def test_acceptance_mutations_fail_assertions(self):
        source = Path(result.__file__).read_text()
        mutations = (
            ("require(restored == ['0'] or", "require(restored != ['0'] or",
             lambda mutant: mutant.cleanup(TEXT.replace('RESTORED error=0', 'RESTORED error=-5'))),
            ("and bar['bytes'] == size", "and bar['bytes'] >= 0",
             lambda mutant: mutant.parse(TEXT.replace('bytes=0000000000008000', 'bytes=0000000000004000'), RAW)),
            ("[bar['raw'] for bar in bars] == expected_raw", "len(bars) == len(expected_raw)",
             lambda mutant: mutant.parse(TEXT, [0] * 6)),
            ("result['refusals'] == 0", "result['refusals'] <= 1",
             lambda mutant: mutant.parse(TEXT.replace('refusals=0', 'refusals=1'), RAW)),
        )
        for before, after, probe in mutations:
            self.assertEqual(source.count(before), 1)
            namespace = {}
            exec(compile(source.replace(before, after, 1), 'mutant-bar-result.py', 'exec'), namespace)
            with self.assertRaises(AssertionError):
                with self.assertRaises(ValueError):
                    probe(SimpleNamespace(**namespace))


if __name__ == '__main__':
    unittest.main()
