# Vimbiosis

Vimbiosis connects Vim 8+ (best supported on Vim 9) to Codex and Claude Code. Install this repository or a submodule as `~/.vim/pack/vendor/start/vimbiosis`. Vim loads the plugin automatically.

Add this checkout's `bin/` directory to `PATH` for external agent sessions. `:Vbio codex` and `:Vbio claude` add it to the launched terminal's PATH automatically. `:VbioAttach` starts an external attachment and prints the `VIMBIOSIS_SESSION` export command; run that command in the shell before launching the agent.

Commands include `:VbioStatus`, `:VbioDetach`, and `:VbioFollow`. The `vimbiosis` CLI provides `status`, `buffers`, `read-buffer`, `open`, and `notify`. Follow the [Claude setup guide](claude/INSTALL.md) or [Codex setup guide](codex/INSTALL.md) to link the skills and add the post-edit hook while preserving your existing configuration.

Consider adding an instruction to your local or global `AGENTS.md` or `CLAUDE.md` to use the `show-code` skill when you ask where code is or ask to see it. This encourages the agent to automatically show the relevant code directly in your Vim session when appropriate.

The bridge uses Vim's job and JSON channel callbacks. It requires Python 3 and a Vim built with `+job`, `+channel`, `+timers`, and `+json`; terminal launching also requires `+terminal`. The bridge uses a private Unix-domain socket on macOS/Linux.

Configure both pre- and post-edit hooks using the setup guide for your agent. Pre-edit checks block direct edits when a Vim buffer contains unsaved work and ask the agent to wait for your decision. Passing checks capture a before snapshot so completed edits can highlight added/changed lines and mark deletions.

Use `:VbioChanges` to review changed regions across files, or `:VbioNext` and `:VbioPrevious` to navigate them. Entering Insert mode clears the current buffer's highlights and deletion signs while retaining the change list. `:VbioClear` clears the current buffer's markers manually; `:VbioChangesClear` clears the list and all its markers. See `:help vimbiosis-changes`.

The review list opens automatically once it contains changes to multiple files, preserving your keyboard focus. Single-file changes do not automatically open the list.

## License

Vimbiosis is licensed under the GNU General Public License, version 3 or (at your option) any later version. See [LICENSE](LICENSE) for the full license text.
