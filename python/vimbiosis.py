#!/usr/bin/env python3
"""Vimbiosis command line client and Vim-owned bridge."""
import argparse
import json
import os
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
    address, token = descriptor.rsplit(":", 1)
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(CLIENT_TIMEOUT)
            client.connect(address)
            client.sendall((json.dumps({"token": token, "request": request}) + "\n").encode())
            return json.loads(client.makefile().readline())
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
    try:
        os.unlink(args.socket)
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX)
    server.bind(args.socket)
    os.chmod(args.socket, 0o600)
    server.listen()
    pending = {}
    snapshots = Snapshots()
    lock = threading.Lock()
    output_lock = threading.Lock()

    def client_loop(conn):
        with conn:
            try:
                msg = json.loads(conn.makefile().readline())
                if msg.get("token") != args.token:
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
                with lock:
                    pending.pop(key, None)
            except (OSError, ValueError, KeyError) as exc:
                try:
                    conn.sendall((json.dumps({"ok": False, "error": str(exc)}) + "\n").encode())
                except OSError:
                    pass

    def stdin_loop():
        while True:
            line = sys.stdin.readline()
            if not line:
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

    threading.Thread(target=stdin_loop, daemon=True).start()
    try:
        while True:
            conn, _ = server.accept()
            threading.Thread(target=client_loop, args=(conn,), daemon=True).start()
    finally:
        server.close()
        try:
            os.unlink(args.socket)
        except FileNotFoundError:
            pass


def main():
    parser = argparse.ArgumentParser(prog="vimbiosis")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bridge")
    b.add_argument("--socket", required=True)
    b.add_argument("--token", required=True)
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
