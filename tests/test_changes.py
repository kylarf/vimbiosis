import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from changes import hunks
from hooks import targets


class ChangeTests(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(hunks(["same"], ["same"]), [])
        self.assertEqual(hunks([], ["new"])[0]["kind"], "added")
        self.assertEqual(hunks(["old"], ["new"])[0]["kind"], "changed")
        removed = hunks(["a", "b"], ["a"])[0]
        self.assertEqual((removed["kind"], removed["line"]), ("deleted", 1))

    def test_move_paths(self):
        result = targets("codex", {
            "cwd": "/tmp", "tool_input": {"command":
                "*** Update File: old.txt\n*** Move to: new.txt\n"}})
        self.assertEqual(result, [{"path": "/tmp/new.txt", "source": "/tmp/old.txt"}])

    def exercise_hooks(self, provider):
        with tempfile.TemporaryDirectory(prefix="vimbiosis-test-", dir="/tmp") as tmp:
            directory = Path(tmp)
            edited = directory / "edited.txt"
            added = directory / "added.txt"
            conflict = directory / "conflict.txt"
            ready, done, result = [directory / name for name in ("ready", "done", "result")]
            edited.write_text("one\ntwo\nthree\n")
            conflict.write_text("original\n")
            q = lambda path: json.dumps(str(path))
            script = "\n".join([
                "set hidden nomore",
                "set rtp^=" + str(ROOT),
                "runtime plugin/vimbiosis.vim",
                "edit " + str(conflict),
                'call setline(1, "unsaved")',
                "new " + str(edited),
                "let original = win_getid()",
                "let g:vimbiosis_anchor_win = original",
                "call vimbiosis#start_bridge()",
                "sleep 100m",
                'call writefile([g:vimbiosis_socket . ":" . g:vimbiosis_token], ' + q(ready) + ")",
                "let deadline = reltime()",
                "while !filereadable(" + q(done) + ") && reltimefloat(reltime(deadline)) < 15",
                "  sleep 10m",
                "endwhile",
                "let edited_buffer = bufnr(" + q(edited) + ")",
                "let added_buffer = bufnr(" + q(added) + ")",
                "let before = sign_getplaced(edited_buffer, {'group': 'Vimbiosis'})[0].signs",
                'call win_execute(original, "doautocmd InsertEnter")',
                "let after = sign_getplaced(edited_buffer, {'group': 'Vimbiosis'})[0].signs",
                "let other = sign_getplaced(added_buffer, {'group': 'Vimbiosis'})[0].signs",
                "let lists = []",
                "for window in getwininfo()",
                "  let items = getloclist(window.winnr)",
                "  if !empty(items) | let lists = items | endif",
                "endfor",
                "VbioPrevious",
                "let previous_file = expand('%:p')",
                "VbioNext",
                "let next_file = expand('%:p')",
                "call win_gotoid(original)",
                "let state = {'before': before, 'after': after, 'other': other,",
                "\\ 'entries': lists, 'focus': win_getid() == original,",
                "\\ 'previous_file': previous_file, 'next_file': next_file,",
                "\\ 'edited': getbufline(edited_buffer, 1, '$'),",
                "\\ 'conflict': getbufline(bufnr(" + q(conflict) + "), 1, '$')}",
                "VbioChangesClear",
                "let state.cleared = sign_getplaced(added_buffer, {'group': 'Vimbiosis'})[0].signs",
                "call writefile([json_encode(state)], " + q(result) + ")",
                "call job_stop(g:vimbiosis_job)",
                "qa!",
            ])
            proc = subprocess.Popen(
                ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-S", "/dev/stdin"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True)
            proc.stdin.write(script + "\n")
            proc.stdin.close()
            try:
                deadline = time.monotonic() + 5
                while (not ready.exists() or not ready.read_text().strip()) and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.exists(), "Vim failed to start")
                env = os.environ.copy()
                env["VIMBIOSIS_SESSION"] = ready.read_text().strip()

                def hook(event, path, key):
                    paths = path if isinstance(path, list) else [path]
                    tool = ({"file_path": str(path)} if provider == "claude" else
                            {"command": "*** Begin Patch\n" + "".join(
                                "*** Update File: " + str(item) + "\n" for item in paths)
                             + "*** End Patch"})
                    run = subprocess.run(
                        [sys.executable, str(ROOT / provider / "hooks/post-edit.py")],
                        input=json.dumps({"hook_event_name": event, "tool_input": tool,
                                          "tool_use_id": key, "cwd": tmp}),
                        env=env, capture_output=True, text=True, timeout=8)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    return json.loads(run.stdout) if run.stdout else None

                denied = hook("PreToolUse", [edited, conflict] if provider == "codex"
                              else conflict, "blocked")
                self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertIn("ask the user", denied["hookSpecificOutput"]["permissionDecisionReason"])
                self.assertEqual(conflict.read_text(), "original\n")
                if provider == "codex":
                    self.assertIsNone(hook("PreToolUse", [edited, added], "batch"))
                    edited.write_text("one\nthree\n")
                    added.write_text("new\n")
                    self.assertIsNone(hook("PostToolUse", [edited, added], "batch"))
                else:
                    self.assertIsNone(hook("PreToolUse", edited, "edit"))
                    edited.write_text("one\nthree\n")
                    self.assertIsNone(hook("PostToolUse", edited, "edit"))
                    self.assertIsNone(hook("PreToolUse", added, "add"))
                    added.write_text("new\n")
                    self.assertIsNone(hook("PostToolUse", added, "add"))
                done.touch()
                proc.wait(timeout=5)
                self.assertEqual(proc.returncode, 0, proc.stderr.read())
                state = json.loads(result.read_text())
                self.assertEqual(state["before"][0]["name"], "VimbiosisDeleted")
                self.assertEqual(state["after"], [])
                self.assertEqual(state["other"][0]["name"], "VimbiosisAdded")
                self.assertEqual(len(state["entries"]), 2)
                self.assertTrue(state["focus"])
                self.assertEqual(state["edited"], ["one", "three"])
                self.assertEqual(state["conflict"], ["unsaved"])
                self.assertEqual(Path(state["previous_file"]).resolve(), edited.resolve())
                self.assertEqual(Path(state["next_file"]).resolve(), added.resolve())
                self.assertEqual(state["cleared"], [])
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()

    def test_codex_hooks_and_vim(self):
        self.exercise_hooks("codex")

    def test_claude_hooks_and_vim(self):
        self.exercise_hooks("claude")


if __name__ == "__main__":
    unittest.main()
