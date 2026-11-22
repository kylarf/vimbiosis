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
    def test_native_diff_tab_uses_live_buffer_and_restores_valid_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "live.txt"
            file.write_text("new\nkeep\n")
            script = Path(tmp) / "review.vim"
            errors = Path(tmp) / "errors"
            script.write_text("\n".join([
                "execute 'set rtp^=' . fnameescape(" + json.dumps(str(ROOT)) + ")",
                "runtime plugin/vimbiosis.vim",
                "let g:vimbiosis_enable_virtual_text = 0",
                "execute 'edit ' . fnameescape(" + json.dumps(str(file)) + ")",
                "let live = bufnr('%')",
                "let origin = win_getid()",
                "let change = {'path': expand('%:p'), 'before_lines': ['old', 'keep'], 'hunks': [{'line': 1, 'end_line': 1, 'kind': 'changed', 'text': 'Changed'}]}",
                "call vimbiosis#changes#record(change, origin)",
                "VbioChanges",
                "VbioDiff",
                "call assert_equal(live, bufnr('%'))",
                "call assert_equal(2, tabpagenr('$'))",
                "call assert_equal(1, &l:diff)",
                "call assert_equal([], sign_getplaced(live, {'group': 'Vimbiosis'})[0].signs)",
                "call win_gotoid(origin)",
                "call assert_equal(1, len(sign_getplaced(live, {'group': 'Vimbiosis'})[0].signs))",
                "VbioDiff",
                "call assert_equal(2, tabpagenr('$'))",
                "1diffget",
                "call assert_equal('old', getline(1))",
                "tabclose",
                "call assert_equal('old', getbufline(live, 1)[0])",
                "call assert_equal([], sign_getplaced(live, {'group': 'Vimbiosis'})[0].signs)",
                "call writefile(v:errors, " + json.dumps(str(errors)) + ")",
                "if !empty(v:errors) | cquit | endif",
                "qa!",
            ]))
            result = subprocess.run(
                ["vim", "-Nu", "NONE", "-i", "NONE", "-n", "-es", "-V1", "-S", str(script)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr +
                             (errors.read_text() if errors.exists() else ""))
            self.assertEqual(file.read_text(), "new\nkeep\n")

    def test_marker_modes_and_automatic_gutter(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / 'result'
            boot = Path(tmp) / 'boot.vim'
            boot.write_text('\n'.join([
                "execute 'set rtp^=' . fnameescape(" + json.dumps(str(ROOT)) + ")",
                "set columns=40 lines=20 signcolumn=auto nonumber norelativenumber",
                "set laststatus=0 noshowmode noruler",
                "call setline(1, ['new', 'added', 'tail'])",
                "let b:vimbiosis_hunks = [",
                r"\ {'line': 1, 'end_line': 1, 'kind': 'changed', 'removed_lines': ['old']},",
                r"\ {'line': 2, 'end_line': 2, 'kind': 'added'},",
                r"\ {'line': 3, 'end_line': 3, 'kind': 'deleted', 'removed_lines': ['gone'], 'removed_placement': 'below'}]",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "redraw!",
                "call assert_equal(0, getwininfo(win_getid())[0].textoff)",
                "call assert_equal(['-', '+', '+', ' ', '-'], map(range(1, 5), {_, row -> screenstring(row, 1)}))",
                "call assert_equal('t', screenstring(4, 2))",
                "call assert_equal(screenattr(2, 1), screenattr(3, 1))",
                "call assert_equal([], sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs)",
                "let g:vimbiosis_enable_virtual_text = 0",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "redraw!",
                "call assert_equal(2, getwininfo(win_getid())[0].textoff)",
                "call assert_equal(['~', '+', '-'], map(range(1, 3), {_, row -> screenstring(row, 1)}))",
                "call assert_equal(['n', 'a', 't'], map(range(1, 3), {_, row -> screenstring(row, 3)}))",
                "call assert_equal([], prop_list(1, {'end_lnum': -1}))",
                "call assert_equal(['VimbiosisChanged', 'VimbiosisAdded', 'VimbiosisDeleted'], map(sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs, 'v:val.name'))",
                "call assert_equal('VimbiosisChanged', sign_getdefined('VimbiosisChanged')[0].linehl)",
                "call assert_notequal(screenattr(1, 3), screenattr(2, 3))",
                "let g:vimbiosis_enable_virtual_text = 1",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "redraw!",
                "call assert_equal(0, getwininfo(win_getid())[0].textoff)",
                "call assert_equal('+', screenstring(2, 1))",
                "call assert_equal(screenattr(2, 1), screenattr(2, 40))",
                "let g:vimbiosis_diff_add_char = 'A'",
                "let g:vimbiosis_diff_remove_char = 'R'",
                "let g:vimbiosis_diff_change_char = 'C'",
                "let g:vimbiosis_diff_padding_char = '.'",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "redraw!",
                "call assert_equal(['R', 'C', 'A', '.', 'R'], map(range(1, 5), {_, row -> screenstring(row, 1)}))",
                "call assert_equal(repeat([' '], 5), map(range(1, 5), {_, row -> screenstring(row, 40)}))",
                "let g:vimbiosis_enable_virtual_text = 0",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "redraw!",
                "call assert_equal(['C', 'A', 'R'], map(range(1, 3), {_, row -> screenstring(row, 1)}))",
                "call vimbiosis#changes#clear(bufnr('%'))",
                "let g:vimbiosis_enable_virtual_text = 0",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "redraw!",
                "call assert_equal(0, getwininfo(win_getid())[0].textoff)",
                "call assert_equal(['new', 'added', 'tail'], getline(1, '$'))",
                'call writefile([json_encode(v:errors)], ' + json.dumps(str(result)) + ')',
                'qa!',
            ]))
            run = subprocess.run(
                ['vim', '--not-a-term', '-Nu', 'NONE', '-i', 'NONE', '-n', '-S', str(boot)],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(result.read_text()), [])

    def test_virtual_removals_have_compact_markers_and_full_row_highlights(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / 'result'
            boot = Path(tmp) / 'boot.vim'
            boot.write_text('\n'.join([
                "execute 'set rtp^=' . fnameescape(" + json.dumps(str(ROOT)) + ")",
                "runtime plugin/vimbiosis.vim",
                "execute 'file ' . fnameescape(" + json.dumps(str(Path(tmp) / 'target')) + ")",
                "set columns=40 lines=20 signcolumn=auto nonumber norelativenumber",
                "set laststatus=0 noshowmode noruler wrap nobreakindent showbreak=",
                "highlight VimbiosisDeleted ctermbg=Red ctermfg=White",
                "call setline(1, ['new', 'tail', \"\\ttabbed\"])",
                "setlocal tabstop=4",
                "let b:vimbiosis_hunks = [{'line': 1, 'end_line': 1, 'kind': 'changed', 'removed_lines': ['old', '  indented', '', 'x' . repeat('y', 45), \"\\ttabbed\"]}]",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "redraw!",
                "call assert_equal(0, getwininfo(win_getid())[0].textoff)",
                "let rows = map(range(1, 9), {_, row -> join(map(range(1, 40), {_, col -> screenstring(row, col)}), '')})",
                "call assert_equal('-old', substitute(rows[0], ' *$', '', ''))",
                "call assert_equal('-  indented', substitute(rows[1], ' *$', '', ''))",
                "call assert_equal('-', substitute(rows[2], ' *$', '', ''))",
                "call assert_equal('-x' . repeat('y', 38), rows[3])",
                "call assert_equal(repeat('y', 7), substitute(rows[4], ' *$', '', ''))",
                "call assert_equal('-   tabbed', substitute(rows[5], ' *$', '', ''))",
                "call assert_equal('+new', substitute(rows[6], ' *$', '', ''))",
                "call assert_equal(' tail', substitute(rows[7], ' *$', '', ''))",
                "call assert_equal('    tabbed', substitute(rows[8], ' *$', '', ''))",
                "for row in range(1, 6)",
                "  call assert_notequal(0, screenattr(row, 1))",
                "  call assert_equal(screenattr(row, 1), screenattr(row, 40))",
                "endfor",
                "call assert_equal([], sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs)",
                "call assert_equal(screenattr(7, 1), screenattr(7, 40))",
                "call assert_equal(['new', 'tail', \"\\ttabbed\"], getline(1, '$'))",
                "let b:vimbiosis_hunks[0].text = 'Changed'",
                "call vimbiosis#changes#record({'path': expand('%:p'), 'hunks': copy(b:vimbiosis_hunks)}, 0)",
                "set columns=60",
                "doautocmd WinResized",
                "redraw!",
                "call assert_equal('-', screenstring(1, 1))",
                "call assert_equal(' ', screenstring(1, 60))",
                "call assert_equal(screenattr(1, 1), screenattr(1, 60))",
                "call assert_equal(8, len(prop_list(1)))",
                "call assert_equal('+', screenstring(6, 1))",
                "call vimbiosis#changes#clear(bufnr('%'))",
                "redraw!",
                "call assert_equal([], prop_list(1))",
                "call assert_equal('n', screenstring(1, 1))",
                'call writefile([json_encode(v:errors)], ' + json.dumps(str(result)) + ')',
                'qa!',
            ]))
            run = subprocess.run(
                ['vim', '--not-a-term', '-Nu', 'NONE', '-i', 'NONE', '-n', '-S', str(boot)],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(result.read_text()), [])

    def test_replacements_use_inline_additions_or_gutter_modifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = Path(tmp) / "result"
            boot = Path(tmp) / "boot.vim"
            boot.write_text("\n".join([
                "execute 'set rtp^=' . fnameescape(" + json.dumps(str(ROOT)) + ")",
                "call setline(1, ['new one', 'new two'])",
                "let b:vimbiosis_hunks = [{'line': 1, 'end_line': 2, 'kind': 'changed', 'removed_lines': ['old']}]",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "if has('textprop') && has('patch-9.0.0438')",
                "  call assert_equal([], sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs)",
                "  call assert_equal(4, len(prop_list(1)))",
                "endif",
                "let g:vimbiosis_enable_virtual_text = 0",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "call assert_equal(['VimbiosisChanged', 'VimbiosisChanged'], map(sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs, 'v:val.name'))",
                "if has('textprop') | call assert_equal([], prop_list(1)) | endif",
                "let g:vimbiosis_enable_virtual_text = 1",
                "unlet b:vimbiosis_hunks[0].removed_lines",
                "call vimbiosis#changes#paint(bufnr('%'))",
                "let expected = has('textprop') && has('patch-9.0.0438') ? [] : ['VimbiosisChanged', 'VimbiosisChanged']",
                "call assert_equal(expected, map(sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs, 'v:val.name'))",
                "call assert_equal(['new one', 'new two'], getline(1, '$'))",
                "call writefile([json_encode(v:errors)], " + json.dumps(str(result)) + ")",
                "qa!",
            ]))
            run = subprocess.run(
                ['vim', '-Nu', 'NONE', '-i', 'NONE', '-n', '-es', '-S', str(boot)],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(result.read_text()), [])

    def test_blank_window_destinations(self):
        scenarios = [
            ([], True),
            (["call setline(1, 'unsaved')"], False),
            (["call setline(1, 'content')", "set nomodified"], False),
            (["file named"], False),
            (["setlocal buftype=nofile"], False),
            (["tabnew", "file named"], False),
        ]
        for operation in ('open', 'refresh'):
            for setup, reuse in scenarios:
                with self.subTest(operation=operation, setup=setup), tempfile.TemporaryDirectory() as tmp:
                    target = Path(tmp) / 'target.txt'
                    target.write_text('one\ntwo\n')
                    result = Path(tmp) / 'result'
                    boot = Path(tmp) / 'boot.vim'
                    path = json.dumps(str(target))
                    action = (
                        "call vimbiosis#open({'path': " + path + ", 'line': 2, 'vertical': v:true})"
                        if operation == 'open' else
                        'call vimbiosis#refresh(' + path + ')')
                    script = [
                        "execute 'set rtp^=' . fnameescape(" + json.dumps(str(ROOT)) + ")",
                        *setup,
                        'let original = win_getid()',
                        'let count_before = winnr("$")',
                        action,
                        'call assert_equal(count_before + ' + str(0 if reuse else 1) + ', winnr("$"))',
                    ]
                    if operation == 'open':
                        script += ['call assert_equal(2, line("."))']
                    else:
                        script += [
                            'call assert_equal(original, win_getid())',
                            'let live = g:vimbiosis_live_win',
                            'call vimbiosis#refresh(' + path + ')',
                            'call assert_equal(live, g:vimbiosis_live_win)',
                        ]
                    if reuse:
                        script += ['call assert_equal(original, ' +
                                   ('win_getid()' if operation == 'open' else 'g:vimbiosis_live_win') + ')']
                    script += [
                        'call writefile([json_encode(v:errors)], ' + json.dumps(str(result)) + ')',
                        'qa!',
                    ]
                    boot.write_text('\n'.join(script))
                    run = subprocess.run(
                        ['vim', '-Nu', 'NONE', '-i', 'NONE', '-n', '-es', '-S', str(boot)],
                        capture_output=True, text=True, timeout=5)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(json.loads(result.read_text()), [])

    def test_bridge_startup_and_restart_from_installation_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="vbio install ") as tmp:
            directory = Path(tmp)
            for name in ("autoload", "python"):
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
            shutil.copytree(ROOT / "autoload", directory / "autoload")
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
            change = Snapshots().finish("missing", [{"path": str(path)}])[0]
            self.assertNotIn("before_lines", change)
            ranges = change["hunks"]
            self.assertEqual(ranges[0]["kind"], "unknown")
            self.assertEqual(ranges[0]["end_line"], 1)

    def test_diff_baselines_for_creation_rename_and_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, renamed, created = (Path(tmp) / name for name in ("old", "new", "created"))
            source.write_text("before\n")
            snapshots = Snapshots()
            snapshots.capture("edit", [str(source), str(created)])
            source.rename(renamed)
            created.write_text("added\n")
            changes = snapshots.finish("edit", [
                {"path": str(renamed), "source": str(source)},
                {"path": str(created)},
                {"path": str(source)},
            ])
            self.assertEqual(changes[0]["before_lines"], ["before"])
            self.assertEqual(changes[1]["before_lines"], [])
            self.assertTrue(changes[2]["deleted"])
            self.assertNotIn("before_lines", changes[2])

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
                "let notification = " + json.dumps({"op": "notify", "changes": changes}),
                "let reply = vimbiosis#dispatch(notification)",
                "call assert_true(reply.ok)",
                "call assert_equal(original, win_getid())",
                "call assert_equal([resolve(fnamemodify(" + json.dumps(str(files[-1])) +
                ", ':p'))], uniq(sort(map(copy(g:entered), 'resolve(v:val)'))))",
                "call assert_equal(3, len(getloclist(win_id2win(g:vimbiosis_live_win))))",
                "call assert_true(getloclist(win_id2win(g:vimbiosis_live_win), {'winid': 0}).winid > 0)",
                "call assert_equal(bufnr(" + json.dumps(str(files[-1])) +
                "), getwininfo(g:vimbiosis_live_win)[0].bufnr)",
                "call assert_equal(-1, getbufvar(bufnr(" + json.dumps(str(files[-1])) +
                "), '&l:autoread'))",
                "call assert_false(&autoread)",
                "call win_execute(g:vimbiosis_live_win, 'lclose')",
                "let g:vimbiosis_auto_open_changes = 0",
                "let reply = vimbiosis#dispatch(notification)",
                "call assert_true(reply.ok)",
                "call assert_equal(original, win_getid())",
                "call assert_equal(3, len(getloclist(win_id2win(g:vimbiosis_live_win))))",
                "call assert_equal(0, getloclist(win_id2win(g:vimbiosis_live_win), {'winid': 0}).winid)",
                "VbioChanges",
                "call assert_true(getloclist(win_id2win(g:vimbiosis_live_win), {'winid': 0}).winid > 0)",
                "VbioPrevious",
                "call assert_equal(['new'], getline(1, '$'))",
                "let expected = has('textprop') && has('patch-9.0.0438') ? [] : ['VimbiosisChanged']",
                "call assert_equal(expected, map(sign_getplaced(bufnr('%'), {'group': 'Vimbiosis'})[0].signs, 'v:val.name'))",
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

    def test_prompt_baselines_reset_and_follow_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = (str(Path(tmp) / name) for name in ("old", "new"))
            snapshots = Snapshots()

            def capture(key, paths, session="agent"):
                snapshots.capture(key, paths, session, snapshots.prompts[session])

            snapshots.reset("agent")
            Path(old).write_text("original\n")
            capture("move", [old, new])
            Path(old).rename(new)
            snapshots.finish("move", [{"path": new, "source": old}], "agent")
            capture("edit", [new])
            Path(new).write_text("changed\n")
            change, = snapshots.finish("edit", [{"path": new}], "agent")
            self.assertEqual(change["hunks"][0]["removed_lines"], ["original"])
            snapshots.reset("other")
            capture("edit", [new], "other")
            capture("late", [new])
            snapshots.reset("agent")
            self.assertEqual(snapshots.finish("late", [{"path": new}], "agent"), [])
            capture("revert", [new])
            Path(new).write_text("original\n")
            change, = snapshots.finish("edit", [{"path": new}], "other")
            self.assertEqual(change["hunks"][0]["removed_lines"], ["changed"])
            Path(new).write_text("changed\n")
            change, = snapshots.finish("revert", [{"path": new}], "agent")
            self.assertEqual(change["hunks"], [])

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
                "let removed = getbufvar(edited_buffer, 'vimbiosis_hunks')[0].removed_lines",
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
                "let state = {'before': before, 'after': after, 'other': other, 'removed': removed,",
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

                self.assertIn("additionalContext",
                              hook("UserPromptSubmit", edited, "")["hookSpecificOutput"])
                edited.write_text("one\ndisk baseline\nthree\n")
                denied = hook("PreToolUse", [edited, conflict] if provider == "codex"
                              else conflict, "blocked")
                self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertIn("ask the user", denied["hookSpecificOutput"]["permissionDecisionReason"])
                self.assertEqual(conflict.read_text(), "original\n")
                self.assertIsNone(hook("PreToolUse", edited, "first"))
                edited.write_text("one\nintermediate\n")
                self.assertIsNone(hook("PostToolUse", edited, "first"))
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
                self.assertEqual(state["removed"], ["disk baseline"])
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
