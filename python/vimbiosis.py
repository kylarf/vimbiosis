#!/usr/bin/env python3
"""Vimbiosis command line client and Vim-owned bridge."""
import argparse
import json
import os
import secrets
import socket
import sys
import threading
import uuid
from changes import Snapshots

VIM_REPLY_TIMEOUT = 5
CLIENT_TIMEOUT = VIM_REPLY_TIMEOUT + 3


def send_payload(request):
    descriptor = os.environ.get("VIMBIOSIS_SESSION")
    if not descriptor:
        return {"ok": False, "error": "not attached (VIMBIOSIS_SESSION is unset)"}
    try:
        port, token = descriptor.split(":")
        if not token or not 0 < int(port) < 65536:
            raise ValueError("invalid session descriptor; attach again")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.settimeout(CLIENT_TIMEOUT)
            client.connect(("127.0.0.1", int(port)))
            client.sendall((json.dumps({"token": token, "request": request}) + "\n").encode())
            with client.makefile(encoding="utf-8") as stream:
                return json.loads(stream.readline())
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": "Vim bridge unavailable: " + str(exc)}


def send_request(args):
    request = vars(args).copy()
    request["op"] = request.pop("command")
    for name in ("path",):
        if name in request:
            request[name] = os.path.abspath(request[name])
    if "files" in request:
        request["files"] = [os.path.abspath(path) for path in request["files"]]
    return send_payload(request)


def bridge(args):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen()
    server.settimeout(.2)
    token = secrets.token_hex(32)
    stopped = threading.Event()
    pending = {}
    snapshots = Snapshots()
    lock = threading.Lock()
    output_lock = threading.Lock()

    def client_loop(conn):
        key = None
        with conn:
            try:
                conn.settimeout(CLIENT_TIMEOUT)
                with conn.makefile(encoding="utf-8") as stream:
                    msg = json.loads(stream.readline())
                if not secrets.compare_digest(str(msg.get("token", "")), token):
                    conn.sendall(b'{"ok":false,"error":"invalid session token"}\n')
                    return
                request = msg["request"]
                operation = request.get("op")
                if operation == "notify":
                    targets = request.get("targets", [{"path": p} for p in request["files"]])
                    with lock:
                        request["changes"] = snapshots.finish(request.get("hook_id", ""), targets)
                key = uuid.uuid4().hex
                event = threading.Event()
                with lock:
                    pending[key] = [event, None]
                with output_lock:
                    print(json.dumps([0, {"id": key, "request": request}]), flush=True)
                if event.wait(VIM_REPLY_TIMEOUT):
                    result = pending[key][1]
                    if operation == "before" and result.get("ok"):
                        with lock:
                            snapshots.capture(request.get("hook_id", ""), request["files"])
                    conn.sendall((json.dumps(result) + "\n").encode())
                else:
                    conn.sendall(b'{"ok":false,"error":"Vim request timed out"}\n')
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                try:
                    conn.sendall((json.dumps({"ok": False, "error": str(exc)}) + "\n").encode())
                except OSError:
                    pass
            finally:
                with lock:
                    pending.pop(key, None)

    def stdin_loop():
        while True:
            line = sys.stdin.readline()
            if not line:
                stopped.set()
                return
            try:
                message = json.loads(line)
                value = message[1]
                key = value.get("reply_to")
                with lock:
                    if key in pending:
                        pending[key][1] = value.get("result")
                        pending[key][0].set()
            except (ValueError, IndexError, AttributeError):
                continue

    try:
        print(json.dumps([0, {"event": "ready", "session":
                              str(server.getsockname()[1]) + ":" + token}]), flush=True)
        threading.Thread(target=stdin_loop, daemon=True).start()
        while not stopped.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            threading.Thread(target=client_loop, args=(conn,), daemon=True).start()
    finally:
        server.close()


def main():
    parser = argparse.ArgumentParser(prog="vimbiosis")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("bridge")
    for name in ("status", "buffers"):
        sub.add_parser(name)
    opened = sub.add_parser("open")
    opened.add_argument("path")
    opened.add_argument("--line", type=int, default=1)
    opened.add_argument("--column", type=int, default=1)
    opened.add_argument("--vertical", action="store_true")
    read = sub.add_parser("read-buffer")
    read.add_argument("path")
    read.add_argument("--start", type=int, default=1)
    read.add_argument("--end", type=int, default=1000000)
    notify = sub.add_parser("notify")
    notify.add_argument("files", nargs="+")
    args = parser.parse_args()
    result = bridge(args) if args.command == "bridge" else send_request(args)
    if args.command != "bridge":
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
