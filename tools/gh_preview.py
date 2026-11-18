#!/usr/bin/env python3
"""Tidy the Rhino viewport: hide the previews of helper components.

A finished definition previews every intermediate step, and the result disappears behind
construction geometry. This hides everything except the component types you want to see.

    gh_preview.py                         # keep only Custom Preview components visible
    gh_preview.py --keep=Param_Brep,Loft  # ...plus these types (substring match)
    gh_preview.py --list                  # what would stay visible
    gh_preview.py --show-all              # everything back on
"""
import json
import socket
import sys

HOST, PORT = "localhost", 8080

# Everything else gets hidden. Matched as a substring of the component type name
# (the "type" column of --list).
KEEP_VISIBLE = ["GH_CustomPreviewComponent"]
for _arg in sys.argv[1:]:
    if _arg.startswith("--keep="):
        KEEP_VISIBLE += [k for k in _arg[len("--keep="):].split(",") if k]


def send(command_type, params=None, timeout=180):
    payload = json.dumps({"type": command_type, "parameters": params or {}})
    sock = socket.socket()
    sock.settimeout(timeout)
    sock.connect((HOST, PORT))
    sock.sendall((payload + "\n").encode())
    chunks = b""
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        chunks += chunk
        if chunks.endswith(b"\n"):
            break
    sock.close()
    response = json.loads(chunks.decode("utf-8-sig").strip())
    if not response.get("success"):
        raise RuntimeError(f"{command_type}: {response.get('error')}")
    return response["data"]


def set_preview(component_id, hidden):
    """Not every component has a preview; those simply refuse and are skipped."""
    try:
        send("set_preview", {"id": component_id, "hidden": hidden})
        return True
    except RuntimeError:
        return False


def main():
    objects = send("get_layout")["objects"]

    if "--list" in sys.argv:
        for obj in sorted(objects, key=lambda o: o["type"]):
            keep = any(k in obj["type"] for k in KEEP_VISIBLE)
            print(f"  {'visible' if keep else 'hidden '} {obj['type'][:34]:34} "
                  f"{obj['nickname'][:26]}")
        return

    show_all = "--show-all" in sys.argv
    changed = 0
    for obj in objects:
        keep = show_all or any(k in obj["type"] for k in KEEP_VISIBLE)
        if set_preview(obj["id"], hidden=not keep):
            changed += 1

    if show_all:
        print(f"Preview switched back on for {changed} components.")
    else:
        print(f"{changed} components checked — only {', '.join(KEEP_VISIBLE)} stay visible.")


if __name__ == "__main__":
    main()
