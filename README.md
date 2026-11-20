# Vimbiosis

Vimbiosis connects Vim 8+ (best supported on Vim 9) to Codex and Claude Code.
Install this repository or a submodule as `~/.vim/pack/vendor/start/vimbiosis`.
Vim loads the plugin automatically.

Start with `:Vbio codex` or `:Vbio claude`. Vim supplies session-specific MCP
configuration to the agent in its terminal split. To start an external agent
against the same Vim instance, run `:VbioAttach` and use the printed exports
and launch command. See the [Claude setup guide](claude/INSTALL.md) or
[Codex setup guide](codex/INSTALL.md) for automatic prompt context and edit hooks.

The prompt hook supplies Vim's working directory and editable file buffers.
The prompt and edit hooks call the Vim-owned MCP listener directly.
When a file buffer has focus, it also supplies the cursor and any active Visual
selection range. Ask the agent to read unsaved buffer text, open a file at a
location, or focus an existing file window using Vimbiosis MCP tools.
To enable arbitrary Ex commands and mapped keys, set
`let g:vimbiosis_allow_arbitrary_actions = 1` in your vimrc. These actions run
with Vim's local permissions.

The bridge uses Vim's job and JSON channel callbacks. It requires Python 3
available as `python3` and a Vim built with `+job`, `+channel`, `+timers`, and
`+json`; terminal launching also requires `+terminal`. Clients connect through
MCP Streamable HTTP bound only to `127.0.0.1`, authenticated with a random per-session token,
using the same transport on macOS, Linux, and Windows.

On Windows, use Git Bash with `vim`, `python3`, and the agent commands
available on its PATH.

Configure both pre- and post-edit hooks using the setup guide for your agent.
Pre-edit checks block direct edits when a Vim buffer contains unsaved work and
ask the agent to wait for your decision. Passing checks capture a before
snapshot so completed edits can highlight added/changed lines and mark
deletions.

Use `:VbioChanges` to review changed regions across files, or `:VbioNext` and
`:VbioPrevious` to navigate them. Entering Insert mode clears the current
buffer's highlights, virtual text and deletion signs while retaining the change
list. `:VbioClear` clears the current buffer's markers manually;
`:VbioChangesClear` clears the list and all its markers. See `:help
vimbiosis-changes`.

On Vim builds with `+textprop` and patch 9.0.0438 or newer, diff markers are
prepended inline: `+` for additions and replacement text, and `-` for removed
original lines displayed as wrapping virtual text. Added and removed rows use
their respective highlight colors without opening a sign gutter. Set `let
g:vimbiosis_enable_virtual_text = 0` in your vimrc to use gutter signs instead:
`+` for additions, `~` for modifications (with a distinct highlight color), and
`-` for deletions. With Vim's default `signcolumn=auto`, the gutter appears
only while signs are present. The default virtual-text setting is `1`, read on
each repaint; unsupported builds use gutter signs. Virtual text never changes
buffer contents; replacement updates and all marker-clearing commands remove
it.

The review list opens automatically once it contains changes to multiple files,
preserving your keyboard focus. Single-file changes do not automatically open
the list. Set `let g:vimbiosis_auto_open_changes = 0` in your vimrc to disable
automatic opening.

## License

Vimbiosis is licensed under the GNU General Public License, version 3 or (at
your option) any later version. See [LICENSE](LICENSE) for the full license
text.
