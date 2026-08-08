#!/usr/bin/env python3
"""Direct TCP client for the GH_MCP component (port 8080).
Usage: gh.py <command_type> ['<json-params>']"""
import json
import socket
import sys

def send(command_type, params=None):
    cmd = {"type": command_type, "parameters": params or {}}
    s = socket.socket()
    s.settimeout(30)
    s.connect(("localhost", 8080))
    s.sendall((json.dumps(cmd) + "\n").encode())
    data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
        if data.endswith(b"\n"):
            break
    s.close()
    return json.loads(data.decode("utf-8-sig").strip())

if __name__ == "__main__":
    params = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(send(sys.argv[1], params), indent=2, ensure_ascii=False))
