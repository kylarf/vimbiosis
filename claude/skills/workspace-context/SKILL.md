---
name: workspace-context
description: Use the files and live buffer contents in the user's attached Vim session as workspace context.
---

Perform editor actions without announcing skill use, mentioning Vimbiosis, or narrating actions in Vim. Answer the user's question directly. Report integration errors or conflicts only when they require the user's attention.

When the user refers to “my workspace” or asks about workspace state, treat that as the attached live Vim session. For other questions, use repository and filesystem context as usual, and consult live Vim context when it may affect the answer. For workspace questions, run `vimbiosis buffers` first. Silently skip Vimbiosis-owned and terminal buffers because `vimbiosis read-buffer` does not work on them; do not read or mention those buffers. Treat every relevant listed file buffer as part of the workspace, even when it is not visible in a window. Read loaded buffers with `vimbiosis read-buffer PATH --start N --end M` to include unsaved edits, and use the returned changedtick to detect stale reads. If a listed buffer appears unloaded, read its file from disk using the workspace working directory. If Vim is unattached, use the current working directory as the fallback context.
