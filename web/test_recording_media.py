import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


class RecordingMediaTests(unittest.TestCase):
    def test_inline_download_and_seek(self):
        with tempfile.TemporaryDirectory() as directory, patch('main.RECORDINGS_PATH', Path(directory)):
            (Path(directory) / 'clip.mp4').write_bytes(b'0123456789')
            with TestClient(app) as client:
                inline = client.get('/recordings/clip.mp4')
                self.assertEqual(inline.status_code, 200)
                self.assertEqual(inline.headers['content-type'], 'video/mp4')
                self.assertTrue(inline.headers['content-disposition'].startswith('inline;'))
                download = client.get('/recordings/clip.mp4?download=true')
                self.assertTrue(download.headers['content-disposition'].startswith('attachment;'))
                seek = client.get('/recordings/clip.mp4', headers={'Range': 'bytes=2-5'})
                self.assertEqual(seek.status_code, 206)
                self.assertEqual(seek.content, b'2345')
                self.assertEqual(seek.headers['content-range'], 'bytes 2-5/10')
                self.assertEqual(client.get('/recordings/missing.mp4').status_code, 404)
                (Path(directory) / 'note.txt').write_text('not video')
                self.assertEqual(client.get('/recordings/note.txt').status_code, 400)


if __name__ == '__main__':
    unittest.main()
