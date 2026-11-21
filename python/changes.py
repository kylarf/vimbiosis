"""Before/after snapshots and line ranges for a completed edit."""
import difflib
from pathlib import Path
import time


def read_lines(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return None


def hunks(before, after):
    result = []
    for tag, a, b, c, d in difflib.SequenceMatcher(
            None, before, after, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        kind = {"insert": "added", "replace": "changed", "delete": "deleted"}[tag]
        line = min(c + 1, max(1, len(after)))
        result.append({
            "line": line, "end_line": max(line, d), "kind": kind,
            "text": "{} (+{}/-{} lines)".format(kind.capitalize(), d - c, b - a),
        })
        if b > a:
            result[-1].update(removed_lines=before[a:b],
                              removed_placement="above" if c < len(after) else "below")
    return result


class Snapshots:
    def __init__(self):
        self.pending = {}
        self.prompts = {}

    def reset(self, session):
        self.prompts[session] = {}

    def capture(self, key, files, session="", baseline=None):
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if now - v[0] < 600}
        if len(self.pending) >= 64:
            self.pending.pop(next(iter(self.pending)))
        before = {} if baseline is None else baseline
        for path in files:
            if path not in before:
                before[path] = read_lines(path)
        self.pending[session, key] = (now, baseline, {path: before[path] for path in files})

    def finish(self, key, targets, session=""):
        captured, baseline, before = self.pending.pop((session, key), (None, None, {}))
        if captured is not None and baseline is not self.prompts.get(session):
            return []
        changes = []
        for target in targets:
            path = target["path"]
            after = read_lines(path)
            source = target.get("source", path)
            if source in before:
                ranges = hunks(before[source] or [], after or [])
            else:
                # Post-only/manual notifications have no reliable before version.
                ranges = [{"line": 1, "end_line": 1,
                           "kind": "unknown", "text": "File changed (no before snapshot)"}]
            deleted = after is None
            if deleted and not ranges and before[source] is not None:
                ranges = [{"line": 1, "end_line": 1, "kind": "deleted",
                           "text": "File deleted"}]
            elif source != path and not ranges:
                ranges = [{"line": 1, "end_line": 1, "kind": "changed",
                           "text": "File moved from " + source}]
            if source != path and source in before and baseline is not None and not deleted:
                baseline[path] = before[source]
                changes.append({"path": source, "hunks": [], "deleted": True})
            changes.append({"path": path, "hunks": ranges, "deleted": deleted})
        return changes
