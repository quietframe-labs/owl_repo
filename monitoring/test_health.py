import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('health', Path(__file__).with_name('pi-security-health.py'))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class HealthTests(unittest.TestCase):
    def test_thresholds_and_states(self):
        for limit in (30, 600):
            self.assertEqual(h.assessment('active', 1000, {'output': limit}, limit), ('HEALTHY', False))
            self.assertEqual(h.assessment('active', 1000, {'output': limit + 1}, limit), ('ACTIVE-but-stale', True))
            self.assertTrue(h.assessment('active', 1000, {'output': None}, limit)[1])
            self.assertFalse(h.assessment('active', 1, {'output': None}, limit)[1])
            self.assertTrue(h.assessment('failed', None, {'output': 0}, limit)[1])
            self.assertFalse(h.assessment('activating', None, {'output': None}, limit)[1])

    def test_both_hls_outputs_required(self):
        for ages in ({'playlist': 1, 'segment': 31}, {'playlist': 31, 'segment': 1},
                     {'playlist': 1, 'segment': None}):
            self.assertTrue(h.assessment('active', 1000, ages, 30)[1])

    def test_file_age_and_empty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(h.newest_age(root, '*.mp4', 1000))
            old = root / 'old.mp4'
            old.write_bytes(b'video')
            os.utime(old, (300, 300))
            (root / 'empty.mp4').touch()
            (root / 'ignore.txt').write_text('ignore')
            self.assertEqual(h.newest_age(root, '*.mp4', 1000), 700)

    def test_independent_restart_and_cooldown(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(h, 'STATE', Path(directory) / 'restarts.json'), \
                patch.object(h, 'service_info', return_value=('active', 2000)), \
                patch.object(h, 'output_ages', return_value=[{'recording': 601}, {'playlist': 1, 'segment': 1}]), \
                patch.object(h.subprocess, 'run') as restart, patch.object(h.time, 'monotonic', return_value=5000):
            restart.return_value.returncode = 0
            h.run(True)
            h.run(True)
            self.assertEqual(restart.call_count, 1)
            self.assertEqual(restart.call_args.args[0], ['systemctl', 'restart', 'pi-security-recorder.service'])

    def test_live_restart_failure_logged(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(h, 'STATE', Path(directory) / 'restarts.json'), \
                patch.object(h, 'service_info', return_value=('active', 2000)), \
                patch.object(h, 'output_ages', return_value=[{'recording': 2}, {'playlist': 40, 'segment': 40}]), \
                patch.object(h.subprocess, 'run') as restart, patch.object(h, 'log') as log:
            restart.return_value.returncode = 1
            h.run(True)
            self.assertEqual(restart.call_args.args[0], ['systemctl', 'restart', 'pi-security-live.service'])
            self.assertIn('ERROR restart failed', log.call_args.args[0])

    def test_status_marks_stale(self):
        with patch.object(h, 'service_info', return_value=('active', 2000)), \
                patch.object(h, 'output_ages', return_value=[{'recording': 601}, {'playlist': 40, 'segment': 40}]), \
                patch('builtins.print') as output:
            self.assertEqual(h.run(), 1)
            self.assertTrue(all('ACTIVE-but-stale' in call.args[0] for call in output.call_args_list))


if __name__ == '__main__':
    unittest.main(verbosity=2)
