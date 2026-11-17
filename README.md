# Vimbiosis

Vimbiosis connects Vim 8+ (best supported on Vim 9) to Codex and Claude Code. Install this repository or a submodule as `~/.vim/pack/vendor/start/vimbiosis`. Vim loads the plugin automatically.

Add this checkout's `bin/` directory to `PATH` for external agent sessions. `:Vbio codex` and `:Vbio claude` add it to the launched terminal's PATH automatically. `:VbioAttach` starts an external attachment and prints the `VIMBIOSIS_SESSION` export command; run that command in the shell before launching the agent.

Commands include `:VbioStatus`, `:VbioDetach`, and `:VbioFollow`. The `vimbiosis` CLI provides `status`, `buffers`, `read-buffer`, `open`, and `notify`. Follow the [Claude setup guide](claude/INSTALL.md) or [Codex setup guide](codex/INSTALL.md) to link the skills and add the post-edit hook while preserving your existing configuration.

Consider adding an instruction to your local or global `AGENTS.md` or `CLAUDE.md` to use the `show-code` skill when you ask where code is or ask to see it. This encourages the agent to automatically show the relevant code directly in your Vim session when appropriate.

Add an instruction to your global or project `AGENTS.md` to interpret “my workspace” or workspace-state questions as referring to the attached live editor session when Vimbiosis is active, and use the `workspace-context` skill to inspect it. This includes currently open files, unsaved edits, and Vim state. For general repository questions, the agent can search the files first and consult live workspace context when it may affect the answer.

The bridge uses Vim's job and JSON channel callbacks. It requires Python 3 available as `python3` and a Vim built with `+job`, `+channel`, `+timers`, and `+json`; terminal launching also requires `+terminal`. Clients connect through TCP bound only to `127.0.0.1`, authenticated with a random per-session token, using the same transport on macOS, Linux, and Windows.

On Windows, use Git Bash with `vim`, `python3`, and the agent commands available on its PATH. The Bash entry point and agent launch commands are the same across platforms.

Configure both pre- and post-edit hooks using the setup guide for your agent. Pre-edit checks block direct edits when a Vim buffer contains unsaved work and ask the agent to wait for your decision. Passing checks capture a before snapshot so completed edits can highlight added/changed lines and mark deletions.

Use `:VbioChanges` to review changed regions across files, or `:VbioNext` and `:VbioPrevious` to navigate them. Entering Insert mode clears the current buffer's highlights, virtual text and deletion signs while retaining the change list. `:VbioClear` clears the current buffer's markers manually; `:VbioChangesClear` clears the list and all its markers. See `:help vimbiosis-changes`.

On Vim builds with `+textprop` and patch 9.0.0438 or newer, diff markers appear inline: `+` for additions and replacement text, and `-` for removed original lines displayed as wrapping virtual text. Removal markers replace the first character when it is whitespace, otherwise they are prepended without a space. Added and removed rows use their respective highlight colors without opening a sign gutter. Set `let g:vimbiosis_enable_virtual_text = 0` in your vimrc to use gutter signs instead: `+` for additions, `~` for modifications (with a distinct highlight color), and `-` for deletions. With Vim's default `signcolumn=auto`, the gutter appears only while signs are present. The default virtual-text setting is `1`, read on each repaint; unsupported builds use gutter signs. Virtual text never changes buffer contents; replacement updates and all marker-clearing commands remove it.

The review list opens automatically once it contains changes to multiple files, preserving your keyboard focus. Single-file changes do not automatically open the list.

## License

Vimbiosis is licensed under the GNU General Public License, version 3 or (at your option) any later version. See [LICENSE](LICENSE) for the full license text.
