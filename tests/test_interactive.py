"""Exercise a synchronous multi-file hook inside a real Vim terminal."""
import json
import os
from pathlib import Path
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest

if os.name != "nt":
    import fcntl
    import pty
    import termios

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == "nt", "requires Unix PTY support")
class InteractiveTests(unittest.TestCase):
    def test_quitting_vim_removes_attached_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            session_id = home / "attached"
            subprocess.run(
                ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es",
                 "-c", "execute 'set rtp^=' . fnameescape($VBIO_TEST_ROOT)",
                 "-c", "runtime plugin/vimbiosis.vim",
                 "-c", "VbioAttach",
                 "-c", "call writefile([g:vimbiosis_session_id], $VBIO_TEST_SESSION)",
                 "-c", "q"],
                env=dict(os.environ, HOME=tmp, VBIO_TEST_ROOT=str(ROOT),
                         VBIO_TEST_SESSION=str(session_id)),
                capture_output=True, check=True, timeout=10,
            )
            directory = home / ".vimbiosis" / "sessions" / session_id.read_text().strip()
            deadline = time.monotonic() + 3
            while directory.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertFalse(directory.exists(), "Vim left its session directory behind")

    def test_batch_hook_completes_without_keyboard_input(self):
        with tempfile.TemporaryDirectory(prefix="vbio terminal ") as tmp:
            directory = Path(tmp)
            done = directory / "done"
            probe = directory / "probe.py"
            probe.write_text("""
import json, pathlib, subprocess, sys, time
import os, urllib.request
root, folder = map(pathlib.Path, sys.argv[1:])
sys.path.insert(0, str(root / 'python'))
from launcher import select
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
selected = select(os.environ['ATTACH_ID'])
assert selected[1] == os.environ['VIMBIOSIS_SESSION']
assert select(None)[0] == selected[0]
context = subprocess.run([sys.executable, str(root / 'codex/hooks/post-edit.py')],
    input=json.dumps({'hook_event_name': 'UserPromptSubmit'}),
    capture_output=True, text=True, check=True, timeout=5)
metadata = json.loads(json.loads(context.stdout)['hookSpecificOutput']
                      ['additionalContext'].split('\\n', 1)[1])
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

port, token = os.environ['VIMBIOSIS_SESSION'].split(':')
def tool(name, **arguments):
    request = urllib.request.Request(f'http://127.0.0.1:{port}/mcp',
        json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                    'params': {'name': name, 'arguments': arguments}}).encode(),
        {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=6) as reply:
        result = json.load(reply)['result']
        return json.loads(result['content'][0]['text'])

opened = tool('open_file', path=metadata['cwd'] + '/first.txt', line=1)
mapped = tool('send_keys', keys='<F5>')
read = tool('read_buffer', path=opened['path'])
tool('execute_ex', command='let g:vimbiosis_allow_arbitrary_actions = 0')
denied = tool('execute_ex', command='echo "should be blocked"')
(folder / 'done').write_text(json.dumps({'events': events, 'metadata': metadata,
    'opened': opened, 'mapped': mapped, 'read': read, 'denied': denied}))
""")
            boot = directory / "boot.vim"
            command = [sys.executable, str(probe), str(ROOT), tmp]
            boot.write_text("\n".join([
                "set noswapfile",
                "set noautoread hidden",
                "autocmd FileType qf wincmd J",
                "execute 'set rtp^=' . fnameescape(" + json.dumps(str(ROOT)) + ")",
                "runtime plugin/vimbiosis.vim",
                "new first.txt",
                "new second.txt",
                "let g:vimbiosis_allow_arbitrary_actions = 1",
                "nnoremap <F5> :call setline(1, 'unsaved mapping output')<CR>",
                "let attach_message = execute('VbioAttach')",
                "if attach_message !~# 'vimbiosis -s ' . g:vimbiosis_session_id | cquit | endif",
                "call term_start(" + json.dumps(command) + ", {'env':",
                "\\ {'VIMBIOSIS_SESSION': g:vimbiosis_session, 'ATTACH_ID': g:vimbiosis_session_id}})",
                "let g:vimbiosis_anchor_win = win_getid()",
            ]))
            pid, fd = pty.fork()
            if pid == 0:
                os.environ["TERM"] = "xterm-256color"
                os.environ["HOME"] = tmp
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
                self.assertNotIn("active", result["metadata"])
                self.assertTrue(result["opened"]["ok"], result)
                self.assertTrue(result["mapped"]["ok"], result)
                self.assertEqual(result["read"]["lines"], ["unsaved mapping output"])
                self.assertFalse(result["denied"]["ok"])
                self.assertEqual({Path(buffer["path"]).name
                                  for buffer in result["metadata"]["buffers"]},
                                 {"first.txt", "second.txt"})
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
