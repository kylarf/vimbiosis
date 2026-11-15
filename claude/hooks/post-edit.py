#!/usr/bin/env python3
"""Claude Code PostToolUse hook: forward direct edits to Vim."""
import json
import os
import subprocess
import sys

payload = json.load(sys.stdin)
tool = payload.get("tool_input", {})
paths = [tool.get("file_path", "")]
paths = [p for p in paths if p]
if paths and os.environ.get("VIMBIOSIS_SESSION"):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    subprocess.run([root + "/bin/vimbiosis", "notify", *paths], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
