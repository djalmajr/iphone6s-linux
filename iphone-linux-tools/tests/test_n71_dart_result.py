"""Incomplete, unstable and wrongly routed DART evidence must be refused."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_dart_result as result

TEXT = ('N71_DART_SOURCE physical=0000000602008000 bytes=00004000 irq=248 provider=disabled owner=none\n'
        'N71_DART_STATE command=00000000 tcr=01800280 error=82000005 enabled=5 ttbr-valid=8001; stable\n'
        'N71_DART_MAP_RELEASED mapped=0 claimed=0\n'
        'N71_DART_RESULT error=0 reads=38 guards=39; no DART writes or DMA\n')


class DartResultTests(unittest.TestCase):
    def test_valid_state_has_sanitized_stream_and_fault_flags(self):
        state = result.parse(TEXT)
        self.assertEqual((state['tcr'], state['enabled_streams']), (0x01800280, 5))
        self.assertEqual((state['valid_ttbr_mask'], state['valid_ttbr_count']), (0x8001, 2))
        self.assertTrue(state['fault_flag'])
        self.assertEqual((state['fault_stream'], state['fault_code']), (2, 5))

    def test_missing_or_wrong_source_counts_state_and_cleanup_refused(self):
        altered = (TEXT + TEXT, TEXT.replace('602008000', '602004000'),
                   TEXT.replace('irq=248', 'irq=247'), TEXT.replace('provider=disabled', 'provider=okay'),
                   TEXT.replace('reads=38', 'reads=37'), TEXT.replace('reads=38', 'reads=39'),
                   TEXT.replace('guards=39', 'guards=38'), TEXT.replace('guards=39', 'guards=40'),
                   TEXT.replace('command=00000000', 'command=00000008'),
                   TEXT.replace('tcr=01800280', 'tcr=ffffffff'), TEXT.replace('enabled=5', 'enabled=4'),
                   TEXT.replace('claimed=0', 'claimed=1'), TEXT.replace('error=0 reads', 'error=-5 reads'),
                   TEXT.replace('; stable', '; unstable'))
        for text in altered:
            with self.subTest(text=text), self.assertRaises(ValueError):
                result.parse(text)

    def test_negative_read_requires_mapping_release(self):
        text = TEXT.replace('error=0 reads=38 guards=39', 'error=-5 reads=5 guards=6')
        result.cleanup(text)
        with self.assertRaises(ValueError):
            result.cleanup(text.replace('MAP_RELEASED', 'MAP_MISSING'))
        result.cleanup('N71_PCIE_INVENTORY_RESULT error=-5')
        with self.assertRaises(ValueError):
            result.cleanup('')

    def test_acceptance_mutations_fail_assertions(self):
        source = Path(result.__file__).read_text()
        mutations = (
            ("== [('0', '0')]", "== [('0', '1')]", TEXT.replace('claimed=0', 'claimed=1')),
            ("result['guards'] == 39", "result['guards'] >= 38", TEXT.replace('guards=39', 'guards=38')),
            ('enabled == expected', 'enabled >= 0', TEXT.replace('enabled=5', 'enabled=4')),
            ('not command & 8', 'not command & 16', TEXT.replace('command=00000000', 'command=00000008')),
        )
        for before, after, text in mutations:
            self.assertEqual(source.count(before), 1)
            namespace = {}
            exec(compile(source.replace(before, after, 1), 'mutant-dart-result.py', 'exec'), namespace)
            with self.assertRaises(AssertionError):
                with self.assertRaises(ValueError):
                    SimpleNamespace(**namespace).parse(text)


if __name__ == '__main__':
    unittest.main()
