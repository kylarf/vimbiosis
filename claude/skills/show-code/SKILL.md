---
name: show-code
description: Open relevant source code in the user's attached Vim session when they ask where code lives or ask to inspect a code section.
---

Find the relevant file and line range, then run `vimbiosis open PATH --line N` for the primary location. Use `--column N` when useful. For multiple locations, open each in turn and leave the main result focused. Explain the code with file and line references after opening it. If the command reports that no Vim session is attached, continue with normal file references.
