# Owl activity detection and archive views
## 2026-09-09 — Motion activity, thumbnails, and service source control

### What changed
- Activity (/activity/) shows completed, indexed clips containing detected visual motion.
- All recordings (/recordings/) shows all completed, indexed clips, grouped by day, with filename/title search and a day filter.
- Every tile has a real image: a frame near the first sustained motion when activity is detected, otherwise a frame from the middle of the clip.
- Activity playback starts about two seconds before the first detected motion.
- Unfinished files are hidden, including from the dashboard's latest recording. A finalized MP4, a matching scan fingerprint, and successful thumbnail generation are required before a clip is listed.
- During the initial backlog scan, completed clips appear gradually; unscanned clips do not count as quiet.
- Display titles differ from filenames. Example: Camera 01 · 4:30:00 PM under Wednesday, September 09, 2026 maps to 2026-09-09_16-30-00.mp4. Original files are NOT renamed or moved. The filename remains visible below the title and is used for downloads. Times come from the filename's camera/Pi-local timestamp; files with unusual names fall back to modification time.

### How motion detection works
The Pi scans existing completed MP4s, not another RTSP stream. FFmpeg decodes grayscale frames at 160×90 and 2 frames/second. A default motion match requires at least 3% of pixels to change by 25 brightness levels for 3 consecutive frame comparisons. It stores the first motion offset and a thumbnail. This is general visual motion: shadows, headlights, rain, and moving plants can trigger it. It is not person/vehicle recognition.

Normal clips are around 5 minutes. The worker rejects recordings longer than 15 minutes instead of silently scanning only part of them. Broken files are logged as errors and retried after an hour. Files changing during scanning are not published.

The timer queues up to 5 clips per run, newest first, then waits 1 minute after completion. It runs as admin with low CPU/I/O priority and a 50% CPU quota. Initial indexing may take time. The recorder and live service continue independently.

### Install this update on Owl
These commands are for the Owl SSH terminal, not Windows PowerShell:

```bash
cd /srv/pi-security/app/owl_repo &&
git pull --ff-only &&
sudo sh deploy/install-activity.sh &&
sudo sh deploy/update-ui.sh
```

FFmpeg, ffprobe, and system Python 3 must already be installed. No new camera password or AI dependency is required. The SSD must be mounted. The installer queues scanning without waiting for the entire backlog. Refresh the browser with Ctrl+F5, then reload periodically as clips finish scanning.

### Verify and inspect
```bash
systemctl status pi-security-activity.timer --no-pager
systemctl status pi-security-activity.service --no-pager
sudo journalctl -u pi-security-activity.service -n 40 --no-pager
curl -s http://owl:8000/api/activity/status
pi-security-status
```

A oneshot activity service can be inactive between successful scans; the timer should remain enabled. The status API lists motion, quiet, pending (including active recording), and error counts. “Pending” does not imply no activity. If all recordings disappear immediately after installation, allow indexing to complete and check this status and the journal.

### Tune sensitivity
Edit on Owl:

```bash
sudo nano /etc/pi-security/activity.env
```

Defaults:
```ini
MOTION_PIXEL_DELTA=25
MOTION_FRACTION=0.03
MOTION_CONSECUTIVE=3
MOTION_BATCH=5
```

Lower MOTION_FRACTION makes the detector more sensitive; increasing it reduces small-motion triggers. Raising MOTION_CONSECUTIVE rejects brief changes. Adjust carefully and compare actual clips. The configuration is reread on each run. A changed sensitivity signature causes rescanning over subsequent batches. Previously indexed results remain visible until rescanned.

Start a scan:
```bash
sudo systemctl start --no-block pi-security-activity.service
```

Pause future scanning:
```bash
sudo systemctl stop pi-security-activity.timer
```

An already running scan finishes unless the service is also stopped. Resume:
```bash
sudo systemctl start pi-security-activity.timer
```

### Files and data
- motion/scan_recordings.py: detector, batch scanning, thumbnail extraction.
- web/recording_files.py: finalized MP4 and open-writer checks.
- web/activity.py: read-only index access.
- web/main.py: indexed recording list, readable metadata, thumbnails, status API.
- systemd/pi-security-activity.service and .timer: installed by deploy/install-activity.sh.
- /srv/pi-security/storage/events/activity.sqlite3: derived activity index.
- /srv/pi-security/storage/events/thumbnails/: generated JPEGs.
- /etc/pi-security/activity.env: sensitivity settings outside Git.
- /usr/local/lib/pi-security/scan_recordings.py and recording_files.py: installed worker copies.

After changing worker code or activity units in Git, rerun deploy/install-activity.sh. A Git pull alone does not update these installed copies. Deleted recordings' index entries and unused generated thumbnails are cleaned on subsequent scans; source recordings are never deleted by this worker.

### Pi Security services in Git
The new activity units and the existing watchdog units are now tracked in systemd/. The watchdog Python source is in monitoring/. Owl's existing recorder/live/web/retention/storage-monitor units still need an export from the actual Pi before they can be committed accurately. Do not replace them with examples from old notes.

To create a redacted inventory:
```bash
cd /srv/pi-security/app/owl_repo
python3 deploy/export-services.py
less /tmp/owl-services-redacted.txt
```

Review before sharing; redaction is best-effort. The report is NOT installable. Inline environment values and secret-bearing directives are omitted; RTSP URLs are replaced with placeholders. Keep actual camera credentials outside Git under /etc/pi-security. Once reviewed, convert real units to credential-free templates and commit through the PC → GitHub → Owl workflow.

### Later: person and vehicle recognition
The desktop can run an offline object detector on motion clips and return labels keyed by the original filename plus file fingerprint. Owl can keep recording and serving video while the desktop does the heavy work. Add separate person/vehicle labels and confidence later; current motion results must not be described as object recognition.

### Validation
Local checks covered stationary vs moving synthetic frames, sustained-motion thresholds, unfinished MP4 exclusion, open-writer exclusion, stale fingerprint exclusion, readable names, inline/download byte-range responses, and existing watchdog tests. A local browser preview verified Activity filtering, day groups, and thumbnail display. Live installation, workload tuning, and real-camera detection accuracy require checks on Owl after pulling.
