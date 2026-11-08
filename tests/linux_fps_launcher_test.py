"""The regression launcher runs on copies and preserves the original profile and caches. No game files or GPU."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'tools' / 'test_linux_fps.py'


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'original game [test]'
        self.game.mkdir()
        for name in ('profile', 'shader-cache', 'romfs', 'exefs'):
            (self.game / name).mkdir()
        (self.game / 'profile' / 'save.txt').write_text('original save')
        # Even a symlinked mutable input must be copied, not written through.
        self.cache = self.root / 'original-cache.bin'
        self.cache.write_text('original cache')
        (self.game / 'pipeline-cache.bin').symlink_to(self.cache)
        (self.game / 'totk.ini').write_text('ub_overlay = 1\n')
        binary = self.game / 'totk'
        binary.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
profile = Path(sys.argv[sys.argv.index('--profile') + 1])
(profile / 'save.txt').write_text('test save')
Path('pipeline-cache.bin').write_text('test cache')
Path('totk.ini').write_text('test settings')
Path('observed.json').write_text(json.dumps({'overlay': os.environ['TOTK_UB_OVERLAY'],
    'recorder': os.environ['TOTK_VK_RECORDER'], 'args': sys.argv[1:]}))
''')
        binary.chmod(0o755)

    def run_case(self, case, out):
        return subprocess.run([sys.executable, str(TOOL), '--game-dir', str(self.game),
                               '--out', str(out), '--case', case], capture_output=True, text=True)

    def test_isolated_runs_and_overrides(self):
        for case, expected in [('stock', '1'), ('legacy', '0')]:
            with self.subTest(case=case):
                dest = self.root / case
                result = self.run_case(case, dest)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed = json.loads((dest / 'observed.json').read_text())
                self.assertEqual(observed['overlay'], expected)
                self.assertEqual(observed['recorder'], '0')
                self.assertEqual((dest / 'profile' / 'save.txt').read_text(), 'test save')
        self.assertEqual((self.game / 'profile' / 'save.txt').read_text(), 'original save')
        self.assertEqual(self.cache.read_text(), 'original cache')
        self.assertEqual((self.game / 'totk.ini').read_text(), 'ub_overlay = 1\n')

    def test_refuses_existing_or_nested_destination(self):
        for dest in [self.game, self.game / 'nested', self.root]:
            with self.subTest(dest=dest):
                self.assertNotEqual(self.run_case('legacy', dest).returncode, 0)
        self.assertFalse((self.game / 'nested').exists())


if __name__ == '__main__':
    unittest.main()
