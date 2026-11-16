"""Exercise a synchronous multi-file hook inside a real Vim terminal."""
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import struct
import sys
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InteractiveTests(unittest.TestCase):
    def test_batch_hook_completes_without_keyboard_input(self):
        with tempfile.TemporaryDirectory(prefix="vbio-terminal-", dir="/tmp") as tmp:
            directory = Path(tmp)
            done = directory / "done"
            probe = directory / "probe.py"
            probe.write_text("""
import json, pathlib, subprocess, sys, time
root, folder = map(pathlib.Path, sys.argv[1:])
files = [folder / ('file' + str(i) + '.txt') for i in range(3)]
for path in files:
    path.write_text('one\\ntwo\\nthree\\n')
patch = '*** Begin Patch\\n' + ''.join(
    '*** Update File: ' + str(path) + '\\n' for path in files) + '*** End Patch'
payload = {'tool_input': {'command': patch}, 'cwd': str(folder), 'tool_use_id': 'batch'}
def hook(event):
    payload['hook_event_name'] = event
    return subprocess.run([sys.executable, str(root / 'codex/hooks/post-edit.py')],
        input=json.dumps(payload), capture_output=True, text=True, timeout=7)
before = hook('PreToolUse')
for path in files:
    path.write_text('one\\nchanged\\nthree\\n')
start = time.monotonic()
after = hook('PostToolUse')
(folder / 'done').write_text(json.dumps({
    'elapsed': time.monotonic() - start, 'pre': before.stdout, 'post': after.stdout,
    'pre_error': before.stderr, 'post_error': after.stderr,
    'returncodes': [before.returncode, after.returncode]}))
""")
            boot = directory / "boot.vim"
            command = [sys.executable, str(probe), str(ROOT), tmp]
            boot.write_text("\n".join([
                "set noswapfile",
                "set rtp^=" + str(ROOT),
                "call vimbiosis#start_bridge()",
                "call term_start(" + json.dumps(command) + ", {'env':",
                "\\ {'VIMBIOSIS_SESSION': g:vimbiosis_socket . ':' . g:vimbiosis_token}})",
                "let g:vimbiosis_anchor_win = win_getid()",
            ]))
            pid, fd = pty.fork()
            if pid == 0:
                os.environ["TERM"] = "xterm-256color"
                os.execv(shutil.which("vim"),
                         ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-S", str(boot)])
            screen = b""
            try:
                fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
                deadline = time.monotonic() + 4
                while (not done.exists() or not done.read_text()) and time.monotonic() < deadline:
                    if select.select([fd], [], [], .03)[0]:
                        screen += os.read(fd, 65536)
                self.assertTrue(done.exists(), "Hook did not finish without a keypress")
                result = json.loads(done.read_text())
                self.assertEqual(result["returncodes"], [0, 0], result)
                self.assertEqual(result["pre"], "", result)
                self.assertEqual(result["post"], "", result)
                self.assertLess(result["elapsed"], 2, result)
                self.assertNotIn(b"Press ENTER", screen)
                self.assertNotIn(b"-- More --", screen)
            finally:
                os.kill(pid, signal.SIGTERM)
                os.waitpid(pid, 0)
                os.close(fd)
