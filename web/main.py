import os
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from activity import indexed_activity, activity_for, DB_PATH as ACTIVITY_DB
from recording_files import complete_mp4, open_writers

from a2wsgi import WSGIMiddleware
from django.conf import settings as django_settings
from django.core.wsgi import get_wsgi_application
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


# ---------------------------------------------------------
# Django setup
# ---------------------------------------------------------

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "dashboard.settings"
)

django_wsgi_app = get_wsgi_application()


# ---------------------------------------------------------
# FastAPI setup
# ---------------------------------------------------------

app = FastAPI(
    title="Pi Security API",
    version="0.1.0"
)


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

if os.name == "nt":
    # Windows development paths
    STORAGE_PATH = BASE_DIR / "dev_storage"
    RECORDINGS_PATH = STORAGE_PATH / "recordings" / "camera01"
    LIVE_PATH = BASE_DIR / "dev_live"
else:
    # Raspberry Pi production paths
    STORAGE_PATH = Path("/srv/pi-security/storage")
    RECORDINGS_PATH = (
        STORAGE_PATH / "recordings" / "camera01"
    )
    LIVE_PATH = Path("/srv/pi-security/live")


# Create development directories if necessary
if os.name == "nt":
    STORAGE_PATH.mkdir(
        parents=True,
        exist_ok=True
    )

    RECORDINGS_PATH.mkdir(
        parents=True,
        exist_ok=True
    )

    LIVE_PATH.mkdir(
        parents=True,
        exist_ok=True
    )


# ---------------------------------------------------------
# Pi systemd service helper
# ---------------------------------------------------------

def service_active(service_name: str) -> bool:

    # systemctl does not exist on Windows
    if os.name == "nt":
        return False

    result = subprocess.run(
        [
            "systemctl",
            "is-active",
            service_name
        ],
        capture_output=True,
        text=True
    )

    return result.stdout.strip() == "active"


# ---------------------------------------------------------
# API: System status
# ---------------------------------------------------------

@app.get("/api/status")
def system_status():

    usage = shutil.disk_usage(STORAGE_PATH)

    completed = list_recordings()
    latest_recording = completed[0] if completed else None

    return {

        "storage": {
            "mounted":
                (
                    STORAGE_PATH.is_mount()
                    if os.name != "nt"
                    else STORAGE_PATH.exists()
                ),

            "total_bytes":
                usage.total,

            "used_bytes":
                usage.used,

            "free_bytes":
                usage.free,

            "percent_used":
                round(
                    (
                        usage.used
                        / usage.total
                    ) * 100,
                    2
                )
        },

        "services": {

            "recorder":
                service_active(
                    "pi-security-recorder.service"
                ),

            "retention_timer":
                service_active(
                    "pi-security-retention.timer"
                ),

            "storage_monitor_timer":
                service_active(
                    "pi-security-storage-monitor.timer"
                ),

            "live_stream":
                service_active(
                    "pi-security-live.service"
                )
        },

        "latest_recording":
            latest_recording
    }


# ---------------------------------------------------------
# API: Recording list
# ---------------------------------------------------------

@app.get("/api/recordings")
def list_recordings():

    if not RECORDINGS_PATH.exists():
        return []

    recordings = []
    activity_index = indexed_activity()
    writers = open_writers()

    for recording in RECORDINGS_PATH.glob(
        "*.mp4"
    ):

        try:
            stat = recording.stat()
        except FileNotFoundError:
            continue
        activity = activity_for(recording, stat, activity_index)
        row = activity_index.get(recording.name, {})
        if activity['status'] not in ('motion', 'quiet') or not row.get('thumbnail') or not complete_mp4(recording, writers):
            continue
        try:
            recorded_at = datetime.strptime(recording.stem, '%Y-%m-%d_%H-%M-%S')
        except ValueError:
            recorded_at = datetime.fromtimestamp(stat.st_mtime)

        recordings.append({
            "filename":
                recording.name,

            "size_bytes":
                stat.st_size,

            "modified":
                stat.st_mtime,
            "day": recorded_at.strftime('%Y-%m-%d'),
            "day_label": recorded_at.strftime('%A, %B %d, %Y'),
            "display_title": 'Camera 01 · ' + recorded_at.strftime('%I:%M:%S %p').lstrip('0'),
            "recorded_at": recorded_at.isoformat(),
            "activity": activity,
            "thumbnail_url": '/api/activity/thumbnail/' + row['thumbnail']
        })

    recordings.sort(
        key=lambda item:
            item["modified"],
        reverse=True
    )

    return recordings


# ---------------------------------------------------------
# API: Serve recording
# ---------------------------------------------------------

@app.get('/api/activity/thumbnail/{filename}')
def activity_thumbnail(filename: str):
    import re
    if not re.fullmatch(r'[a-f0-9]{64}\.jpg', filename):
        raise HTTPException(status_code=404)
    path = ACTIVITY_DB.parent / 'thumbnails' / filename
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type='image/jpeg')


@app.get('/api/activity/status')
def activity_status():
    index = indexed_activity()
    counts = {'motion': 0, 'quiet': 0, 'pending': 0, 'error': 0}
    for path in RECORDINGS_PATH.glob('*.mp4'):
        try:
            state = activity_for(path, path.stat(), index)['status']
            counts[state] = counts.get(state, 0) + 1
        except FileNotFoundError:
            continue
    return {'counts': counts, 'installed': ACTIVITY_DB.exists()}


@app.get("/recordings/{filename}")
def get_recording(filename: str, download: bool = False):

    recording = (
        RECORDINGS_PATH / filename
    ).resolve()

    if (
        recording.parent
        != RECORDINGS_PATH.resolve()
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename"
        )

    if not recording.exists():
        raise HTTPException(
            status_code=404,
            detail="Recording not found"
        )

    if recording.suffix.lower() != ".mp4":
        raise HTTPException(
            status_code=400,
            detail="Invalid recording type"
        )

    return FileResponse(
        recording,
        media_type="video/mp4",
        filename=recording.name,
        content_disposition_type="attachment" if download else "inline"
    )


# ---------------------------------------------------------
# Live HLS files
# ---------------------------------------------------------

class LiveStaticFiles(StaticFiles):
    """FFmpeg reuses segment names after restart; never reuse cached output."""

    def is_not_modified(self, response_headers, request_headers):
        return False

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response


app.mount(
    "/live",
    LiveStaticFiles(
        directory=str(LIVE_PATH),
        check_dir=False
    ),
    name="live"
)


# ---------------------------------------------------------
# Django static files
# ---------------------------------------------------------

app.mount(
    "/static",
    StaticFiles(
        directory=str(
            django_settings.STATIC_ROOT
        ),
        check_dir=False
    ),
    name="django-static"
)


# ---------------------------------------------------------
# Django
#
# MUST stay last because "/" catches everything
# not matched by FastAPI above.
# ---------------------------------------------------------

app.mount(
    "/",
    WSGIMiddleware(
        django_wsgi_app
    )
)
