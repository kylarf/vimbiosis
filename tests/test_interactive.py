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
events = []
def hook(event, paths, key):
    patch = '*** Begin Patch\\n' + ''.join(
        '*** Update File: ' + str(path) + '\\n' for path in paths) + '*** End Patch'
    payload = {'hook_event_name': event, 'tool_input': {'command': patch},
               'cwd': str(folder), 'tool_use_id': key}
    start = time.monotonic()
    result = subprocess.run([sys.executable, str(root / 'codex/hooks/post-edit.py')],
        input=json.dumps(payload), capture_output=True, text=True, timeout=9)
    events.append({'event': event, 'key': key, 'seconds': time.monotonic() - start,
                   'stdout': result.stdout, 'stderr': result.stderr, 'code': result.returncode})
    return not result.stdout and result.returncode == 0
# Load one file, switch away, then revisit it after another on-disk edit.
# Leave autoread off, matching Vim's default.
time.sleep(4.2)
for key, paths, line, text in [
    ('initial', files[:1], 0, 'first edit'),
    ('batch', files, 1, 'second edit'),
    ('reverse', list(reversed(files)), 2, 'third edit with extra text'),
    ('repeat', files[:1], 0, 'fourth edit in another region'),
]:
    if not hook('PreToolUse', paths, key):
        break
    for path in paths:
        lines = path.read_text().splitlines()
        lines[line] = text
        path.write_text('\\n'.join(lines) + '\\n')
    time.sleep(.1)
    if not hook('PostToolUse', paths, key):
        break
(folder / 'done').write_text(json.dumps({'events': events}))
""")
            boot = directory / "boot.vim"
            command = [sys.executable, str(probe), str(ROOT), tmp]
            boot.write_text("\n".join([
                "set noswapfile",
                "set noautoread hidden",
                "autocmd FileType qf wincmd J",
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
                deadline = time.monotonic() + 20
                while (not done.exists() or not done.read_text()) and time.monotonic() < deadline:
                    if select.select([fd], [], [], .03)[0]:
                        screen += os.read(fd, 65536)
                self.assertTrue(done.exists(), "Hook did not finish without a keypress")
                result = json.loads(done.read_text())
                self.assertEqual(len(result["events"]), 8, result)
                for event in result["events"]:
                    self.assertEqual(event["code"], 0, event)
                    self.assertEqual(event["stdout"], "", event)
                    self.assertEqual(event["stderr"], "", event)
                    self.assertLess(event["seconds"], 2, event)
                self.assertNotIn(b"Press ENTER", screen)
                self.assertNotIn(b"-- More --", screen)
            finally:
                os.kill(pid, signal.SIGTERM)
                os.waitpid(pid, 0)
                os.close(fd)
