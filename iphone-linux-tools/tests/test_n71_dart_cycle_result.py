"""Only a complete guarded provider cycle is accepted as physical success."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from test_n71_dart_result import TEXT as OBSERVATION

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/host'))
import n71_dart_cycle_result as result
import n71_dart_result

VALUES = [0x80000000 + index for index in range(16)]
TEXT = ('N71_DART_CYCLE_PROVIDER bound=1 irq-hwirq=248 mapping-new=1; no DMA attachment\n'
        'N71_DART_CYCLE_REMOVED device=0 mapping-new=0 claimed=1; restore ownership held\n'
        'N71_DART_CYCLE_RELEASED device=0 mapping-new=0 claimed=0 mapped=0\n'
        'N71_DART_CYCLE_RESULT error=0 snapshots=4 reads=152 guards=156 quiet=17 writes=16 '
        'attempted=1 stopped=1 restored=1 control-changed=0; no DMA\n')
TEXT += ''.join(f'N71_DART_CYCLE_SNAPSHOT index={index} command=00000f02 tcr=00000000 '
                f'error=00000100 valid={valid}; stable\n'
                for index, valid in enumerate(('ffff', '0000', '0000', 'ffff'), 1))
TEXT += ''.join(f'N71_DART_TTBR index={index:02d} value={value:08x}; stable\n'
                for index, value in enumerate(VALUES))


class DartCycleResultTests(unittest.TestCase):
    def test_success_is_sanitized_and_binds_source_counts(self):
        state = result.parse(TEXT)
        self.assertTrue(state['provider_initialized'])
        self.assertFalse(state['dma_enabled'])
        self.assertEqual(state['ttbr_words_restored'], 16)
        self.assertEqual(state['ttbr_sha256'], hashlib.sha256(struct.pack('<16I', *VALUES)).hexdigest())
        self.assertNotIn('80000001', str(state))

    def test_incomplete_active_changed_or_unrestored_cycle_refused(self):
        alterations = (('snapshots=4', 'snapshots=3'), ('reads=152', 'reads=151'),
                       ('guards=156', 'guards=155'), ('quiet=17', 'quiet=16'),
                       ('writes=16', 'writes=15'), ('bound=1', 'bound=0'),
                       ('irq-hwirq=248', 'irq-hwirq=247'), ('attempted=1', 'attempted=0'),
                       ('restored=1', 'restored=0'), ('stopped=1', 'stopped=0'),
                       ('control-changed=0', 'control-changed=1'),
                       ('tcr=00000000', 'tcr=00000080'), ('command=00000f02', 'command=00000f0a'),
                       ('error=00000100', 'error=80000100'), ('index=2 command', 'index=1 command'),
                       ('value=80000000', 'value=00000000'), ('index=03 value', 'index=04 value'),
                       ('RELEASED device=0', 'RELEASED device=1'), ('RELEASED device=0 mapping-new=0',
                                                                  'RELEASED device=0 mapping-new=1'))
        for before, after in alterations:
            with self.subTest(before=before), self.assertRaises(ValueError):
                result.parse(TEXT.replace(before, after))
        with self.assertRaises(ValueError):
            result.parse(TEXT + TEXT)

    def test_failed_probe_can_clean_up_only_with_restore_and_no_owner(self):
        text = TEXT.replace('error=0 snapshots', 'error=-19 snapshots')
        result.cleanup(text)
        for before in ('restored=1', 'stopped=1'):
            with self.assertRaises(ValueError):
                result.cleanup(text.replace(before, before.replace('1', '0')))
        result.cleanup('N71_PCIE_LINK_RESULT error=-110')
        with self.assertRaises(ValueError):
            result.cleanup('')

    def test_previous_private_digest_and_real_log_must_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            rows = {'result-private.json': json.dumps({'dart_observation': n71_dart_result.parse(OBSERVATION)}),
                    'preflight-private.log': '[ 1.000000] old N71_PCIE_LINK_RESULT error=0\n',
                    'pcie-cleanup-private.log': '[ 1.000000] old N71_PCIE_LINK_RESULT error=0\n' + OBSERVATION}
            for name, text in rows.items():
                path = folder / name; path.write_text(text); path.chmod(0o600)
            result.previous(folder)
            for name, text in (('result-private.json', '{}'), ('pcie-cleanup-private.log', OBSERVATION.replace('index=01', 'index=02'))):
                path = folder / name; path.write_text(text)
                with self.assertRaises(ValueError):
                    result.previous(folder)
                path.write_text(rows[name])

    def test_acceptance_mutations_fail_by_assertion(self):
        source = Path(result.__file__).read_text()
        mutations = (
            ("== [('0', '0', '0', '0')]", "== [('1', '0', '0', '0')]", TEXT.replace('RELEASED device=0', 'RELEASED device=1')),
            ('len({state[:3] for state in states}) == 1', 'True', TEXT.replace('index=2 command=00000f02', 'index=2 command=00000f00')),
            ('not error & 0x80000000', 'not error & 0x40000000', TEXT.replace('error=00000100', 'error=80000100')),
            ('states[0][3] == states[3][3] == mask', 'True', TEXT.replace('value=80000000', 'value=00000000')),
        )
        for before, after, text in mutations:
            self.assertEqual(source.count(before), 1)
            namespace = {};exec(compile(source.replace(before, after), 'mutant-cycle.py', 'exec'), namespace)
            with self.assertRaises(AssertionError):
                with self.assertRaises(ValueError):
                    namespace['parse'](text)


if __name__ == '__main__':
    unittest.main()
