import os
import shutil
import subprocess
from pathlib import Path

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

    latest_recording = None

    if RECORDINGS_PATH.exists():

        recordings = list(
            RECORDINGS_PATH.glob("*.mp4")
        )

        if recordings:

            newest = max(
                recordings,
                key=lambda file:
                    file.stat().st_mtime
            )

            latest_recording = {
                "filename":
                    newest.name,

                "size_bytes":
                    newest.stat().st_size,

                "modified":
                    newest.stat().st_mtime
            }

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

    for recording in RECORDINGS_PATH.glob(
        "*.mp4"
    ):

        stat = recording.stat()

        recordings.append({
            "filename":
                recording.name,

            "size_bytes":
                stat.st_size,

            "modified":
                stat.st_mtime
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

@app.get("/recordings/{filename}")
def get_recording(filename: str):

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
        filename=recording.name
    )


# ---------------------------------------------------------
# Live HLS files
# ---------------------------------------------------------

app.mount(
    "/live",
    StaticFiles(
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