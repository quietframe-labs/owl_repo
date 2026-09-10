Updated: 2026-09-09
Related: [[Projects/owl/Commands|Commands]] · [[Projects/owl/Workflow|Workflow]]

## The workflow
Edit in VS Code on the PC → test → commit → push to GitHub → pull on Owl → publish changed static files when needed → restart → verify.

GitHub repository: https://github.com/quietframe-labs/owl_repo
PC checkout: C:\dev\owl_repo
Owl checkout: /srv/pi-security/app/owl_repo
Running web directory: /srv/pi-security/app/owl_repo/web
Website: http://owl:8000
SSH: admin@owl (Tailscale must be connected)

The old /srv/pi-security/web directory is NOT the running Django app. Running git in /srv/pi-security gives “not a git repository.” Use the full checkout path above.

## 1. Make and test changes on the PC
Open C:\dev\owl_repo in VS Code. Save your changes. In PowerShell:

```powershell
cd C:\dev\owl_repo
git status
git diff
.\.venv\Scripts\python.exe web/manage.py check
.\.venv\Scripts\python.exe -m unittest discover -s web -p "test_*.py"
```

The tests require the project dependencies plus httpx in the virtual environment. The optional player regression check also needs Node.js:

```powershell
node web/test_live_player.cjs
```

In VS Code Source Control, stage only the intended files, write a descriptive message, and commit. Then:

```powershell
git push origin main
```

Do not commit passwords, RTSP credentials, .env files, databases, video files, or virtual environments. If push says 403, authenticate with a GitHub account that has write access to quietframe-labs/owl_repo. Never force-push just to bypass a rejection.

## 2. Update Owl
Connect from PowerShell:

```powershell
ssh admin@owl
```

Enter the password at the SSH prompt. On Owl, check for local edits first:

```bash
cd /srv/pi-security/app/owl_repo
git status --short
git log -1 --oneline
```

If status shows edits, preserve and reconcile them before pulling. Do not use git reset --hard or git clean to clear an error.

For ordinary Python/template changes:

```bash
cd /srv/pi-security/app/owl_repo &&
git pull --ff-only &&
sudo systemctl restart pi-security-web.service
```

For the current UI/recording-tile updates, which also change app.css:

```bash
cd /srv/pi-security/app/owl_repo &&
git pull --ff-only &&
sudo sh deploy/update-ui.sh
```

The UI helper backs up the existing collected app.css under /var/backups/pi-security-ui.*, publishes the updated CSS into web/staticfiles, and restarts the web service. It only publishes app.css. New JS/images or other static assets need Django collectstatic using the service's Python environment. Dependency/model/systemd changes may additionally need package installation, migrations, or daemon-reload; inspect the change before deploying.

Refresh the browser with Ctrl+F5.

## 3. Verify
On Owl:

```bash
systemctl status pi-security-web.service --no-pager
sudo journalctl -u pi-security-web.service -n 40 --no-pager
pi-security-status
git log -1 --oneline
```

Compare that commit with the PC or GitHub. Open Live View and confirm the camera timestamp keeps advancing. Open Recordings, filter by filename/date, select View, play and seek, then test Download.

## Recording tiles and viewer
Each recording has a play-icon tile, a primary View action, and a secondary Download link. View opens the on-page HTML video player with playback controls. Close player stops it and returns focus to the tile.

The media endpoint /recordings/{filename} sends video/mp4 with inline disposition. Adding ?download=true sends attachment disposition. HTTP byte ranges let the player seek without downloading the whole clip.

Tiles use icons, not extracted image thumbnails. A still-open recording or a browser-incompatible camera codec may not play; select a completed older clip or download it. The update does not transcode video.

Files to edit:
- web/dashboard_app/templates/dashboard_app/recordings.html: tiles, search, player, download links.
- web/dashboard_app/static/dashboard_app/css/app.css: styling.
- web/main.py: media response and byte-range-compatible file serving.
- web/test_recording_media.py: inline/download/seek checks.

## Live-view troubleshooting
If old footage plays once and buffers, confirm that HLS files are fresh and refresh the browser cache. The live player reconnects after stalls. Check:

```bash
curl -I http://owl:8000/live/camera01/index.m3u8
```

Expected: HTTP 200 and Cache-Control: no-store, max-age=0. HTTP 200 alone does not prove freshness.

The live-view-specific installer is:

```bash
sudo sh deploy/install-live-view.sh
```

It reads the service WorkingDirectory, backs up its target files, restarts the service, and checks HLS headers using the Owl hostname. It retries during startup. Its file restore does not undo a Git pull that already changed files in the live checkout. Use Git history/revert for a previous code revision.

## Watchdog
Checks run about every 15–16 seconds.
- Recorder restart threshold: newest recording older than 600 seconds.
- Live restart threshold: playlist OR newest segment older than 30 seconds.
- Startup grace periods and restart cooldowns avoid tight restart loops.
- Actions are logged in the system journal.
- pi-security-status distinguishes HEALTHY from ACTIVE-but-stale.

```bash
systemctl is-enabled pi-security-watchdog.timer
systemctl list-timers pi-security-watchdog.timer --no-pager
sudo journalctl -u pi-security-watchdog.service -n 30 --no-pager
```

Paths:
- Recordings: /srv/pi-security/storage/recordings/camera01
- HLS: /srv/pi-security/live/camera01
- Health script: /usr/local/lib/pi-security/pi-security-health.py
- Units: /etc/systemd/system/pi-security-watchdog.service and .timer
- Original status helper backup: /usr/local/lib/pi-security/pi-security-status-original

Manual recovery, when output really is stale:

```bash
sudo systemctl restart pi-security-recorder.service
sudo systemctl restart pi-security-live.service
```

These briefly interrupt their respective streams.

## Tailscale and deployment pitfalls
Use tailscale ip -4 ON OWL to confirm its current IP. During this session the PC resolved owl to 100.72.103.117; the supplied 100.88.233.122 timed out. Do not assume those addresses stay unchanged. Prefer the working hostname.

A service bound only to Tailscale may not answer at 127.0.0.1:8000. One installer falsely reported failure for this reason, although the new code was running.

If the page looks unchanged:
1. Verify the Git commit on Owl.
2. Check systemctl show pi-security-web.service -p WorkingDirectory --no-pager.
3. Publish the CSS with deploy/update-ui.sh.
4. Restart and refresh with Ctrl+F5.
5. Read journal errors before retrying blindly.

If a pushed change must be undone, use git revert on the PC, push the revert, then pull and redeploy on Owl. For a specific older commit, inspect the history and select the intended revision; avoid blindly reverting HEAD when other changes have been made.

## Change log
2026-09-09: Watchdog installed; live cache/reconnection fixed; deployment standardized through GitHub; UI refreshed; recording icon tiles, in-page player, and separate downloads added. Verify the newest change on Owl after pulling.
