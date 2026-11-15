#!/usr/bin/env python3
"""Codex PostToolUse hook: forward apply_patch paths to Vim."""
import json
import os
import re
import subprocess
import sys

payload = json.load(sys.stdin)
patch = payload.get("tool_input", {}).get("command", "")
paths = re.findall(r"^\+\+\+ (?:b/)?(.+)$", patch, re.MULTILINE)
paths = [p for p in paths if p != "/dev/null"]
if paths and os.environ.get("VIMBIOSIS_SESSION"):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    subprocess.run([root + "/bin/vimbiosis", "notify", *paths], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
