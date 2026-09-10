"""Conservative completion checks for FFmpeg's ordinary segmented MP4 files."""
import os
from pathlib import Path


def open_writers():
    """Inspect same-user processes; the scanner runs as recorder user admin."""
    result = set()
    if os.name == 'nt':
        return result
    for process in Path('/proc').glob('[0-9]*'):
        try:
            for fd in (process / 'fd').iterdir():
                try:
                    info = (process / 'fdinfo' / fd.name).read_text()
                    flags = next(line.split()[1] for line in info.splitlines() if line.startswith('flags:'))
                    if int(flags, 8) & os.O_ACCMODE:
                        stat = fd.stat()
                        result.add((stat.st_dev, stat.st_ino))
                except (OSError, StopIteration):
                    continue
        except OSError:
            continue
    return result


def complete_mp4(path, writers=()):
    """Require finalized moov and complete top-level boxes, never infer from age."""
    try:
        stat = path.stat()
        if (stat.st_dev, stat.st_ino) in writers:
            return False
        found_moov = False
        with path.open('rb') as stream:
            offset = 0
            while offset < stat.st_size:
                header = stream.read(8)
                if len(header) != 8:
                    return False
                size, kind = int.from_bytes(header[:4], 'big'), header[4:]
                header_size = 8
                if size == 1:
                    extended = stream.read(8)
                    if len(extended) != 8:
                        return False
                    size, header_size = int.from_bytes(extended, 'big'), 16
                if size < header_size or offset + size > stat.st_size:
                    return False
                found_moov |= kind == b'moov'
                offset += size
                stream.seek(offset)
        return found_moov and stat.st_size == path.stat().st_size
    except OSError:
        return False
