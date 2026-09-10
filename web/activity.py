"""Shared, read-only access to the recording activity index."""
import os
import sqlite3
from pathlib import Path
from contextlib import closing

DB_PATH = Path(os.environ.get('OWL_ACTIVITY_DB',
    str(Path(__file__).parent / 'dev_storage/events/activity.sqlite3') if os.name == 'nt'
    else '/srv/pi-security/storage/events/activity.sqlite3'))


def indexed_activity():
    if not DB_PATH.exists():
        return {}
    try:
        with closing(sqlite3.connect(DB_PATH.resolve().as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            return {row['filename']: dict(row) for row in db.execute('SELECT * FROM activity')}
    except sqlite3.Error:
        return {}


def activity_for(path, stat, index):
    row = index.get(path.name)
    if not row or row['size'] != stat.st_size or row['mtime_ns'] != stat.st_mtime_ns:
        return {'status': 'pending', 'first_motion_seconds': None}
    return {'status': row['status'], 'first_motion_seconds': row['first_motion_seconds']}
