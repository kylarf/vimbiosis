# Vimbiosis

Vimbiosis connects Vim 8+ (best supported on Vim 9) to Codex and Claude Code. Install this repository or a submodule as `~/.vim/pack/vendor/start/vimbiosis`. Vim loads the plugin automatically.

Add this checkout's `bin/` directory to `PATH` for external agent sessions. `:Vbio codex` and `:Vbio claude` add it to the launched terminal's PATH automatically. `:VbioAttach` starts an external attachment and prints the `VIMBIOSIS_SESSION` export command; run that command in the shell before launching the agent.

Commands include `:VbioStatus`, `:VbioDetach`, and `:VbioFollow`. The `vimbiosis` CLI provides `status`, `buffers`, `read-buffer`, `open`, and `notify`. Follow the [Claude setup guide](claude/INSTALL.md) or [Codex setup guide](codex/INSTALL.md) to link the skills and add the post-edit hook while preserving your existing configuration.

The bridge uses Vim's job and JSON channel callbacks. It requires Python 3 and a Vim built with `+job`, `+channel`, `+timers`, and `+json`; terminal launching also requires `+terminal`. The bridge uses a private Unix-domain socket on macOS/Linux.
