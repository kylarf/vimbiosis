#!/usr/bin/env python3
"""Claude Code PreToolUse/PostToolUse adapter."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
from hooks import run

run("claude")
