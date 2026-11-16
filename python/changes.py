"""Before/after snapshots and line ranges for a completed edit."""
import difflib
from pathlib import Path
import time


def read_lines(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []


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
    return result


class Snapshots:
    def __init__(self):
        self.pending = {}

    def capture(self, key, files):
        now = time.monotonic()
        self.pending = {k: v for k, v in self.pending.items() if now - v[0] < 600}
        if len(self.pending) >= 64:
            self.pending.pop(next(iter(self.pending)))
        self.pending[key] = (now, {path: read_lines(path) for path in files})

    def finish(self, key, targets):
        _, before = self.pending.pop(key, (0, {}))
        changes = []
        for target in targets:
            path = target["path"]
            after = read_lines(path)
            source = target.get("source", path)
            if source in before:
                ranges = hunks(before[source], after)
            else:
                # Post-only/manual notifications have no reliable before version.
                ranges = [{"line": 1, "end_line": 1,
                           "kind": "unknown", "text": "File changed (no before snapshot)"}]
            deleted = not Path(path).exists()
            if deleted and not ranges:
                ranges = [{"line": 1, "end_line": 1, "kind": "deleted",
                           "text": "File deleted"}]
            elif source != path and not ranges:
                ranges = [{"line": 1, "end_line": 1, "kind": "changed",
                           "text": "File moved from " + source}]
            changes.append({"path": path, "hunks": ranges, "deleted": deleted})
        return changes
