import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tray import Controls, autostart_file


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root / 'config')})
        env.start()
        self.addCleanup(env.stop)
        self.state = self.root / 'state.json'
        self.state.write_text(json.dumps({'raw': 82, 'saved': 82}))
        helper = self.root / 'helper.py'
        helper.write_text('''import json, sys
from pathlib import Path
p = Path(''' + repr(str(self.state)) + ''')
s = json.loads(p.read_text())
if s.get('unavailable'):
    print(json.dumps({'available': False, 'error': 'No ScreenPad driver'}))
    sys.exit(1)
if sys.argv[1] == 'set':
    s['raw'] = max(1, (int(sys.argv[2])*255+50)//100)
elif sys.argv[1] == 'toggle':
    if s['raw']:
        s['saved'], s['raw'] = s['raw'], 0
    else:
        s['raw'] = s['saved']
p.write_text(json.dumps(s))
print(json.dumps({'available': True, 'raw': s['raw'], 'maximum': 255,
    'percent': (s['raw']*100+127)//255, 'off': s['raw']==0}))
''')
        self.window = Controls(helper)
        self.wait_for(lambda: self.window.available)

    def tearDown(self):
        self.window.shutdown()
        self.window.deleteLater()
        self.app.processEvents()

    def wait_for(self, condition):
        end = time.monotonic() + 5
        while time.monotonic() < end:
            self.app.processEvents()
            if condition():
                return
            time.sleep(0.01)
        self.fail('Desktop control did not settle')

    def test_initial_state_and_rapid_updates(self):
        self.assertEqual(self.window.percent, 32)
        for value in (25, 50, 75):
            self.window.set_brightness(value)
        self.wait_for(lambda: not self.window.busy() and self.window.percent == 75)
        self.assertEqual(json.loads(self.state.read_text())['raw'], 191)
        self.assertEqual(self.window.slider.value(), 75)

    def test_power_toggle_restores_exact_value(self):
        self.window.toggle_power()
        self.wait_for(lambda: self.window.powered_off and not self.window.busy())
        self.window.toggle_power()
        self.wait_for(lambda: not self.window.powered_off and not self.window.busy())
        self.assertEqual(json.loads(self.state.read_text())['raw'], 82)

    def test_missing_driver_disables_controls_and_can_recover(self):
        self.state.write_text(json.dumps({'unavailable': True}))
        self.window.refresh()
        self.wait_for(lambda: not self.window.available)
        self.assertFalse(self.window.slider.isEnabled())
        self.assertIn('ScreenPad', self.window.error.text())
        self.state.write_text(json.dumps({'raw': 128, 'saved': 128}))
        self.window.refresh()
        self.wait_for(lambda: self.window.available)
        self.assertTrue(self.window.slider.isEnabled())

    def test_autostart_is_user_scoped_and_reversible(self):
        self.window.startup.setChecked(True)
        path = autostart_file()
        self.assertTrue(path.is_relative_to(self.root / 'config'))
        self.assertIn('--background', path.read_text())
        self.assertIn('tray.py" --background', path.read_text())
        self.window.startup.setChecked(False)
        self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
