import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from changes import hunks, Snapshots
from hooks import targets


class ChangeTests(unittest.TestCase):
    def test_bridge_startup_and_restart_from_installation_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="vbio install ") as tmp:
            directory = Path(tmp)
            for name in ("autoload", "bin", "python"):
                shutil.copytree(ROOT / name, directory / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
            result = directory / "result"
            boot = directory / "boot.vim"
            boot.write_text("\n".join([
                "execute 'set rtp^=' . fnameescape(" + json.dumps(tmp) + ")",
                "call vimbiosis#start_bridge()",
                "let first = g:vimbiosis_session",
                "call vimbiosis#start_bridge()",
                "call assert_equal(first, g:vimbiosis_session)",
                "call ch_close_in(job_getchannel(g:vimbiosis_job))",
                "let deadline = reltime()",
                "while exists('g:vimbiosis_session') && reltimefloat(reltime(deadline)) < 3",
                "  sleep 10m",
                "endwhile",
                "call assert_false(exists('g:vimbiosis_session'))",
                "call vimbiosis#start_bridge()",
                "call assert_notequal(first, g:vimbiosis_session)",
                "call vimbiosis#agent#detach()",
                "call assert_false(exists('g:vimbiosis_session'))",
                "call vimbiosis#start_bridge()",
                "sleep 100m",
                "call assert_true(exists('g:vimbiosis_session'))",
                "call vimbiosis#agent#detach()",
                "sleep 100m",
                "call assert_equal(0, len(filter(timer_info(), 'string(v:val.callback) =~# \"drain\"')))",
                "call writefile([json_encode(v:errors)], " + json.dumps(str(result)) + ")",
                "qa!",
            ]))
            run = subprocess.run(
                ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-S", str(boot)],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(result.read_text()), [])

    def test_bridge_startup_failure_reports_stderr(self):
        with tempfile.TemporaryDirectory(prefix="vbio failure ") as tmp:
            directory = Path(tmp)
            for name in ("autoload", "bin"):
                shutil.copytree(ROOT / name, directory / name)
            (directory / "python").mkdir()
            (directory / "python/vimbiosis.py").write_text(
                "import sys\nprint('bridge startup probe failed', file=sys.stderr)\nsys.exit(1)\n")
            result = directory / "result"
            boot = directory / "boot.vim"
            boot.write_text("\n".join([
                "execute 'set rtp^=' . fnameescape(" + json.dumps(tmp) + ")",
                "try",
                "  call vimbiosis#start_bridge()",
                "  call assert_report('expected startup failure')",
                "catch",
                "  call assert_match('bridge startup probe failed', v:exception)",
                "endtry",
                "call assert_false(exists('g:vimbiosis_session'))",
                "call assert_equal(0, len(filter(timer_info(), 'string(v:val.callback) =~# \"drain\"')))",
                "call writefile([json_encode(v:errors)], " + json.dumps(str(result)) + ")",
                "qa!",
            ]))
            run = subprocess.run(
                ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-S", str(boot)],
                capture_output=True, text=True, timeout=8)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(result.read_text()), [])

    def test_ranges(self):
        self.assertEqual(hunks(["same"], ["same"]), [])
        self.assertEqual(hunks([], ["new"])[0]["kind"], "added")
        self.assertEqual(hunks(["old"], ["new"])[0]["kind"], "changed")
        removed = hunks(["a", "b"], ["a"])[0]
        self.assertEqual((removed["kind"], removed["line"]), ("deleted", 1))

    def test_removal_payloads(self):
        for before, after, lines, placement in [
                (["a", "b", "c"], ["c"], ["a", "b"], "above"),
                (["a", "b", "c"], ["a"], ["b", "c"], "below"),
                (["a", "b"], [], ["a", "b"], "below"),
                (["  old", "\told"], ["new"], ["  old", "\told"], "above")]:
            change = hunks(before, after)[0]
            self.assertEqual(change["removed_lines"], lines)
            self.assertEqual(change["removed_placement"], placement)

    def test_missing_snapshot_does_not_claim_line_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "file.txt"
            path.write_text("one\ntwo\nthree\n")
            ranges = Snapshots().finish("missing", [{"path": str(path)}])[0]["hunks"]
            self.assertEqual(ranges[0]["kind"], "unknown")
            self.assertEqual(ranges[0]["end_line"], 1)

    def test_batch_displays_only_the_last_hidden_file(self):
        with tempfile.TemporaryDirectory(prefix="vbio test ") as tmp:
            directory = Path(tmp)
            files = [directory / ("file" + str(i)) for i in range(3)]
            for path in files:
                path.write_text("new\n")
            changes = [{"path": str(path), "hunks": [{
                "line": 1, "end_line": 1, "kind": "changed", "text": "Changed"
            }]} for path in files]
            result = directory / "result"
            script = "\n".join([
                "execute 'set rtp^=' . fnameescape(" + json.dumps(str(ROOT)) + ")",
                "let original = win_getid()",
                "let g:vimbiosis_anchor_win = original",
                "let g:entered = []",
                "runtime plugin/vimbiosis.vim",
                "autocmd BufEnter * if exists('g:vimbiosis_live_win') && win_getid() == g:vimbiosis_live_win | call add(g:entered, expand('%:p')) | endif",
                "let reply = vimbiosis#dispatch(" + json.dumps({
                    "op": "notify", "changes": changes}) + ")",
                "call assert_true(reply.ok)",
                "call assert_equal(original, win_getid())",
                "call assert_equal([fnamemodify(" + json.dumps(str(files[-1])) +
                ", ':p')], uniq(sort(copy(g:entered))))",
                "call assert_equal(3, len(getloclist(win_id2win(g:vimbiosis_live_win))))",
                "call assert_true(getloclist(win_id2win(g:vimbiosis_live_win), {'winid': 0}).winid > 0)",
                "call assert_equal(bufnr(" + json.dumps(str(files[-1])) +
                "), getwininfo(g:vimbiosis_live_win)[0].bufnr)",
                "call assert_equal(-1, getbufvar(bufnr(" + json.dumps(str(files[-1])) +
                "), '&l:autoread'))",
                "call assert_false(&autoread)",
                "VbioPrevious",
                "call assert_equal(['new'], getline(1, '$'))",
                "call assert_equal('VimbiosisChanged', sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs[0].name)",
                "call writefile([json_encode(v:errors)], " + json.dumps(str(result)) + ")",
                "qa!",
            ])
            boot = directory / "boot.vim"
            boot.write_text(script)
            run = subprocess.run(
                ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-S", str(boot)],
                text=True, capture_output=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(result.read_text()), [])

    def test_move_paths(self):
        result = targets("codex", {
            "cwd": str(ROOT), "tool_input": {"command":
                "*** Update File: old.txt\n*** Move to: new.txt\n"}})
        self.assertEqual(result, [{"path": str(ROOT / "new.txt"),
                                   "source": str(ROOT / "old.txt")}])

    def exercise_hooks(self, provider):
        with tempfile.TemporaryDirectory(prefix="vimbiosis test ") as tmp:
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
                "let g:vimbiosis_enable_virtual_text = 0",
                "execute 'set rtp^=' . fnameescape(" + q(ROOT) + ")",
                "runtime plugin/vimbiosis.vim",
                "execute 'edit ' . fnameescape(" + q(conflict) + ")",
                'call setline(1, "unsaved")',
                "execute 'new ' . fnameescape(" + q(edited) + ")",
                "let original = win_getid()",
                "let g:vimbiosis_anchor_win = original",
                "call vimbiosis#start_bridge()",
                'call writefile([g:vimbiosis_session], ' + q(ready) + ")",
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
                "let review_window = getloclist(win_id2win(g:vimbiosis_live_win), {'winid': 0}).winid",
                "let state = {'before': before, 'after': after, 'other': other,",
                "\\ 'entries': lists, 'focus': win_getid() == original,",
                "\\ 'review_visible': review_window > 0,",
                "\\ 'previous_file': previous_file, 'next_file': next_file,",
                "\\ 'edited': getbufline(edited_buffer, 1, '$'),",
                "\\ 'conflict': getbufline(bufnr(" + q(conflict) + "), 1, '$')}",
                "VbioChangesClear",
                "let state.cleared = sign_getplaced(added_buffer, {'group': 'Vimbiosis'})[0].signs",
                "call job_stop(g:vimbiosis_job)",
                "sleep 100m",
                "let state.detached = !exists('g:vimbiosis_session')",
                "let state.remaining_pumps = len(filter(timer_info(), 'string(v:val.callback) =~# \"drain\"'))",
                "call writefile([json_encode(state)], " + q(result) + ")",
                "qa!",
            ])
            boot = directory / "boot.vim"
            boot.write_text(script)
            proc = subprocess.Popen(
                ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-S", str(boot)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True)
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
                self.assertTrue(state["review_visible"])
                self.assertEqual(state["edited"], ["one", "three"])
                self.assertEqual(state["conflict"], ["unsaved"])
                self.assertEqual(Path(state["previous_file"]).resolve(), edited.resolve())
                self.assertEqual(Path(state["next_file"]).resolve(), added.resolve())
                self.assertEqual(state["cleared"], [])
                self.assertEqual(state["remaining_pumps"], 0)
                self.assertTrue(state["detached"])
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
