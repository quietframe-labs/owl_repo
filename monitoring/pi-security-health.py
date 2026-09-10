#!/usr/bin/env python3
"""Output freshness is authoritative; a running FFmpeg alone is not healthy."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

RECORDINGS = Path('/srv/pi-security/storage/recordings/camera01')
HLS = Path('/srv/pi-security/live/camera01')
STATE = Path('/run/pi-security-watchdog/restarts.json')
SERVICES = [('pi-security-recorder.service', 600), ('pi-security-live.service', 30)]


def newest_age(directory, pattern, now):
    newest = None
    for path in directory.glob(pattern):
        try:
            stat = path.stat()
            if path.is_file() and stat.st_size > 0:
                newest = max(newest or stat.st_mtime, stat.st_mtime)
        except FileNotFoundError:  # HLS rotates files while being inspected.
            continue
    return None if newest is None else max(0, now - newest)


def output_ages(now):
    return [
        {'recording': newest_age(RECORDINGS, '*.mp4', now)},
        {'playlist': newest_age(HLS, 'index.m3u8', now),
         'segment': newest_age(HLS, '*.ts', now)},
    ]


def service_info(unit):
    result = subprocess.run(['systemctl', 'show', unit,
                             '--property=LoadState,ActiveState,ActiveEnterTimestampMonotonic'],
                            check=True, capture_output=True, text=True, timeout=10)
    props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if props.get('LoadState') != 'loaded':
        raise RuntimeError(unit + ' is not loaded')
    entered = int(props.get('ActiveEnterTimestampMonotonic', '0')) / 1000000
    return props['ActiveState'], max(0, time.monotonic() - entered) if entered else None


def assessment(state, uptime, ages, limit):
    stale = any(age is None or age > limit for age in ages.values())
    if state == 'active' and not stale:
        return 'HEALTHY', False
    if state in ('activating', 'deactivating', 'reloading'):
        return state.upper(), False
    if state == 'active' and uptime is not None and uptime < limit:
        return 'STARTING (output missing or stale; startup grace)', False
    return ('ACTIVE-but-stale' if state == 'active' else state.upper()), True


def log(message):
    print(time.strftime('%Y-%m-%dT%H:%M:%S%z') + ' ' + message, flush=True)


def run(watchdog=False):
    now = time.time()
    attempts = {}
    if watchdog:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        if STATE.exists():
            attempts = json.loads(STATE.read_text())
    unhealthy = False
    ages_by_service = output_ages(now)
    for (unit, limit), ages in zip(SERVICES, ages_by_service):
        try:
            state, uptime = service_info(unit)
            label, restart = assessment(state, uptime, ages, limit)
            detail = ', '.join(f'{key} age=' + ('MISSING' if age is None else f'{age:.0f}s')
                               for key, age in ages.items())
            message = f'{unit}: {label}; state={state}; {detail}; limit={limit}s'
            unhealthy |= label != 'HEALTHY'
            if not watchdog:
                print(message)
            elif restart and time.monotonic() - attempts.get(unit, -1e12) >= limit:
                log('RESTART requested: ' + message)
                attempts[unit] = time.monotonic()
                temporary = STATE.with_suffix('.tmp')
                temporary.write_text(json.dumps(attempts))
                temporary.replace(STATE)
                result = subprocess.run(['systemctl', 'restart', unit], timeout=90,
                                        capture_output=True, text=True)
                log(('RESTART completed: ' if result.returncode == 0 else 'ERROR restart failed: ')
                    + unit + f' (exit={result.returncode})')
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            unhealthy = True
            log(f'ERROR {unit}: {error}')
    return 1 if unhealthy and not watchdog else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--watchdog', action='store_true')
    args = parser.parse_args()
    if args.watchdog:
        import fcntl
        STATE.parent.mkdir(parents=True, exist_ok=True)
        with (STATE.parent / 'lock').open('w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SystemExit(0)
            raise SystemExit(run(True))
    raise SystemExit(run())
