# Claude Code setup

Set `VIMBIOSIS_ROOT` to the absolute path of this checkout. Add `$VIMBIOSIS_ROOT/bin` to `PATH` in the shell used to start Claude Code. For an attachment started from Vim, `:Agent claude` sets this path automatically. For an existing Vim, run `:AgentAttach` and evaluate its printed `VIMBIOSIS_SESSION` export in the shell before starting Claude.

## Skills

Link the provided skills into Claude Code's personal skill directory:

```sh
mkdir -p "$HOME/.claude/skills"
ln -s "$VIMBIOSIS_ROOT/claude/skills/show-code" "$HOME/.claude/skills/vimbiosis-show-code"
ln -s "$VIMBIOSIS_ROOT/claude/skills/workspace-context" "$HOME/.claude/skills/vimbiosis-workspace-context"
```

Claude Code also supports project skills in `.claude/skills/` if you prefer to enable these only for one repository. Avoid replacing an existing skill with the same destination name.

## Post-edit hook

Add this entry to the existing `hooks.PostToolUse` array in `~/.claude/settings.json`:

```json
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
```

Claude's hook command does not expand your shell's `$VIMBIOSIS_ROOT` in `args`. Replace that string with the absolute path to `post-edit.py`. Merge the entry into the existing JSON object; do not replace the settings file or its other hooks. Restart Claude Code after changing settings. Hooks run after `Edit` and `Write` calls and send file paths to Vim when `VIMBIOSIS_SESSION` is set.

To uninstall, remove these two skill links and only this hook entry from the settings array.
