"""Transport tests using real bridge processes and simulated Vim replies."""
from concurrent.futures import ThreadPoolExecutor
import json
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

    def request(self, session, request):
        port, token = session.split(":")
        with socket.create_connection(("127.0.0.1", int(port)), timeout=3) as client:
            client.sendall((json.dumps({"token": token, "request": request}) + "\n").encode())
            with client.makefile(encoding="utf-8") as stream:
                return json.loads(stream.readline())

    def reply(self, proc, message, result):
        proc.stdin.write(json.dumps([0, {"reply_to": message["id"], "result": result}]) + "\n")
        proc.stdin.flush()

    def test_timeout_reaches_client(self):
        _, _, session = self.start_bridge(timeout=.05)
        with mock.patch.dict(os.environ, {"VIMBIOSIS_SESSION": session}):
            self.assertEqual(vimbiosis.send_payload({"op": "status"}),
                             {"ok": False, "error": "Vim request timed out"})

    def test_invalid_sessions_return_errors(self):
        for session in ("bad", "0:token", "65536:token", "123:", "path:old:token"):
            with self.subTest(session=session):
                with mock.patch.dict(os.environ, {"VIMBIOSIS_SESSION": session}):
                    self.assertFalse(vimbiosis.send_payload({"op": "status"})["ok"])

    def test_wrong_token_never_reaches_vim(self):
        _, messages, session = self.start_bridge()
        bad_session = session.split(":")[0] + ":incorrect"
        self.assertEqual(self.request(bad_session, {"op": "status"}),
                         {"ok": False, "error": "invalid session token"})
        self.assertTrue(messages.empty())

    def test_concurrent_requests_receive_their_own_replies(self):
        proc, messages, session = self.start_bridge()
        with ThreadPoolExecutor(max_workers=3) as pool:
            replies = [pool.submit(self.request, session, {"op": op})
                       for op in ("status", "buffers", "read-buffer")]
            requests = [messages.get(timeout=3) for _ in replies]
            for message in reversed(requests):
                self.reply(proc, message, {"ok": True, "op": message["request"]["op"]})
            self.assertEqual([reply.result(timeout=3)["op"] for reply in replies],
                             ["status", "buffers", "read-buffer"])

    def test_incomplete_client_times_out_without_blocking_others(self):
        proc, messages, session = self.start_bridge()
        port = int(session.split(":")[0])
        with socket.create_connection(("127.0.0.1", port), timeout=3) as idle:
            idle.sendall(b'{"token":')
            with ThreadPoolExecutor(max_workers=1) as pool:
                reply = pool.submit(self.request, session, {"op": "status"})
                self.reply(proc, messages.get(timeout=3), {"ok": True})
                self.assertEqual(reply.result(timeout=3), {"ok": True})
            with idle.makefile(encoding="utf-8") as stream:
                self.assertFalse(json.loads(stream.readline())["ok"])

    def test_sessions_are_independent_and_eof_stops_bridge(self):
        first, _, session = self.start_bridge()
        second, messages, other = self.start_bridge()
        self.assertNotEqual(session.split(":")[0], other.split(":")[0])
        self.assertNotEqual(session.split(":")[1], other.split(":")[1])
        self.assertFalse(self.request(other.split(":")[0] + ":" + session.split(":")[1],
                                      {"op": "status"})["ok"])
        self.assertTrue(messages.empty())
        port = int(session.split(":")[0])
        first.stdin.close()
        self.assertEqual(first.wait(timeout=3), 0)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", port), timeout=.2)
        self.assertIsNone(second.poll())
