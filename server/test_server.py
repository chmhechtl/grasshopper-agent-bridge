#!/usr/bin/env python3
"""Self-check for gh_mcp_server.py — needs no Rhino.

1. The tool table matches the commands registered in the .gha source.
2. A call travels MCP → socket → fake bridge and back, and a bridge error surfaces.

    python3 test_server.py
"""
import asyncio
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from gh_mcp_server import TOOLS  # noqa: E402

# Compute-only leftovers from upstream that do not touch the document; deliberately not exposed.
NOT_EXPOSED = {"create_point", "create_curve", "create_circle", "create_pattern", "get_available_patterns"}


class FakeBridge(socketserver.StreamRequestHandler):
    def handle(self):
        command = json.loads(self.rfile.readline())
        if command["type"] == "delete_component":
            reply = {"success": False, "data": None, "error": "boom"}
        else:
            reply = {"success": True, "data": {"echo": command}, "error": None}
        self.wfile.write(("﻿" + json.dumps(reply) + "\n").encode())


async def round_trip(port):
    params = StdioServerParameters(command=sys.executable, args=[str(HERE / "gh_mcp_server.py")],
                                   env={"GH_BRIDGE_PORT": str(port)})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        listed = {tool.name for tool in (await session.list_tools()).tools}
        assert listed == set(TOOLS), listed ^ set(TOOLS)

        result = await session.call_tool("set_nickname", {"id": "abc", "name": "Radius"})
        echo = json.loads(result.content[0].text)["echo"]
        assert echo == {"type": "set_nickname", "parameters": {"id": "abc", "name": "Radius"}}, echo

        failed = await session.call_tool("delete_component", {"id": "abc"})
        assert failed.isError and "boom" in failed.content[0].text, failed

        invalid = await session.call_tool("set_nickname", {"id": "abc"})  # 'name' missing
        assert invalid.isError, invalid


def main():
    registry = (HERE.parent / "bridge/GH_MCP/Commands/GrasshopperCommandRegistry.cs").read_text()
    registered = set(re.findall(r'RegisterCommand\("(\w+)"', registry))
    assert registered - NOT_EXPOSED == set(TOOLS), (registered - NOT_EXPOSED) ^ set(TOOLS)

    with socketserver.TCPServer(("127.0.0.1", 0), FakeBridge) as bridge:
        threading.Thread(target=bridge.serve_forever, daemon=True).start()
        asyncio.run(round_trip(bridge.server_address[1]))
        bridge.shutdown()
    print(f"ok — {len(TOOLS)} tools match the registry, round trip and error path work")


if __name__ == "__main__":
    main()
