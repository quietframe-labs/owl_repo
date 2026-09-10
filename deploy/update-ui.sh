#!/bin/sh
# Run after git pull in Owl's application checkout.
set -eu
web=$(systemctl show pi-security-web.service --property=WorkingDirectory --value)
test -n "$web"
cd "$web"
source_css=dashboard_app/static/dashboard_app/css/app.css
served_css=staticfiles/dashboard_app/css/app.css
test -f "$source_css"
# STATIC_ROOT is BASE_DIR / 'staticfiles' in dashboard/settings.py.
test -f "$served_css" || { echo 'Collected stylesheet not found; check STATIC_ROOT before proceeding.' >&2; exit 1; }
backup=$(mktemp -d /var/backups/pi-security-ui.XXXXXXXX)
cp -p "$served_css" "$backup/app.css"
cat "$source_css" > "$served_css"
systemctl restart pi-security-web.service
sleep 2
systemctl is-active --quiet pi-security-web.service
echo "UI updated. Previous stylesheet: $backup/app.css"
echo 'Refresh the browser with Ctrl+F5.'
