# Owl systemd units

The activity scanner and watchdog definitions in this folder are managed source
files. Editing them in Git does not update `/etc/systemd/system` until installed.

Install activity with `sudo sh deploy/install-activity.sh` from the checkout.
The existing watchdog remains installed on Owl. Its source is now tracked here,
and its Python implementation is in `monitoring/pi-security-health.py`.

The recorder, live, web, retention, and storage monitor unit definitions have not
yet been exported from Owl. Do not replace them with guessed configurations.
Keep credentials in `/etc/pi-security` on Owl, outside Git. The earlier project
notes may contain example units but are not authoritative production definitions.

To capture a reviewable, redacted inventory on Owl:

```sh
python3 deploy/export-services.py
```

The output is a text report in `/tmp/owl-services-redacted.txt`. Review it before
sharing. Redaction is best-effort; this report is for review, not installation.
Keep original backups on Owl. Once reviewed, the real units can be converted to
credential-free templates and committed through the normal PC workflow.
