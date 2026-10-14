import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('screenpadctl', str(Path(__file__).resolve().parents[1] / 'screenpadctl'))
spec = importlib.util.spec_from_loader(loader.name, loader)
ctl = importlib.util.module_from_spec(spec)
loader.exec_module(ctl)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.device = self.root / 'backlight/asus_screenpad'
        self.device.mkdir(parents=True)
        (self.device / 'brightness').write_text('82')
        (self.device / 'max_brightness').write_text('255')
        env = patch.dict(os.environ, {'XDG_STATE_HOME': str(self.root / 'state')})
        env.start()
        self.addCleanup(env.stop)

    def run_cli(self, *args, fail=False):
        def write(device, value):
            if fail:
                raise RuntimeError('permission denied')
            (device / 'brightness').write_text(str(value))
        output = io.StringIO()
        with patch.object(ctl, 'find_device', return_value=self.device), \
             patch.object(ctl, 'write_brightness', side_effect=write), \
             patch('sys.argv', ['screenpadctl', *args]), contextlib.redirect_stdout(output):
            code = ctl.main()
        return code, json.loads(output.getvalue())

    def test_status_rounding(self):
        code, state = self.run_cli('status')
        self.assertEqual((code, state['percent'], state['raw']), (0, 32, 82))

    def test_percent_limits_reach_exact_maximum(self):
        for percent, expected in [('1', 3), ('100', 255)]:
            code, state = self.run_cli('set', percent)
            self.assertEqual((code, state['raw']), (0, expected))

    def test_toggle_restores_exact_hardware_value(self):
        self.assertTrue(self.run_cli('toggle')[1]['off'])
        code, state = self.run_cli('toggle')
        self.assertEqual((code, state['raw']), (0, 82))

    def test_corrupt_saved_state_falls_back_to_half_brightness(self):
        (self.device / 'brightness').write_text('0')
        ctl.state_file().parent.mkdir(parents=True)
        ctl.state_file().write_text('invalid json')
        self.assertEqual(self.run_cli('toggle')[1]['raw'], 128)

    def test_failure_does_not_claim_success_or_save_requested_value(self):
        code, state = self.run_cli('set', '80', fail=True)
        self.assertEqual(code, 1)
        self.assertFalse(state['available'])
        self.assertIn('permission denied', state['error'])
        self.assertFalse(ctl.state_file().exists())
        self.assertEqual((self.device / 'brightness').read_text(), '82')

    def test_command_always_selects_screenpad_and_never_uses_shell(self):
        with patch.object(ctl.shutil, 'which', return_value='/usr/bin/brightnessctl'), \
             patch.object(ctl.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            ctl.write_brightness(self.device, 99)
        self.assertEqual(run.call_args.args[0], ['/usr/bin/brightnessctl', '-q', '-c',
            'backlight', '-d', 'asus_screenpad', 'set', '99'])
        self.assertNotIn('shell', run.call_args.kwargs)

    def test_missing_device_never_falls_back_to_primary_backlight(self):
        with patch.object(ctl.Path, 'is_file', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'ScreenPad'):
                ctl.find_device()

    def test_old_led_device_uses_correct_class(self):
        old = self.root / 'leds/asus::screenpad'
        with patch.object(ctl.shutil, 'which', return_value='/usr/bin/brightnessctl'), \
             patch.object(ctl.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            ctl.write_brightness(old, 100)
        self.assertEqual(run.call_args.args[0][2:6], ['-c', 'leds', '-d', 'asus::screenpad'])


if __name__ == '__main__':
    unittest.main()
