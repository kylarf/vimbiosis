# Codex setup

Start the agent with `:Vbio codex`, or run `:VbioAttach` and use the printed
exports and launch command in an external shell. Both paths configure the
Vim-owned MCP endpoint for that launch.

If upgrading, remove the old Vimbiosis skill symlinks and their matching
agent instructions. Restart Vim and the agent to switch to HTTP.

## Prompt and edit hooks

The prompt hook resets the diff baseline. Each file's first successful pre-edit
check saves its disk contents for cumulative diffs within that prompt.

Append this TOML to `~/.codex/config.toml`:

```toml
[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = 'python3 "ABSOLUTE_PATH_TO_VIMBIOSIS/codex/hooks/post-edit.py"'

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

The prompt hook injects live workspace metadata. The same script handles both edit events. Before an edit, it checks all affected Vim buffers for unsaved text. A conflict blocks the tool and asks the agent to pause for your decision; save or reconcile the buffer in Vim before retrying. It does not save, reload, or discard your unsaved work. Once the check passes, it captures a before snapshot. After the edit, it refreshes Vim and records added, changed, and deleted regions in the change list. A conflict introduced while the tool was running is reported through the post-edit hook.

All hooks are silent no-ops when `VIMBIOSIS_SESSION` is unset. For external attachments, start Codex with `--no-daemon`; `:Vbio codex` adds that option automatically. Existing post-only setups still refresh and add a file-level change-list entry, but omit highlights because no before snapshot is available.

These hooks cover direct `apply_patch` edits, not writes performed by shell commands or external formatters.

To uninstall, remove the Vimbiosis hook entries.
