#!/usr/bin/env python3
"""Tidy the Rhino viewport: hide the previews of helper components.

Robot Components draws an axis cross for every target — at a hundred targets the
model disappears behind red and green arrows. The size of those crosses is not
adjustable, so the answer is to hide them and keep only what tells a story:
the robot, the cell, the model, the slice indicator and the tool path.

    gh_preview.py            # tidy up
    gh_preview.py --list     # what is currently visible
    gh_preview.py --show-all # everything back on
"""
import json
import socket
import sys

HOST, PORT = "localhost", 8080

# Everything else gets hidden. Matched against the component type name.
KEEP_VISIBLE = (
    "GH_CustomPreviewComponent",   # cell, cardboard, slices, path — all coloured
    "PathGeneratorComponent",      # the robot itself and its tool path
    "Param_Brep",                  # the referenced model
)


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
            print(f"  {'sichtbar ' if keep else 'versteckt'} {obj['type'][:34]:34} "
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
        print(f"{changed} components checked — only the robot, path, cell, model "
              f"and the coloured previews stay visible.")


if __name__ == "__main__":
    main()
