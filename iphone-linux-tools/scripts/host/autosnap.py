#!/usr/bin/env python3
"""Opt-in foreground scheduler for private phone snapshots."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('O valor deve ser maior ou igual a 1.')
    return number


def read_status():
    path = ROOT / 'logs/autosnap-last.json'
    if not path.exists():
        return {'format': 1, 'last_success': None}
    state = json.loads(path.read_text())
    if not isinstance(state, dict) or state.get('format') != 1:
        raise ValueError('Estado do agendador inválido; inspecione logs/autosnap-last.json.')
    return state


def write_status(state):
    directory = ROOT / 'logs'
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    descriptor, name = tempfile.mkstemp(prefix='.autosnap-', dir=directory)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'w') as file:
            json.dump(state, file, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(directory / 'autosnap-last.json')
    finally:
        temporary.unlink(missing_ok=True)


def stop_job(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        return process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate()


def once(options):
    state = read_status()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    command = [sys.executable, str(ROOT / 'scripts/host/persist.py'),
               'automatic', '--keep', str(options.keep)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True)
    outcome = 'failed'
    try:
        output, error = process.communicate(timeout=options.timeout)
        if process.returncode == 0:
            outcome = 'success'
    except subprocess.TimeoutExpired:
        output, error = stop_job(process)
        outcome = 'timeout'
    except BaseException:
        stop_job(process)
        raise
    if output:
        print(output, end='', flush=True)
    if error:
        print(error, end='', file=sys.stderr, flush=True)
    state.update(started_at=started, finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 outcome=outcome, returncode=process.returncode)
    if outcome == 'success':
        matches = re.findall(r'^Snapshot: (\d{8}T\d{6}Z-[a-f0-9]{8})$', output, re.MULTILINE)
        if len(matches) != 1:
            raise ValueError('Job concluiu sem identificador único de snapshot.')
        state['last_success'] = matches[0]
    write_status(state)
    print('Agendador:', outcome, flush=True)
    return 0 if outcome == 'success' else 1


def cancelled(_signal, _frame):
    raise KeyboardInterrupt


def main():
    signal.signal(signal.SIGTERM, cancelled)
    signal.signal(signal.SIGHUP, cancelled)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('once', 'watch', 'status'))
    parser.add_argument('--interval', type=positive, default=300)
    parser.add_argument('--keep', type=positive, default=12)
    parser.add_argument('--timeout', type=positive, default=300)
    parser.add_argument('--cycles', type=positive)
    options = parser.parse_args()
    os.umask(0o077)
    if options.mode == 'status':
        print(json.dumps(read_status(), indent=2))
        return 0
    if options.mode == 'once':
        return once(options)
    completed = 0
    result = 0
    while True:
        result = max(result, once(options))
        completed += 1
        if options.cycles is not None and completed >= options.cycles:
            return result
        time.sleep(options.interval)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('Agendador encerrado; nenhum job será reiniciado.')
        raise SystemExit(130)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
