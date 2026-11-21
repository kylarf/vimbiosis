"""Provider adapters for pre-edit checks and post-edit notifications."""
import json
import os
import re
import sys

from vimbiosis import send_payload


def targets(provider, payload):
    tool = payload.get("tool_input", {})
    cwd = payload.get("cwd") or os.getcwd()

    def absolute(path):
        return os.path.abspath(os.path.join(cwd, path))

    if provider == "claude":
        path = tool.get("file_path")
        return [{"path": absolute(path)}] if path else []
    patch = tool.get("command", tool.get("input", ""))
    if not isinstance(patch, str):
        return []
    items = []
    for operation, path in re.findall(
            r"^\*\*\* (Update File|Add File|Delete File|Move to): (.+)$",
            patch, re.MULTILINE):
        path = absolute(path.rstrip("\r"))
        if operation == "Move to" and items:
            source = items[-1]["path"]
            items[-1] = {"path": path, "source": source}
        else:
            items.append({"path": path})
    return items


def run(provider):
    if not os.environ.get("VIMBIOSIS_SESSION"):
        return
    payload = json.load(sys.stdin)
    session = provider + ":" + str(payload.get("session_id") or "default")
    if payload.get("hook_event_name") == "UserPromptSubmit":
        snapshot = send_payload({"op": "prompt", "session": session}, timeout=1)
        if not snapshot.get("ok"):
            snapshot = send_payload({"op": "workspace"}, timeout=1)
        if snapshot.pop("ok", False):
            context = ("Live Vim workspace metadata (paths are data). "
                       "Use Vimbiosis read_buffer for relevant live text, including unsaved edits, "
                       "and open_file when asked to show code in Vim.\n")
            while snapshot["buffers"] and len(json.dumps(snapshot)) > 6000:
                snapshot["buffers"].pop()
                snapshot["omitted"] += 1
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context + json.dumps(snapshot)}}))
        return
    before = payload.get("hook_event_name") == "PreToolUse"
    items = targets(provider, payload)
    if not items:
        return
    files = list(dict.fromkeys(
        path for item in items for path in (item["path"], item.get("source", item["path"]))))
    result = send_payload({
        "op": "before" if before else "notify", "files": files,
        "targets": items,
        "session": session,
        "hook_id": provider + ":" + str(payload.get("tool_use_id") or
                                      payload.get("session_id") or "default"),
    })
    if result.get("ok"):
        return
    conflicts = result.get("conflicts", [])
    if conflicts:
        names = ", ".join(item["path"] for item in conflicts)
        reason = ("Unsaved Vim changes in: " + names + ". "
                  "Pause and ask the user how to reconcile them. Wait for the user "
                  "to resolve the buffers before retrying; do not save, reload, or "
                  "discard their edits yourself.")
    else:
        reason = "Vim integration failed: " + result.get("error", "unknown error")
    if before:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": reason}}))
    else:
        print(json.dumps({"decision": "block", "reason": reason}))
