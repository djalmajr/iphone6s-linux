"""A chip identifier alone never proves restored config or a released map."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_chip_result as result

TEXT = ('N71_PCIE_CHIP_CONFIG_RESTORED error=0; route/window/readback checked\n'
        'N71_PCIE_CHIP_ID raw=13324350 chip=4350 revision=2; one read only\n'
        'N71_PCIE_CHIP_MAP_RELEASED mapped=0 claimed=0\n'
        'N71_PCIE_CHIP_RESULT error=0 config_reads=90 mmio_reads=1; no DMA or radio\n')


class ChipResultTests(unittest.TestCase):
    def test_chip_revision_and_cleanup_are_one_result(self):
        identity = result.parse(TEXT)
        self.assertEqual((identity['chip'], identity['revision']), (0x4350, 2))
        self.assertEqual(identity['mmio_reads'], 1)

    def test_invalid_id_budget_and_cleanup_refused(self):
        altered = (TEXT + TEXT, TEXT.replace('revision=2', 'revision=3'),
                   TEXT.replace('raw=13324350', 'raw=ffffffff'),
                   TEXT.replace('mmio_reads=1', 'mmio_reads=2'),
                   TEXT.replace('mmio_reads=1', 'mmio_reads=0'),
                   TEXT.replace('config_reads=90', 'config_reads=201'),
                   TEXT.replace('RESTORED error=0', 'RESTORED error=-5'),
                   TEXT.replace('claimed=0', 'claimed=1'))
        for text in altered:
            with self.subTest(text=text), self.assertRaises(ValueError):
                result.parse(text)

    def test_negative_read_still_requires_full_cleanup(self):
        failed = TEXT.replace('RESULT error=0', 'RESULT error=-19')
        result.cleanup(failed)
        for text in (failed.replace('CONFIG_RESTORED', 'CONFIG_MISSING'),
                     failed.replace('MAP_RELEASED', 'MAP_MISSING')):
            with self.assertRaises(ValueError):
                result.cleanup(text)
        result.cleanup('N71_PCIE_SIZING_RESULT error=-5')
        with self.assertRaises(ValueError):
            result.cleanup('')

    def test_acceptance_mutations_fail_assertions(self):
        source = Path(result.__file__).read_text()
        mutations = (
            ("require(restored == ['0']", "require(restored != ['0']",
             TEXT.replace('RESTORED error=0', 'RESTORED error=-5')),
            ("== [('0', '0')]", "== [('0', '1')]", TEXT.replace('claimed=0', 'claimed=1')),
            ("revision == (raw >> 16) & 0xf", "revision >= 0", TEXT.replace('revision=2', 'revision=3')),
            ("result['mmio_reads'] == 1", "result['mmio_reads'] <= 1", TEXT.replace('mmio_reads=1', 'mmio_reads=0')),
        )
        for before, after, text in mutations:
            self.assertEqual(source.count(before), 1)
            namespace = {}
            exec(compile(source.replace(before, after, 1), 'mutant-chip-result.py', 'exec'), namespace)
            with self.assertRaises(AssertionError):
                with self.assertRaises(ValueError):
                    SimpleNamespace(**namespace).parse(text)


if __name__ == '__main__':
    unittest.main()
