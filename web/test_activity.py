import importlib.util
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from recording_files import complete_mp4

spec = importlib.util.spec_from_file_location('scanner', Path(__file__).resolve().parents[1] / 'motion/scan_recordings.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


class ActivityTests(unittest.TestCase):
    def test_motion_requires_sustained_change(self):
        frame = scanner.WIDTH * scanner.HEIGHT
        self.assertIsNone(scanner.detect(bytes(frame * 8)))
        self.assertIsNone(scanner.detect(bytes(frame) + bytes([255]) * frame + bytes(frame * 5)))
        moving = b''.join(bytes([value]) * frame for value in (0,255,0,255,0))
        self.assertEqual(scanner.detect(moving), 0.5)
        with self.assertRaises(ValueError):
            scanner.detect(b'broken')

    def test_only_finalized_unopened_indexed_files_are_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            clip = root / '2026-09-09_16-30-00.mp4'
            box = lambda kind: struct.pack('>I', 8) + kind
            clip.write_bytes(box(b'ftyp') + box(b'mdat'))
            self.assertFalse(complete_mp4(clip))
            clip.write_bytes(clip.read_bytes() + box(b'moov'))
            self.assertTrue(complete_mp4(clip))
            st = clip.stat()
            self.assertFalse(complete_mp4(clip, {(st.st_dev, st.st_ino)}))
            index = {clip.name: {'size':st.st_size,'mtime_ns':st.st_mtime_ns,
                'status':'motion','first_motion_seconds':12,'thumbnail':'a'*64+'.jpg'}}
            with patch('main.RECORDINGS_PATH', root), patch('main.indexed_activity',return_value=index), patch('main.open_writers',return_value=set()), TestClient(app) as client:
                data = client.get('/api/recordings').json()
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]['display_title'], 'Camera 01 · 4:30:00 PM')
                self.assertEqual(data[0]['day'], '2026-09-09')
                self.assertEqual(data[0]['filename'], clip.name)
                with patch('main.open_writers',return_value={(st.st_dev,st.st_ino)}):
                    self.assertEqual(client.get('/api/recordings').json(), [])
                clip.write_bytes(clip.read_bytes()+box(b'free'))
                self.assertEqual(client.get('/api/recordings').json(), [])


if __name__ == '__main__':
    unittest.main()
