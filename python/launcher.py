"""Select a live Vim session and start an external agent."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import shutil
import subprocess
import sys

from vimbiosis import registry, send_payload


def native_path(path):
    if os.name == "nt" and path.startswith("/"):
        return subprocess.check_output(["cygpath", "-w", path], text=True).strip()
    return path


def directory_key(path):
    return os.path.normcase(os.path.realpath(native_path(path)))


def inspect(directory, read_workspace):
    try:
        record = json.loads((directory / "session.json").read_text(encoding="utf-8"))
        port, token = record["port"], record["token"]
        if type(port) is not int or not 0 < port < 65536 or not re.fullmatch(r"[0-9a-f]{64}", token):
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    session = f"{port}:{token}"
    if not send_payload({"op": "probe"}, timeout=1, session=session)["ok"]:
        return None
    workspace = send_payload({"op": "workspace"}, session=session) if read_workspace else {}
    return directory.name, session, workspace


def discover(root):
    if not root.exists():
        return []
    entries = sorted(path for path in root.iterdir() if re.fullmatch(r"[0-9a-f]{8}", path.name))
    with ThreadPoolExecutor(max_workers=8) as pool:
        return [item for item in pool.map(lambda path: inspect(path, True), entries) if item]


def select(session_id):
    root = registry()
    if session_id:
        selected = inspect(root / session_id, False)
        if selected:
            return selected
    sessions = discover(root)
    if not session_id:
        cwd = directory_key(os.getcwd())
        matches = [item for item in sessions if item[2].get("cwd")
                   and directory_key(item[2]["cwd"]) == cwd]
        if len(matches) == 1 and all(item[2].get("cwd") for item in sessions):
            return matches[0]
    print("Specify a live Vim session with -s <id>.", file=sys.stderr)
    if not sessions:
        print("No live Vimbiosis sessions. Run :VbioAttach in Vim.", file=sys.stderr)
    for identifier, _, workspace in sessions:
        cwd = workspace.get("cwd", "(unavailable)")
        current = workspace.get("active", {}).get("path", "—" if workspace.get("ok") else "(unavailable)")
        print(f"{identifier}\t{cwd}\t{current}", file=sys.stderr)
    return None


def launch(command, session):
    executable = native_path(command[0])
    agent = os.path.basename(executable).lower()
    if agent.endswith(".exe"):
        agent = agent[:-4]
    port, token = session.split(":")
    url = f"http://127.0.0.1:{port}/mcp"
    if agent == "codex":
        options = [] if "--no-daemon" in command[1:] else ["--no-daemon"]
        options += ["-c", "mcp_servers.vimbiosis.url=" + json.dumps(url),
                    "-c", 'mcp_servers.vimbiosis.bearer_token_env_var="VIMBIOSIS_MCP_BEARER"']
    elif agent == "claude":
        options = ["--mcp-config", json.dumps({"mcpServers": {"vimbiosis": {
            "type": "http", "url": url, "alwaysLoad": True,
            "headers": {"Authorization": "Bearer ${VIMBIOSIS_MCP_BEARER}"},
        }}})]
    else:
        raise ValueError("agent must be codex or claude")
    env = dict(os.environ, VIMBIOSIS_SESSION=session, VIMBIOSIS_MCP_BEARER=token)
    if os.name == "nt":
        if not executable.lower().endswith(".exe"):
            executable += ".exe"
        executable = shutil.which(executable)
        if not executable:
            raise ValueError(f"{agent}.exe is required on Windows; pass its full path if needed")
        return subprocess.call([executable, *options, *command[1:]], env=env)
    os.execvpe(executable, [executable, *options, *command[1:]], env)


def main():
    parser = argparse.ArgumentParser(prog="vimbiosis", description=__doc__)
    parser.add_argument("-s", "--session")
    parser.add_argument("command", nargs=argparse.REMAINDER, metavar="agent [args ...]")
    args = parser.parse_args()
    if not args.command:
        parser.error("an agent command is required")
    if args.session is not None and not re.fullmatch(r"[0-9a-f]{8}", args.session):
        parser.error("session ID must be eight lowercase hexadecimal digits")
    try:
        selected = select(args.session)
        return launch(args.command, selected[1]) if selected else 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"vimbiosis: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
