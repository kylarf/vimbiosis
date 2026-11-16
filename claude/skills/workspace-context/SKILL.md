---
name: workspace-context
description: Use the files and live buffer contents in the user's attached Vim session as workspace context.
---

Perform editor actions without announcing skill use, mentioning Vimbiosis, or narrating actions in Vim. Answer the user's question directly. Report integration errors or conflicts only when they require the user's attention.

When the user refers to the editor workspace, run `vimbiosis buffers` first. Select relevant listed file buffers, then run `vimbiosis read-buffer PATH --start N --end M` to read their current contents, including unsaved Vim edits. Use the returned changedtick to detect stale reads. If Vim is unattached, use the current working directory as the fallback context.
