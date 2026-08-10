#!/usr/bin/env python3
"""Play a Grasshopper slider like an animation — for demonstrating the robot.

Grasshopper's own "Animate" renders frames to disk; that is a batch job, not a
live playback. This steps the slider through its range instead, so the viewport
moves while you talk.

    gh_play.py                          # simulation slider, one pass, 20 s
    gh_play.py --loop                   # until Ctrl+C
    gh_play.py --pingpong --seconds 30  # forth and back, slower
    gh_play.py --slider "Layer no."     # flip through the layers instead

Stop any time with Ctrl+C — the slider stays where it was.
"""
import json
import socket
import sys
import time

HOST, PORT = "localhost", 8080
DEFAULT_SLIDER = "Simulation time"


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


def flag(name, default):
    for arg in sys.argv:
        if arg.startswith(f"--{name}="):
            return arg.split("=", 1)[1]
    if f"--{name}" in sys.argv:
        index = sys.argv.index(f"--{name}")
        if index + 1 < len(sys.argv) and not sys.argv[index + 1].startswith("--"):
            return sys.argv[index + 1]
    return default


def find_slider(wanted):
    """Match on nickname, so renaming the label does not break playback."""
    sliders = [o for o in send("get_layout")["objects"] if o["type"] == "GH_NumberSlider"]
    hits = [s for s in sliders if wanted.lower() in (s["nickname"] or "").lower()]
    if not hits:
        names = ", ".join(sorted(s["nickname"] for s in sliders if s["nickname"]))
        raise SystemExit(f"No slider matches '{wanted}'.\nAvailable: {names}")
    return hits[0]


def read_range(slider_id):
    """The bridge reports the current value; the range comes from a probe."""
    info = send("get_component_info", {"id": slider_id})
    value = info.get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main():
    wanted = flag("slider", DEFAULT_SLIDER)
    seconds = float(flag("seconds", 20))
    steps = int(flag("steps", 60))
    low = float(flag("from", 0.0))
    high = float(flag("to", 1.0))
    loop = "--loop" in sys.argv
    pingpong = "--pingpong" in sys.argv

    slider = find_slider(wanted)
    print(f"Playing '{slider['nickname']}' from {low} to {high} "
          f"in {steps} steps over {seconds:.0f} s"
          + (" (looping)" if loop else "")
          + (" (there and back)" if pingpong else "")
          + "  —  Ctrl+C stops it")

    start_value = read_range(slider["id"])
    pause = seconds / max(1, steps)
    sequence = [low + (high - low) * i / steps for i in range(steps + 1)]
    if pingpong:
        sequence += list(reversed(sequence[:-1]))

    frames = 0
    began = time.time()
    try:
        while True:
            for value in sequence:
                tick = time.time()
                send("set_component_value", {"id": slider["id"], "value": f"{value:.4f}"})
                frames += 1
                # Each step forces a full re-solve; only wait for the rest of the slot.
                rest = pause - (time.time() - tick)
                if rest > 0:
                    time.sleep(rest)
            if not loop:
                break
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
    finally:
        elapsed = time.time() - began
        if frames:
            print(f"{frames} Bilder in {elapsed:.1f} s  ({frames / elapsed:.1f} Bilder/s)")
        print(f"Slider is at {read_range(slider['id'])} (started at {start_value})")


if __name__ == "__main__":
    main()
