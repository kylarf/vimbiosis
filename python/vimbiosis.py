"""Vim-owned HTTP listener and internal client for agent hooks."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import sys
import threading
import time
from urllib.request import ProxyHandler, Request, build_opener

from changes import Snapshots
from mcp_tools import PROTOCOL_VERSIONS, rpc

VIM_REPLY_TIMEOUT = 5
CLIENT_TIMEOUT = 8
MAX_BODY = 2 * 1024 * 1024


def send_payload(request, timeout=CLIENT_TIMEOUT):
    """Call a Vim MCP tool from a short-lived agent hook process."""
    try:
        port, token = os.environ.get("VIMBIOSIS_SESSION", "").split(":")
        if not token or not 0 < int(port) < 65536:
            raise ValueError("invalid session descriptor")
        operation = request["op"]
        endpoint = "/mcp" if operation == "workspace" else "/hooks"
        opener = build_opener(ProxyHandler({}))
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream"}

        def call(method, params, request_id=None):
            body = {"jsonrpc": "2.0", "method": method, "params": params}
            if request_id is not None:
                body["id"] = request_id
            message = Request(f"http://127.0.0.1:{int(port)}{endpoint}",
                              json.dumps(body).encode(), headers)
            with opener.open(message, timeout=timeout) as reply:
                if request_id is not None:
                    return json.load(reply)["result"]
            return None

        version = PROTOCOL_VERSIONS[0]
        initialized = call("initialize", {"protocolVersion": version, "capabilities": {},
                                         "clientInfo": {"name": "Vimbiosis hook",
                                                        "version": "1.0.0"}}, 1)
        headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
        call("notifications/initialized", {})
        result = call("tools/call", {"name": operation, "arguments": {
            key: value for key, value in request.items() if key != "op"}}, 2)
        return json.loads(result["content"][0]["text"])
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        return {"ok": False, "error": "Vim bridge unavailable: " + str(exc)}


def bridge():
    token = secrets.token_hex(32)
    pending = {}
    snapshots = Snapshots()
    lock = threading.Lock()
    output_lock = threading.Lock()

    def dispatch(request):
        key = secrets.token_hex(16)
        event = threading.Event()
        operation = request["op"]
        with lock:
            if operation == "notify":
                targets = request.get("targets")
                if targets is None:
                    targets = [{"path": path} for path in request["files"]]
                request["changes"] = snapshots.finish(request.get("hook_id", ""), targets)
            pending[key] = [event, None]
        try:
            with output_lock:
                deadline = int((time.time() + VIM_REPLY_TIMEOUT) * 1000)
                print(json.dumps([0, {"id": key, "request": request,
                                      "deadline": deadline}]), flush=True)
            if not event.wait(VIM_REPLY_TIMEOUT):
                return {"ok": False, "error": "Vim request timed out"}
            with lock:
                result = pending[key][1]
                if operation == "before" and result.get("ok"):
                    snapshots.capture(request.get("hook_id", ""), request["files"])
            return result
        finally:
            with lock:
                pending.pop(key, None)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(CLIENT_TIMEOUT)
            super().setup()

        def log_message(self, *_):
            pass

        def respond(self, status, body=None):
            data = b"" if body is None else json.dumps(body).encode()
            self.send_response(status)
            if data:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def authorized(self):
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get_all("Host") != [host] or self.headers.get_all("Origin") not in (
                    None, ["http://" + host]):
                self.respond(403)
                return False
            authorization = self.headers.get_all("Authorization")
            if not authorization or len(authorization) != 1 or not hmac.compare_digest(
                    authorization[0].encode(), ("Bearer " + token).encode()):
                self.respond(401)
                return False
            return True

        def do_GET(self):
            if self.authorized():
                self.respond(405 if self.path == "/mcp" else 404)

        do_DELETE = do_GET

        def do_POST(self):
            if not self.authorized():
                return
            if self.path not in ("/mcp", "/hooks"):
                self.respond(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY or self.headers.get("Transfer-Encoding"):
                    self.respond(413)
                    return
                if self.headers.get_content_type() != "application/json":
                    self.respond(415)
                    return
                request = json.loads(self.rfile.read(length))
            except (ValueError, OSError):
                self.respond(400, {"jsonrpc": "2.0", "id": None,
                                   "error": {"code": -32700, "message": "Invalid JSON"}})
                return
            version = self.headers.get("MCP-Protocol-Version")
            if version is not None and version not in PROTOCOL_VERSIONS:
                self.respond(400)
                return
            response = rpc(request, dispatch, hooks=self.path == "/hooks")
            self.respond(202 if response is None else 200, response)

    def read_vim():
        for line in sys.stdin:
            try:
                reply = json.loads(line)[1]
                with lock:
                    item = pending.get(reply["reply_to"])
                    if item:
                        item[1] = reply["result"]
                        item[0].set()
            except (ValueError, IndexError, KeyError, TypeError):
                continue
        server.shutdown()

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        print(json.dumps([0, {"event": "ready",
                              "session": f"{server.server_port}:{token}"}]), flush=True)
        threading.Thread(target=read_vim, daemon=True).start()
        server.serve_forever(poll_interval=.2)


def main():
    bridge()


if __name__ == "__main__":
    main()
