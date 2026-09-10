# Owl

To install UI changes after they are pushed to GitHub, run on Owl:

```sh
cd /srv/pi-security/app/owl_repo &&
git pull --ff-only &&
sudo sh deploy/update-ui.sh
```

This publishes the updated stylesheet to the existing collected static directory
and restarts the web service. Refresh the browser with Ctrl+F5. Changes that add
other static assets require Django's `collectstatic` using the service's Python
environment; this UI helper only publishes the app stylesheet.

Changes flow from the PC checkout to GitHub, then to Owl's checkout.
Owl's checkout is `/srv/pi-security/app/owl_repo`, and its web service runs
from that checkout's `web` directory. The installer reads the service's
`WorkingDirectory` so it does not accidentally update the legacy
`/srv/pi-security/web` installation.

For the live-view cache and recovery update:

1. On the PC, test and commit the intended files, then push to GitHub.
2. On Owl, enter its existing repository checkout and inspect `git status`.
   Preserve any local changes before pulling; do not use a hard reset.
3. Run `git pull --ff-only`.
4. Run `sudo sh deploy/install-live-view.sh` from that checkout.
5. Refresh `/live-view/` with Ctrl+F5.

The HTTP check uses `http://owl:8000/live/camera01/index.m3u8`, since the web
service may bind only to its Tailscale address. To check a different confirmed
address, pass its full playlist URL as the installer's first argument.
The check retries to allow time for the web service to start.

The installer backs up the two production files under
`/var/backups/pi-security-live-view.*`, restarts the web service, and checks
that HLS responses contain `Cache-Control: no-store`. It restores the backed-up
files if the restart or HTTP check fails. If the checkout is the production
directory, Git has already changed those files before installation; use Git's
history when an earlier revision is needed.

Local regression checks (requires project dependencies plus `httpx`):

```powershell
cd web
python -m unittest test_live_cache -v
node test_live_player.cjs
```

These changes affect caching, reconnection, and playback status, not the page's
appearance. The watchdog is separately installed as systemd service/timer files.
