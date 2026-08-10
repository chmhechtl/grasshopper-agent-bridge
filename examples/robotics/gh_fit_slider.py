#!/usr/bin/env python3
"""Set the layer slider's range to the layers this model actually has.

A Grasshopper slider's range is a UI setting, not an input — no wire can drive
it. So after loading a new model the slider still scrolls to whatever maximum it
had before, and hunting for layer 12 among 500 steps is miserable.

    gh_fit_slider.py        # fit the range to the current model

Run it whenever the model changes. The layer count comes from the same Tree
Statistics component the canvas already uses.
"""
import json
import socket
import sys

HOST, PORT = "localhost", 8080
SLIDER = "Layer no."


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


def main():
    objects = send("get_layout")["objects"]

    stats = next((o for o in objects if "TreeStatistics" in o["type"]), None)
    if stats is None:
        raise SystemExit("No Tree Statistics component found — layer count unknown.")
    count = int(send("get_component_output", {"id": stats["id"], "limit": 5})["outputs"][2]["items"][0])

    slider = next((o for o in objects
                   if o["type"] == "GH_NumberSlider"
                   and (o["nickname"] or "").lower().startswith(SLIDER.lower())), None)
    if slider is None:
        raise SystemExit(f"No slider '{SLIDER}' found.")

    current = send("get_component_info", {"id": slider["id"]}).get("value")
    try:
        value = min(float(current), count - 1)
    except (TypeError, ValueError):
        value = 0

    send("set_slider", {"id": slider["id"], "min": 0, "max": max(1, count - 1),
                        "value": value, "digits": 0, "name": slider["nickname"]})
    print(f"{count} layers — slider '{slider['nickname']}' now runs 0 to {count - 1}"
          f" (set to {value:.0f}).")


if __name__ == "__main__":
    main()
