#!/usr/bin/env python3
"""Compile the release selector and require assertions for every mutant."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'phone/kernel/n71-hdq-release-plan.h'
MUTATIONS = (
    ('reverse-mode', 'software_mode == 1', 'software_mode == 0'),
    ('always-handshake', 'input->cached_mask ?', '1 ?'),
    ('always-final', 'battery_alert_present && !(input->status7 & 0x80)', 'battery_alert_present || !(input->status7 & 0x80)'),
    ('reverse-status', '!(input->status7 & 0x80)', '!!(input->status7 & 0x80)'),
    ('wrong-status-bit', 'status7 & 0x80', 'status7 & 0x40'),
    ('skip-final', 'plan.action = N71_HDQ_RELEASE_ACK_FINAL;', 'plan.action = N71_HDQ_RELEASE_ACK;'),
    ('zero-is-final', 'plan.action = N71_HDQ_RELEASE_WRITE_ZERO;', 'plan.action = N71_HDQ_RELEASE_ACK_FINAL;'),
    ('clear-wrong-event', '~0x40U', '~0x20U'),
    ('drop-mask', 'plan.disable_event_mask = input->cached_mask;', 'plan.disable_event_mask = 0;'),
    ('ignore-mode-range', 'software_mode > 1', 'software_mode > 2'),
    ('ignore-mask-range', 'cached_mask > 0xff', 'cached_mask > 0x1ff'),
    ('ignore-alert-range', 'battery_alert_present > 1', 'battery_alert_present > 2'),
    ('ignore-status-range', 'status7 > 0xff', 'status7 > 0x1ff'),
    ('ignore-status-validity', 'status_valid != 1', 'status_valid > 2'),
)


def main():
    compiler = shutil.which('cc')
    if compiler is None:
        raise RuntimeError('Native compiler required; no passing gate.')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = HEADER.read_text()
    with tempfile.TemporaryDirectory(prefix='n71-hdq-release-') as directory:
        folder = Path(directory)
        binary = folder / 'contract'
        for name, before, after in (('baseline', None, None),) + MUTATIONS:
            if before is not None and source.count(before) != 1:
                raise ValueError('Mutation anchor not unique: ' + name)
            (folder / HEADER.name).write_text(
                source if before is None else source.replace(before, after, 1))
            result = subprocess.run(
                [compiler, '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                 '-I', str(folder), str(ROOT / 'tests/n71_hdq_release_plan.c'), '-o', str(binary)],
                capture_output=True, text=True, timeout=30, env=dict(os.environ, LC_ALL='C'))
            if result.returncode:
                raise RuntimeError('Compilation is not assertion proof: ' + name + result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20,
                                    cwd=folder, env=dict(os.environ, LC_ALL='C'))
            if before is None:
                if result.returncode or 'N71_HDQ_RELEASE_PLAN_OK' not in result.stdout:
                    raise RuntimeError('Baseline failed: ' + result.stderr)
            elif result.returncode != -signal.SIGABRT or 'assert' not in result.stderr.lower():
                raise RuntimeError('Missing assertion kill: ' + name + result.stderr)
            else:
                print('N71_HDQ_RELEASE_ASSERTION_KILL ' + name, flush=True)
    print('N71_HDQ_RELEASE_MUTATION_GATE_OK ' + str(len(MUTATIONS)))


if __name__ == '__main__':
    main()
