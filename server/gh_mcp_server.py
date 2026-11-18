#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=1.2,<2"]  # ponytail: written against the v1 low-level API; port when v1 is retired
# ///
"""MCP server for the Grasshopper Agent Bridge.

Exposes every bridge command as an MCP tool over stdio and forwards each call to the
.gha's socket (one JSON line per command, see docs/protocol.md). Tool names and
argument keys are the bridge's own, so docs/commands.md is the reference for both.

    uv run gh_mcp_server.py            # dependencies resolved from the header
    pip install 'mcp<2' && python3 gh_mcp_server.py

Host and port come from GH_BRIDGE_HOST / GH_BRIDGE_PORT (default 127.0.0.1:8080).
"""
import asyncio
import json
import os
import socket

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

HOST = os.environ.get("GH_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("GH_BRIDGE_PORT", "8080"))
TIMEOUT = float(os.environ.get("GH_BRIDGE_TIMEOUT", "120"))  # heavy documents solve slowly

S, N, I, B = {"type": "string"}, {"type": "number"}, {"type": "integer"}, {"type": "boolean"}
IDS = {"type": "array", "items": S}
VALUE = {"type": ["string", "number", "boolean"]}
ID = {"id": S}

# name: (description, properties, required)
TOOLS = {
    # --- reading
    "get_document_info": ("Name, path and all components (id, type, name) of the active document.", {}, []),
    "get_component_info": ("Inputs, outputs and current value of one object. Read the input list before wiring.", ID, ["id"]),
    "get_component_output": (
        "The data actually flowing out of an object, as strings, with branch paths and counts. "
        "The honest success check: a component can report success and emit nothing.",
        {**ID, "limit": I}, ["id"]),
    "get_connections": ("Wires as source/target pairs, sources resolved to the owning component. Pass 'id' for only\n"
                        "the wires into or out of one object — the whole document is large.", ID, []),
    "get_errors": ("Every object carrying a runtime error, warning or remark. Run after each build step.", {}, []),
    "get_layout": ("Real bounding boxes, pivots, wire grips and all groups with their members. Large: pass 'ids' for\n"
                   "specific objects and grips=false unless you need wire attachment points.",
                   {"ids": IDS, "grips": B}, []),
    "search_components": (
        "Search Grasshopper's component registry. Returns guid, name, category, obsolete. "
        "Always resolve the GUID here before add_component.", {"query": S}, ["query"]),
    "describe_document": (
        "Everything needed to understand or rebuild a definition: per object its componentGuid, value, "
        "and per parameter the mapping (flatten/graft), expression, internal values and sources. "
        "With clusterId, the inside of that cluster. Large — save it to a file rather than reading it whole.",
        {"clusterId": S}, []),
    "get_documents": ("All documents open in the Grasshopper editor, with index, name, path and which is active.", {}, []),
    # --- building
    "add_component": (
        "Place a component. Pass a GUID from search_components as 'type'; name lookup is fuzzy "
        "and can return an obsolete twin.", {"type": S, "x": N, "y": N}, ["type", "x", "y"]),
    "connect_components": (
        "Wire an output to an input. Prefer the index parameters. Replaces the wires already on that "
        "input unless append=true.",
        {"sourceId": S, "targetId": S, "sourceParam": S, "targetParam": S,
         "sourceParamIndex": I, "targetParamIndex": I, "append": B}, ["sourceId", "targetId"]),
    "disconnect_components": (
        "Remove the wires into one input (by name or index); with sourceId only that wire.",
        {"targetId": S, "targetParam": S, "targetParamIndex": I, "sourceId": S}, ["targetId"]),
    "delete_component": ("Delete an object or group. The bridge component itself is protected.", ID, ["id"]),
    "add_variable_parameter": (
        "Toggle a parameter that a plugin hides in its right-click menu.",
        {**ID, "index": I, "side": {"type": "string", "enum": ["input", "output"]}}, ["id", "index"]),
    # --- values and labels
    "set_component_value": (
        "Set a panel (text), slider (number or 'min < value < max') or boolean toggle (true/false).",
        {**ID, "value": VALUE}, ["id", "value"]),
    "set_param_value": (
        "Write a persistent value into an unwired integer, number, boolean or string input.",
        {**ID, "index": I, "value": VALUE}, ["id", "index", "value"]),
    "set_slider": ("Set a slider's range, value and decimal digits (0 = integer).",
                   {**ID, "min": N, "max": N, "value": N, "digits": I, "name": S}, ["id"]),
    "set_nickname": ("Rename a component or group.", {**ID, "name": S}, ["id", "name"]),
    "set_value_list": ("Select a value-list entry by name or index.", {**ID, "value": {"type": ["string", "integer"]}}, ["id", "value"]),
    "set_colour": ("Set a colour swatch, e.g. '#A0785A'.", {**ID, "colour": S}, ["id", "colour"]),
    "set_script": ("Replace the source of a GhPython script component.", {**ID, "code": S}, ["id", "code"]),
    # --- layout and display
    "set_component_position": (
        "Move one object (id, x, y) or a batch (items: [{id, x, y}]) in a single solution. No undo record.",
        {**ID, "x": N, "y": N, "items": {"type": "array", "items": {"type": "object"}}}, []),
    "set_component_size": ("Resize an object's box, mainly panels.", {**ID, "width": N, "height": N},
                           ["id", "width", "height"]),
    "create_group": ("Group objects under a name, optional colour.", {"name": S, "ids": IDS, "color": S},
                     ["name", "ids"]),
    "add_to_group": ("Add existing objects to an existing group.", {"groupId": S, "ids": IDS}, ["groupId", "ids"]),
    "remove_from_group": ("Take objects out of a group; they stay on the canvas.", {"groupId": S, "ids": IDS},
                          ["groupId", "ids"]),
    "set_wire_display": (
        "Draw the wires into a parameter as default, faint or hidden. Targets a standalone parameter, "
        "or with inputIndex one input of a component. 'ids' for a batch.",
        {**ID, "ids": IDS, "inputIndex": I, "mode": {"type": "string", "enum": ["default", "faint", "hidden"]}},
        ["mode"]),
    "set_preview": ("Show or hide an object's viewport preview.", {**ID, "hidden": B}, ["id", "hidden"]),
    "set_enabled": ("Enable or disable objects. A disabled component computes nothing.",
                    {**ID, "ids": IDS, "enabled": B}, ["enabled"]),
    # --- solution and Rhino
    "recompute": ("Force a recompute of the whole document, or of 'id'/'ids' and everything downstream. "
                  "Clears stale runtime messages.", {**ID, "ids": IDS}, []),
    "bake_component": ("Bake an object's geometry into the Rhino document, optionally onto a named layer.",
                       {**ID, "layer": S}, ["id"]),
    # --- document
    "new_document": ("Open an empty document next to the ones already open and make it active. Closes nothing.", {}, []),
    "activate_document": ("Switch the active document, by index from get_documents or by name.",
                          {"index": I, "name": S}, []),
    "save_document": ("Save the document; without a path, where it came from.", {"path": S}, []),
    "load_document": ("Open a .gh file and close the previous document.", {"path": S}, ["path"]),
    "clear_document": ("Remove everything except the bridge component, toggles and panels.", {}, []),
}


def send(command, params):
    """One command, one connection. Raises with the bridge's own error text."""
    try:
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
    except OSError as error:
        raise RuntimeError(
            f"Bridge not reachable on {HOST}:{PORT} ({error}). In Grasshopper, place the "
            "'Grasshopper MCP' component and set its toggle to True.") from error
    with sock:
        sock.sendall((json.dumps({"type": command, "parameters": params}) + "\n").encode())
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(8192)
            if not chunk:
                break
            data += chunk
    response = json.loads(data.decode("utf-8-sig").strip())
    if not response.get("success"):
        raise RuntimeError(response.get("error") or f"{command} failed")
    return response.get("data")


server = Server("grasshopper-agent-bridge")


@server.list_tools()
async def list_tools():
    return [types.Tool(name=name, description=description,
                       inputSchema={"type": "object", "properties": properties, "required": required})
            for name, (description, properties, required) in TOOLS.items()]


@server.call_tool()
async def call_tool(name, arguments):
    if name not in TOOLS:
        raise ValueError(f"Unknown tool {name}")
    data = await asyncio.to_thread(send, name, arguments or {})
    return [types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
