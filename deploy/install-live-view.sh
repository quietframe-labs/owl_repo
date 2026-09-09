#!/bin/sh
# Run from a Git checkout: sudo sh deploy/install-live-view.sh
set -eu
cd "$(dirname "$0")"
test "$(id -u)" = 0 || { echo 'Run this installer with sudo.'; exit 1; }
health_url=${1:-http://owl:8000/live/camera01/index.m3u8}
web=$(systemctl show pi-security-web.service --property=WorkingDirectory --value)
case "$web" in
    /*) ;;
    *) echo 'Web service has no absolute WorkingDirectory; stopping.' >&2; exit 1 ;;
esac
template=dashboard_app/templates/dashboard_app/live.html
test -f "$web/main.py"
test -f "$web/$template"
if test -f ../web/main.py; then
    source_main=../web/main.py
    source_live=../web/$template
else
    # Compatibility with the previously prepared standalone copy.
    source_main=main.py
    source_live=live.html
fi
test -f "$source_main"
test -f "$source_live"
python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read())' "$source_main"
systemctl cat pi-security-web.service >/dev/null
backup=$(mktemp -d /var/backups/pi-security-live-view.XXXXXXXX)
cp -p "$web/main.py" "$backup/main.py"
cp -p "$web/$template" "$backup/live.html"
cp "$source_main" "$backup/new-main.py"
cp "$source_live" "$backup/new-live.html"
echo "Backup saved in $backup"
rollback() {
    trap - EXIT
    cp -p "$backup/main.py" "$web/main.py"
    cp -p "$backup/live.html" "$web/$template"
    systemctl restart pi-security-web.service || true
    echo "Update failed; restored files from $backup" >&2
    exit 1
}
trap rollback EXIT
# Write in place to preserve existing file ownership and permissions.
cat "$backup/new-main.py" > "$web/main.py"
cat "$backup/new-live.html" > "$web/$template"
systemctl restart pi-security-web.service
sleep 2
systemctl is-active --quiet pi-security-web.service
echo "Checking live output at $health_url"
verified=false
for attempt in 1 2 3 4 5; do
    if curl --fail --silent --show-error --max-time 5 -I "$health_url" \
        > "$backup/response-headers.txt" && \
        grep -qi '^cache-control:.*no-store' "$backup/response-headers.txt"; then
        verified=true
        break
    fi
    sleep 2
done
if test "$verified" != true; then
    echo "Could not verify updated HLS headers at $health_url" >&2
    exit 1
fi
trap - EXIT
echo 'Live-view update installed. Web service is active.'
echo 'Refresh Live View with Ctrl+F5.'
pi-security-status
systemctl is-enabled pi-security-watchdog.timer
systemctl list-timers pi-security-watchdog.timer --no-pager
