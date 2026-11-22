"""Transport tests using real bridge processes and simulated Vim replies."""
from concurrent.futures import ThreadPoolExecutor
import json
from http.client import HTTPConnection
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import vimbiosis


class BridgeTests(unittest.TestCase):
    def start_bridge(self, timeout=2, client_timeout=.2):
        code = ("import sys; sys.path.insert(0, " + repr(str(ROOT / "python")) +
                "); import vimbiosis; vimbiosis.VIM_REPLY_TIMEOUT = " + repr(timeout) +
                "; vimbiosis.CLIENT_TIMEOUT = " + repr(client_timeout) +
                "; vimbiosis.main()")
        proc = subprocess.Popen([sys.executable, "-c", code, "bridge"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        messages = queue.Queue()

        def read_messages():
            for line in proc.stdout:
                messages.put(json.loads(line)[1])

        reader = threading.Thread(target=read_messages)
        reader.start()

        def cleanup():
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=3)
            reader.join(timeout=3)
            proc.stdin.close()
            proc.stdout.close()
            proc.stderr.close()

        self.addCleanup(cleanup)
        ready = messages.get(timeout=3)
        self.assertEqual(ready["event"], "ready")
        port, token = ready["session"].split(":")
        self.assertTrue(0 < int(port) < 65536)
        self.assertRegex(token, r"^[0-9a-f]{64}$")
        return proc, messages, ready["session"]

    def request(self, session, request, path="/hooks", origin=None):
        port, token = session.split(":")
        client = HTTPConnection("127.0.0.1", int(port), timeout=3)
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        operation = request.get("op")
        if operation:
            if operation == "workspace":
                path = "/mcp"
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": operation, "arguments": {
                           key: value for key, value in request.items() if key != "op"}}}
        try:
            client.request("POST", path, json.dumps(request), headers)
            reply = client.getresponse()
            body = reply.read()
            if not body:
                return reply.status
            result = json.loads(body)
            if operation:
                return json.loads(result["result"]["content"][0]["text"])
            return result
        finally:
            client.close()

    def reply(self, proc, message, result):
        proc.stdin.write(json.dumps([0, {"reply_to": message["id"], "result": result}]) + "\n")
        proc.stdin.flush()

    def test_timeout_reaches_client(self):
        _, _, session = self.start_bridge(timeout=.05)
        with mock.patch.dict(os.environ, {"VIMBIOSIS_SESSION": session}):
            self.assertEqual(vimbiosis.send_payload({"op": "workspace"}),
                             {"ok": False, "error": "Vim request timed out"})

    def test_invalid_sessions_return_errors(self):
        for session in ("bad", "0:token", "65536:token", "123:", "path:old:token"):
            with self.subTest(session=session):
                with mock.patch.dict(os.environ, {"VIMBIOSIS_SESSION": session}):
                    self.assertFalse(vimbiosis.send_payload({"op": "workspace"})["ok"])

    def test_wrong_token_never_reaches_vim(self):
        _, messages, session = self.start_bridge()
        bad_session = session.split(":")[0] + ":incorrect"
        self.assertEqual(self.request(bad_session, {"op": "workspace"}), 401)
        self.assertEqual(self.request(session, {"op": "workspace"},
                                      origin="http://invalid.example"), 403)
        self.assertTrue(messages.empty())

    def test_concurrent_requests_receive_their_own_replies(self):
        proc, messages, session = self.start_bridge()
        with ThreadPoolExecutor(max_workers=3) as pool:
            replies = [pool.submit(self.request, session, {"op": "before", "files": [str(index)]})
                       for index in range(3)]
            requests = [messages.get(timeout=3) for _ in replies]
            for message in reversed(requests):
                self.reply(proc, message, {"ok": False, "index": message["request"]["files"][0]})
            self.assertEqual([reply.result(timeout=3)["index"] for reply in replies], ["0", "1", "2"])

    def test_incomplete_client_times_out_without_blocking_others(self):
        proc, messages, session = self.start_bridge()
        port = int(session.split(":")[0])
        with socket.create_connection(("127.0.0.1", port), timeout=3) as idle:
            idle.sendall(b'POST /mcp HTTP/1.1\r\nHost:')
            with ThreadPoolExecutor(max_workers=1) as pool:
                reply = pool.submit(self.request, session, {"op": "workspace"})
                self.reply(proc, messages.get(timeout=3), {"ok": True})
                self.assertEqual(reply.result(timeout=3), {"ok": True})
            with idle.makefile(encoding="utf-8") as stream:
                self.assertEqual(stream.readline(), "")

    def test_sessions_are_independent_and_eof_stops_bridge(self):
        first, _, session = self.start_bridge()
        second, messages, other = self.start_bridge()
        self.assertNotEqual(session.split(":")[0], other.split(":")[0])
        self.assertNotEqual(session.split(":")[1], other.split(":")[1])
        self.assertEqual(self.request(other.split(":")[0] + ":" + session.split(":")[1],
                                      {"op": "workspace"}), 401)
        self.assertTrue(messages.empty())
        port = int(session.split(":")[0])
        first.stdin.close()
        self.assertEqual(first.wait(timeout=3), 0)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=.2)
        self.assertIsNone(second.poll())

    def test_mcp_tools_and_dispatch(self):
        proc, messages, session = self.start_bridge()

        def request(method, params=None):
            return self.request(session, {"jsonrpc": "2.0", "id": 1,
                                          "method": method, "params": params or {}}, "/mcp")

        self.assertEqual(request("initialize", {"protocolVersion": "2025-11-25"})
                         ["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("focus_window", [tool["name"] for tool in request("tools/list")
                                       ["result"]["tools"]])
        self.assertEqual(request("tools/call", {"name": "focus_window",
                                               "arguments": {"winid": True}})
                         ["error"]["code"], -32602)
        with ThreadPoolExecutor(max_workers=1) as pool:
            reply = pool.submit(request, "tools/call", {"name": "workspace"})
            message = messages.get(timeout=3)
            self.assertEqual(message["request"], {"op": "workspace"})
            self.reply(proc, message, {"ok": True, "buffers": []})
            self.assertFalse(reply.result(timeout=3)["result"]["isError"])
