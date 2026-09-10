"""Produce a redacted systemd report; never install this report as unit files."""
import re
import subprocess
from pathlib import Path


def redact(text):
    lines = []
    omitted_continuation = False
    for line in text.splitlines():
        if omitted_continuation:
            omitted_continuation = line.rstrip().endswith('\\')
            continue
        # Inline environments may contain arbitrary secrets; omit all values.
        if re.match(r'\s*(Environment|SetCredential|SetCredentialEncrypted)=', line):
            omitted_continuation = line.rstrip().endswith('\\')
            line = '# Inline environment/credential omitted; configure outside Git.'
        elif re.search(r'(?i)(password|passwd|token|secret|api[_-]?key|authorization)', line) and not line.startswith('#'):
            omitted_continuation = line.rstrip().endswith('\\')
            line = '# Secret-bearing directive omitted; review original on Owl.'
        else:
            line = re.sub(r'(?i)rtsps?://[^\s\x22\x27]+', '<RTSP_URL_CONFIGURED_ON_OWL>', line)
            line = re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@', r'\1<credentials>@', line)
        lines.append(line)
    return '\n'.join(lines)


def main():
    listing = subprocess.run(['systemctl', 'list-unit-files', 'pi-security-*',
        '--no-legend', '--no-pager'], check=True, capture_output=True, text=True)
    units = [line.split()[0] for line in listing.stdout.splitlines() if line.strip()]
    output = []
    for unit in units:
        result = subprocess.run(['systemctl', 'cat', unit, '--no-pager'],
            check=True, capture_output=True, text=True)
        output.append(f'## {unit}\n{redact(result.stdout)}')
    path = Path('/tmp/owl-services-redacted.txt')
    path.write_text('\n\n'.join(output))
    path.chmod(0o600)
    print(f'Wrote {len(units)} units to {path}. Review before sharing; do not install this report.')


if __name__ == '__main__':
    main()
