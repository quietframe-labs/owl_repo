import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from main import LiveStaticFiles


class LiveCacheTests(unittest.TestCase):
    def test_playlist_and_reused_segments_are_not_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            app = FastAPI()
            app.mount('/live', LiveStaticFiles(directory=directory))
            with TestClient(app) as client:
                for name in ('index.m3u8', 'segment_00001.ts'):
                    path = Path(directory) / name
                    path.write_bytes(b'old output')
                    first = client.get('/live/' + name)
                    self.assertEqual(first.status_code, 200)
                    self.assertIn('no-store', first.headers['cache-control'])
                    conditional = client.get('/live/' + name, headers={
                        'If-None-Match': first.headers['etag'],
                        'If-Modified-Since': first.headers['last-modified'],
                    })
                    self.assertEqual(conditional.status_code, 200)
                    path.write_bytes(b'new output')
                    self.assertEqual(client.get('/live/' + name).content, b'new output')


if __name__ == '__main__':
    unittest.main()
