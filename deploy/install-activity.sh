#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
test "$(id -u)" = 0 || { echo 'Run with sudo.'; exit 1; }
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
test -x /usr/bin/python3
id admin >/dev/null
mountpoint -q /srv/pi-security/storage
backup=$(mktemp -d /var/backups/pi-security-activity.XXXXXXXX)
for file in /usr/local/lib/pi-security/scan_recordings.py /etc/systemd/system/pi-security-activity.service /etc/systemd/system/pi-security-activity.timer; do
    if test -f "$file"; then cp -p "$file" "$backup/"; fi
done
install -d /usr/local/lib/pi-security /etc/pi-security
if ! test -d /srv/pi-security/storage/events; then
    install -d -o admin -g admin -m 0755 /srv/pi-security/storage/events
fi
sudo -u admin test -w /srv/pi-security/storage/events
if ! test -f /etc/pi-security/activity.env; then
    printf '%s\n' 'MOTION_PIXEL_DELTA=25' 'MOTION_FRACTION=0.03' 'MOTION_CONSECUTIVE=3' 'MOTION_BATCH=5' > /etc/pi-security/activity.env
fi
install -m 0755 motion/scan_recordings.py /usr/local/lib/pi-security/scan_recordings.py
install -m 0644 web/recording_files.py /usr/local/lib/pi-security/recording_files.py
install -m 0644 systemd/pi-security-activity.service systemd/pi-security-activity.timer /etc/systemd/system/
systemd-analyze verify /etc/systemd/system/pi-security-activity.service /etc/systemd/system/pi-security-activity.timer
systemctl daemon-reload
systemctl enable --now pi-security-activity.timer
systemctl start --no-block pi-security-activity.service
echo "Activity scan queued. Installer backups: $backup"
systemctl list-timers pi-security-activity.timer --no-pager
