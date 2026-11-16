#!/usr/bin/env python3
"""Codex PostToolUse hook: forward apply_patch paths to Vim."""
import json
import os
import re
import subprocess
import sys

payload = json.load(sys.stdin)
patch = payload.get("tool_input", {}).get("command", "")
paths = re.findall(
    r"^\*\*\* (?:Update File|Add File|Move to): (.+)$", patch, re.MULTILINE
)
cwd = payload.get("cwd") or os.getcwd()
paths = [os.path.abspath(os.path.join(cwd, p)) for p in paths]
paths = list(dict.fromkeys(p for p in paths if os.path.isfile(p)))
if paths and os.environ.get("VIMBIOSIS_SESSION"):
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    subprocess.run([root + "/bin/vimbiosis", "notify", *paths], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
