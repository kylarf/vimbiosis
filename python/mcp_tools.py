"""The Vimbiosis MCP tool schemas and JSON-RPC dispatch."""
import json

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")


def tool(name, description, properties=None, required=(), read_only=False):
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties or {},
                        "required": list(required), "additionalProperties": False},
        "annotations": {"readOnlyHint": read_only,
                        "destructiveHint": name in ("execute_ex", "send_keys"),
                        "openWorldHint": not read_only},
        "_meta": {"anthropic/alwaysLoad": True},
    }


PATH = {"type": "string", "minLength": 1, "maxLength": 4096}
POSITION = {"type": "integer", "minimum": 1, "maximum": 2147483647}
ACTION = {"type": "string", "minLength": 1, "maxLength": 4096}
TOOLS = {item["name"]: item for item in (
    tool("workspace", "Inspect Vim's current editable file buffers and window IDs.",
         read_only=True),
    tool("read_buffer", "Read live Vim lines, including unsaved changes. Start and end "
         "are one-based and inclusive. Use this when the live buffer matters.",
         {"path": PATH, "start": POSITION, "end": POSITION}, ("path",), read_only=True),
    tool("open_file", "Open and focus a file in Vim. Use this when asked to show code "
         "or open a location. Line and byte column are one-based.",
         {"path": PATH, "line": POSITION, "column": POSITION,
          "vertical": {"type": "boolean"}}, ("path",)),
    tool("focus_window", "Focus an existing file window using an ID from workspace.",
         {"winid": POSITION}, ("winid",)),
    tool("execute_ex", "Run an Ex command in Vim only when explicitly requested. "
         "Requires g:vimbiosis_allow_arbitrary_actions.",
         {"command": ACTION, "winid": POSITION}, ("command",)),
    tool("send_keys", "Run mapped Normal-mode keys using Vim key notation only when "
         "explicitly requested. Requires g:vimbiosis_allow_arbitrary_actions.",
         {"keys": ACTION, "winid": POSITION}, ("keys",)),
)}

HOOK_TOOLS = {name: {
    "name": name,
    "description": description,
    "inputSchema": {"type": "object", "required": ["files"], "additionalProperties": False,
                    "properties": {"files": {"type": "array", "items": {"type": "string"}},
                                   "targets": {"type": "array", "items": {"type": "object"}},
                                   "session": {"type": "string"},
                                   "hook_id": {"type": "string"}}},
} for name, description in (
    ("before", "Check affected Vim buffers and capture a pre-edit snapshot."),
    ("notify", "Refresh affected Vim buffers and record a completed edit."),
)}
HOOK_TOOLS["prompt"] = tool("prompt", "Reset the prompt baseline and inspect Vim.",
                            {"session": PATH}, ("session",))


def valid_arguments(schema, arguments):
    if not isinstance(arguments, dict) or not set(schema["required"]) <= arguments.keys():
        return False
    types = {"boolean": bool, "integer": int, "string": str}
    for key, value in arguments.items():
        definition = schema["properties"].get(key)
        if definition is None or type(value) is not types[definition["type"]]:
            return False
        if isinstance(value, str) and (not 0 < len(value) <= definition["maxLength"]
                                       or any(char in value for char in "\x00\r\n")):
            return False
        if type(value) is int and not definition["minimum"] <= value <= definition["maximum"]:
            return False
    return True


def valid_hook_arguments(arguments):
    return (isinstance(arguments, dict) and arguments.keys() <= {"files", "targets", "hook_id", "session"}
            and isinstance(arguments.get("files"), list)
            and all(isinstance(path, str) for path in arguments["files"])
            and isinstance(arguments.get("hook_id", ""), str)
            and isinstance(arguments.get("session", ""), str)
            and isinstance(arguments.get("targets", []), list)
            and all(isinstance(target, dict) and isinstance(target.get("path"), str)
                    and isinstance(target.get("source", ""), str)
                    for target in arguments.get("targets", [])))


def rpc(message, dispatch, hooks=False):
    request_id = message.get("id") if isinstance(message, dict) else None
    response = {"jsonrpc": "2.0", "id": request_id}

    def error(code, description):
        return {**response, "error": {"code": code, "message": description}}

    if (not isinstance(message, dict) or message.get("jsonrpc") != "2.0"
            or not isinstance(message.get("method"), str)
            or type(request_id) not in (str, int, type(None))):
        response["id"] = None
        return error(-32600, "Invalid request")
    if "id" not in message:
        return None
    method = message["method"]
    tools = HOOK_TOOLS if hooks else TOOLS
    params = message.get("params", {})
    if not isinstance(params, dict):
        return error(-32602, "Invalid parameters")
    if method == "initialize":
        version = params.get("protocolVersion")
        if version not in PROTOCOL_VERSIONS:
            version = PROTOCOL_VERSIONS[0]
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "Vimbiosis", "version": "1.0.0"}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": list(tools.values())}
    elif method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(name, str) or name not in tools:
            return error(-32602, "Unknown Vim tool")
        valid = valid_hook_arguments(arguments) if hooks and name != "prompt" else valid_arguments(
            tools[name]["inputSchema"], arguments)
        if not valid:
            return error(-32602, "Invalid tool arguments")
        if name == "read_buffer" and arguments.get("end", POSITION["maximum"]) < arguments.get("start", 1):
            return error(-32602, "End line precedes start line")
        reply = dispatch({"op": name, **arguments})
        result = {"content": [{"type": "text", "text": json.dumps(reply)}],
                  "isError": not reply.get("ok", False)}
    else:
        return error(-32601, "Method not found")
    return {**response, "result": result}
