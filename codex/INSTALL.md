# Codex setup

Set `VIMBIOSIS_ROOT` to the absolute path of this checkout. Add `$VIMBIOSIS_ROOT/bin` to `PATH` in the shell used to start Codex. For an attachment started from Vim, `:Vbio codex` sets this path automatically. For an existing Vim, run `:VbioAttach` and evaluate its printed `VIMBIOSIS_SESSION` export in the shell before starting Codex.

## Skills

Link the provided skills into Codex's personal skill directory:

```sh
mkdir -p "$HOME/.agents/skills"
ln -s "$VIMBIOSIS_ROOT/codex/skills/show-code" "$HOME/.agents/skills/vimbiosis-show-code"
ln -s "$VIMBIOSIS_ROOT/codex/skills/workspace-context" "$HOME/.agents/skills/vimbiosis-workspace-context"
```

Codex also supports repository skills in `.agents/skills/`. Avoid replacing an existing skill with the same destination name.

In your global or project `AGENTS.md`, add instructions to use the `vimbiosis-show-code` skill when you ask where code is or ask to see it, and the `vimbiosis-workspace-context` skill when you ask about currently open files, unsaved edits, Vim state, or the attached workspace. For general repository questions, Codex can search the files first and consult live workspace context when it may affect the answer. These let Codex open relevant code and inspect live editor state when appropriate.

## Edit hooks

Append this TOML to `~/.codex/config.toml`:

```toml
[[hooks.PostToolUse]]
matcher = "^apply_patch$"

[[hooks.PostToolUse.hooks]]
type = "command"
command = 'python3 "ABSOLUTE_PATH_TO_VIMBIOSIS/codex/hooks/post-edit.py"'

[[hooks.PreToolUse]]
matcher = "^apply_patch$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = 'python3 "ABSOLUTE_PATH_TO_VIMBIOSIS/codex/hooks/post-edit.py"'
```

Replace `ABSOLUTE_PATH_TO_VIMBIOSIS` with this checkout's path. Merge these hook tables alongside existing settings; do not overwrite `config.toml` or duplicate an existing Vimbiosis entry. Review and enable the hooks through Codex's hook trust UI after updating them.

The same script handles both events. Before an edit, it checks all affected Vim buffers for unsaved text. A conflict blocks the tool and asks the agent to pause for your decision; save or reconcile the buffer in Vim before retrying. It does not save, reload, or discard your unsaved work. Once the check passes, it captures a before snapshot. After the edit, it refreshes Vim and records added, changed, and deleted regions in the change list. A conflict introduced while the tool was running is reported through the post-edit hook.

Both hooks are silent no-ops when `VIMBIOSIS_SESSION` is unset. For external attachments, start Codex with `--no-daemon`; `:Vbio codex` adds that option automatically. Existing post-only setups still refresh and add a file-level change-list entry, but omit highlights because no before snapshot is available.

These hooks cover direct `apply_patch` edits, not writes performed by shell commands or external formatters.

To uninstall, remove these two skill links and only the matching hook tables from `config.toml`.
