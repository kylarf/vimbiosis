# Claude Code setup

Set `VIMBIOSIS_ROOT` to the absolute path of this checkout. Add `$VIMBIOSIS_ROOT/bin` to `PATH` in the shell used to start Claude Code. For an attachment started from Vim, `:Vbio claude` sets this path automatically. For an existing Vim, run `:VbioAttach` and evaluate its printed `VIMBIOSIS_SESSION` export in the shell before starting Claude.

## Skills

Link the provided skills into Claude Code's personal skill directory:

```sh
mkdir -p "$HOME/.claude/skills"
ln -s "$VIMBIOSIS_ROOT/claude/skills/show-code" "$HOME/.claude/skills/vimbiosis-show-code"
ln -s "$VIMBIOSIS_ROOT/claude/skills/workspace-context" "$HOME/.claude/skills/vimbiosis-workspace-context"
```

Claude Code also supports project skills in `.claude/skills/` if you prefer to enable these only for one repository. Avoid replacing an existing skill with the same destination name.

In your global or project `CLAUDE.md`, add instructions to use the `vimbiosis-show-code` skill when you ask where code is or ask to see it, and the `vimbiosis-workspace-context` skill when you ask about currently open files, unsaved edits, Vim state, or the attached workspace. For general repository questions, Claude Code can search the files first and consult live workspace context when it may affect the answer. These let Claude Code open relevant code and inspect live editor state when appropriate.

## Edit hooks

Merge these entries into the corresponding hook arrays in `~/.claude/settings.json`:

```json
{
  "hooks": {
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

The same script handles both events. Before `Edit` or `Write`, it checks the affected Vim buffer for unsaved text. A conflict blocks the tool and asks the agent to pause for your decision; save or reconcile the buffer in Vim before retrying. It does not save, reload, or discard your unsaved work. Once the check passes, it captures a before snapshot. After the edit, it refreshes Vim and records added, changed, and deleted regions in the change list. A conflict introduced while the tool was running is reported through the post-edit hook.

Both hooks are silent no-ops when `VIMBIOSIS_SESSION` is unset. Existing post-only setups still refresh and add a file-level change-list entry, but omit highlights because no before snapshot is available. These hooks cover direct `Edit` and `Write` calls, not writes performed by shell commands or external formatters.

To uninstall, remove these two skill links and only the Vimbiosis entries from the two hook arrays.
