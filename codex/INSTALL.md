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

## Post-edit hook

Append this TOML to `~/.codex/config.toml`:

```toml
[[hooks.PostToolUse]]
matcher = "^apply_patch$"

[[hooks.PostToolUse.hooks]]
type = "command"
command = 'python3 "ABSOLUTE_PATH_TO_VIMBIOSIS/codex/hooks/post-edit.py"'
```

Replace `ABSOLUTE_PATH_TO_VIMBIOSIS` with this checkout's path. Append these hook tables alongside existing settings; do not overwrite `config.toml`. Codex runs the hook after `apply_patch`, and it forwards the changed paths to Vim when `VIMBIOSIS_SESSION` is set.

To uninstall, remove these two skill links and only the matching hook tables from `config.toml`.
