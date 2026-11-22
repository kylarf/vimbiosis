# Claude Code setup

Start the agent with `:Vbio claude`, or run `:VbioAttach` and use the printed
exports and launch command in an external shell. Both paths configure the
Vim-owned MCP endpoint for that launch.

If upgrading, remove the old Vimbiosis skill symlinks and their matching
agent instructions. Restart Vim and the agent to switch to HTTP.

## Prompt and edit hooks

The prompt hook resets the diff baseline. Each file's first successful pre-edit
check saves its disk contents for cumulative diffs within that prompt.

Merge these entries into the corresponding hook arrays in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["$VIMBIOSIS_ROOT/claude/hooks/post-edit.py"]
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["$VIMBIOSIS_ROOT/claude/hooks/post-edit.py"]
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["$VIMBIOSIS_ROOT/claude/hooks/post-edit.py"]
          }
        ]
      }
    ]
  }
}
```

Claude's hook command does not expand your shell's `$VIMBIOSIS_ROOT` in `args`. Replace that string with the absolute path to `post-edit.py`. Preserve the settings file's other hooks and settings, and avoid duplicating an existing Vimbiosis entry. Restart Claude Code after changing settings.

The prompt hook injects live workspace metadata. The same script handles both edit events. Before `Edit` or `Write`, it checks the affected Vim buffer for unsaved text. A conflict blocks the tool and asks the agent to pause for your decision; save or reconcile the buffer in Vim before retrying. It does not save, reload, or discard your unsaved work. Once the check passes, it captures a before snapshot. After the edit, it refreshes Vim and records added, changed, and deleted regions in the change list. A conflict introduced while the tool was running is reported through the post-edit hook.

All hooks are silent no-ops when `VIMBIOSIS_SESSION` is unset. Existing post-only setups still refresh and add a file-level change-list entry, but omit highlights because no before snapshot is available. These hooks cover direct `Edit` and `Write` calls, not writes performed by shell commands or external formatters.

To uninstall, remove the Vimbiosis hook entries.
