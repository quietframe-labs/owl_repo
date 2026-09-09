# Owl

Changes flow from the PC checkout to GitHub, then to Owl's checkout.
The web service runs from `/srv/pi-security/web`. A Git pull in a separate
checkout does not update that running directory until the installer runs.

For the live-view cache and recovery update:

1. On the PC, test and commit the intended files, then push to GitHub.
2. On Owl, enter its existing repository checkout and inspect `git status`.
   Preserve any local changes before pulling; do not use a hard reset.
3. Run `git pull --ff-only`.
4. Run `sudo sh deploy/install-live-view.sh` from that checkout.
5. Refresh `/live-view/` with Ctrl+F5.

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
