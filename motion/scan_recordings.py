#!/usr/bin/env python3
"""Low-resolution frame differences on closed MP4s. No camera credentials needed."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import hashlib
import math
import re
from recording_files import complete_mp4, open_writers

RECORDINGS = Path('/srv/pi-security/storage/recordings/camera01')
DB_PATH = Path('/srv/pi-security/storage/events/activity.sqlite3')
WIDTH, HEIGHT, FPS = 160, 90, 2
VERSION = 1


def detect(raw, pixel_delta=25, fraction=0.03, consecutive=3):
    frame_size = WIDTH * HEIGHT
    if len(raw) < frame_size * 2 or len(raw) % frame_size:
        raise ValueError('No complete decodable video frames')
    previous = raw[:frame_size]
    run = 0
    first = None
    for offset in range(frame_size, len(raw), frame_size):
        frame = raw[offset:offset + frame_size]
        changed = sum(abs(a - b) >= pixel_delta for a, b in zip(previous, frame))
        run = run + 1 if changed / frame_size >= fraction else 0
        if run >= consecutive and first is None:
            first = max(0, (offset // frame_size - consecutive + 1) / FPS)
        previous = frame
    return first


def scan(path, config):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'json', str(path)], capture_output=True, timeout=20, check=True)
    duration = float(json.loads(probe.stdout)['format']['duration'])
    if not math.isfinite(duration) or not 0 < duration <= 900:
        raise ValueError('Expected a completed recording up to 15 minutes')
    result = subprocess.run([
        'ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-threads', '1',
        '-filter_threads', '1', '-i', str(path), '-an', '-sn', '-dn',
        '-vf', f'fps={FPS},scale={WIDTH}:{HEIGHT},format=gray',
        '-t', '900', '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1',
    ], capture_output=True, timeout=600, check=True)
    first = detect(result.stdout, **config)
    return first, duration


def thumbnail(path, seconds, destination):
    temporary = destination.with_suffix('.tmp.jpg')
    try:
        subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-threads', '1', '-filter_threads', '1', '-ss', str(seconds), '-i', str(path),
            '-frames:v', '1', '-vf', 'scale=480:-2', '-q:v', '3', '-y', str(temporary)],
            capture_output=True, timeout=60, check=True)
        if not temporary.stat().st_size:
            raise ValueError('Empty thumbnail')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    import fcntl
    pixel_delta = int(os.environ.get('MOTION_PIXEL_DELTA', '25'))
    fraction = float(os.environ.get('MOTION_FRACTION', '0.03'))
    consecutive = int(os.environ.get('MOTION_CONSECUTIVE', '3'))
    batch = int(os.environ.get('MOTION_BATCH', '5'))
    if not (1 <= pixel_delta <= 255 and 0 < fraction <= 1 and 1 <= consecutive <= 60 and 1 <= batch <= 10):
        raise ValueError('Invalid motion configuration')
    config = dict(pixel_delta=pixel_delta, fraction=fraction, consecutive=consecutive)
    signature = json.dumps([VERSION, config], sort_keys=True)
    if not os.path.ismount('/srv/pi-security/storage'):
        raise RuntimeError('Recording SSD is not mounted')
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with (DB_PATH.parent / 'activity.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with sqlite3.connect(DB_PATH, timeout=10) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS activity (
                filename TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER,
                status TEXT, first_motion_seconds REAL, checked REAL, config TEXT,
                thumbnail TEXT, duration REAL)''')
            thumbnails = DB_PATH.parent / 'thumbnails'
            thumbnails.mkdir(exist_ok=True)
            writers = open_writers()
            files = []
            for path in RECORDINGS.glob('*.mp4'):
                try:
                    stat = path.stat()
                    files.append((path, stat))
                except FileNotFoundError:
                    continue
            files.sort(key=lambda item: item[1].st_mtime, reverse=True)
            count = 0
            for path, before in files:
                age = time.time() - before.st_mtime
                if not before.st_size or age < 30 or not complete_mp4(path, writers):
                    continue
                row = db.execute('SELECT size,mtime_ns,status,checked,config,thumbnail FROM activity WHERE filename=?', (path.name,)).fetchone()
                if row and row[0:2] == (before.st_size, before.st_mtime_ns) and row[4] == signature:
                    if (row[2] != 'error' and row[5] and (thumbnails / row[5]).exists()) or (row[2] == 'error' and time.time() - row[3] < 3600):
                        continue
                first, status, duration, thumb = None, 'error', None, None
                try:
                    first, duration = scan(path, config)
                    thumb = hashlib.sha256(f'{path.name}:{before.st_size}:{before.st_mtime_ns}:{signature}'.encode()).hexdigest() + '.jpg'
                    thumbnail(path, min(duration / 2 if first is None else first + 0.5, max(0, duration - 0.1)), thumbnails / thumb)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        continue
                    status = 'motion' if first is not None else 'quiet'
                except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                    print(f'ERROR {path.name}: {type(error).__name__}', flush=True)
                db.execute('INSERT OR REPLACE INTO activity VALUES (?,?,?,?,?,?,?,?,?)',
                    (path.name, before.st_size, before.st_mtime_ns, status, first, time.time(), signature, thumb if status != 'error' else None, duration))
                db.commit()
                print(f'{path.name}: {status}; first motion={first}', flush=True)
                count += 1
                if count >= batch:
                    break
            existing = {p.name for p, _ in files}
            for (filename,) in db.execute('SELECT filename FROM activity').fetchall():
                if filename not in existing:
                    db.execute('DELETE FROM activity WHERE filename=?', (filename,))
            referenced = {row[0] for row in db.execute('SELECT thumbnail FROM activity WHERE thumbnail IS NOT NULL')}
            for image in thumbnails.glob('*.jpg'):
                if re.fullmatch(r'[a-f0-9]{64}\.jpg', image.name) and image.name not in referenced:
                    image.unlink(missing_ok=True)
            print(f'Scan complete: {count} recordings processed', flush=True)


if __name__ == '__main__':
    main()
