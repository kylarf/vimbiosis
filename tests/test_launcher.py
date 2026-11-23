"""Regression coverage for session selection and external agent argv."""
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
import launcher
import vimbiosis


class LauncherTests(unittest.TestCase):
    def test_selection_and_listing(self):
        cwd = os.getcwd()
        first = ("aaaaaaaa", "123:one", {"cwd": cwd, "active": {"path": "first.py"}})
        second = ("bbbbbbbb", "456:two", {"cwd": cwd, "active": {"path": "second.py"}})
        with patch.object(launcher, "discover", return_value=[first]) as discover:
            self.assertEqual(launcher.select(None), first)
            discover.return_value = [first, second]
            with redirect_stderr(io.StringIO()) as output:
                self.assertIsNone(launcher.select(None))
            self.assertIn(f"aaaaaaaa\t{cwd}\tfirst.py", output.getvalue())
            self.assertIn(f"bbbbbbbb\t{cwd}\tsecond.py", output.getvalue())
            with patch.object(launcher, "inspect", return_value=second):
                self.assertEqual(launcher.select("bbbbbbbb"), second)
            with tempfile.TemporaryDirectory() as other:
                with patch.object(launcher.os, "getcwd", return_value=other):
                    with redirect_stderr(io.StringIO()):
                        self.assertIsNone(launcher.select(None))

    def test_registry_and_stale_endpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "vimbiosis" / "sessions"
            with patch.object(vimbiosis, "registry", return_value=root):
                first = vimbiosis.publish(123, "a" * 64)
                second = vimbiosis.publish(456, "b" * 64)
            self.assertNotEqual(first, second)
            self.assertEqual(json.loads((first / "session.json").read_text()),
                             {"port": 123, "token": "a" * 64})
            with patch.object(launcher, "send_payload", return_value={"ok": False}) as request:
                self.assertIsNone(launcher.inspect(first, True))
            request.assert_called_once_with({"op": "probe"}, timeout=1,
                                            session="123:" + "a" * 64)

    @unittest.skipIf(os.name == "nt", "checks the POSIX exec handoff")
    def test_agent_arguments_and_environment(self):
        args = ["resume", "-s", "", "a b", 'a"b', "/literal"]
        for agent in ("codex", "claude"):
            with self.subTest(agent=agent), patch.object(launcher.os, "execvpe") as execute:
                launcher.launch([agent, *args], "123:token")
                executable, argv, env = execute.call_args.args
                self.assertEqual(executable, agent)
                self.assertEqual(argv[-len(args):], args)
                self.assertEqual(env["VIMBIOSIS_SESSION"], "123:token")
                self.assertEqual(env["VIMBIOSIS_MCP_BEARER"], "token")
                if agent == "codex":
                    self.assertIn("--no-daemon", argv)
                    self.assertIn('mcp_servers.vimbiosis.url="http://127.0.0.1:123/mcp"', argv)
                else:
                    config = json.loads(argv[2])["mcpServers"]["vimbiosis"]
                    self.assertEqual(config["url"], "http://127.0.0.1:123/mcp")
