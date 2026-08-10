#!/usr/bin/env python3
"""Sweep the whole program and report every pose that is not safe.

The check on the canvas judges the pose the simulation slider currently shows.
That is right for scrubbing by hand, but a program is only safe if EVERY pose
is. This steps the slider through all path points and collects the verdicts.

    gh_check_collisions.py            # every path point
    gh_check_collisions.py --steps 40 # coarser, faster

Reports the offending path points and exits with status 1 if any pose fails, so
it can gate a release later on.
"""
import json
import socket
import sys

HOST, PORT = "localhost", 8080
SLIDER = "Simulation time"
VERDICT = "safe?"          # nickname of the And gate on the canvas
OBSTACLE = "no obstacle hit"
INSIDE = "all inside fence"


def send(command_type, params=None, timeout=300):
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


def by_nickname(objects, wanted):
    for obj in objects:
        if (obj["nickname"] or "").lower().startswith(wanted.lower()):
            return obj["id"]
    raise SystemExit(f"Component '{wanted}' not found — "
                     "is the collision check on the canvas?")


def first_value(component_id):
    items = send("get_component_output", {"id": component_id, "limit": 2})["outputs"][0]["items"]
    return items[0] if items else None


def main():
    steps = None
    for arg in sys.argv:
        if arg.startswith("--steps="):
            steps = int(arg.split("=", 1)[1])

    objects = send("get_layout")["objects"]
    slider = by_nickname(objects, SLIDER)
    verdict = by_nickname(objects, VERDICT)
    obstacle = by_nickname(objects, OBSTACLE)
    inside = by_nickname(objects, INSIDE)

    if steps is None:
        # One check per path point — the poses the robot actually passes through.
        joints = next(o for o in objects if "DeconstructRobotJointPos" in o["type"])
        counts = send("get_component_output", {"id": joints["id"], "limit": 100000})["outputs"]
        steps = max(1, len(counts[1]["items"]) - 1)

    print(f"Checking {steps + 1} poses …")
    bad = []
    for i in range(steps + 1):
        value = i / steps
        send("set_component_value", {"id": slider, "value": f"{value:.6f}"})
        if first_value(verdict) != "True":
            bad.append((i, first_value(obstacle), first_value(inside)))
            print(f"  Pose {i:4}: NICHT SICHER "
                  f"(clear of obstacle={bad[-1][1]}, inside fence={bad[-1][2]})")

    if bad:
        print(f"\n{len(bad)} of {steps + 1} poses unsafe — do not run this program.")
        raise SystemExit(1)
    print(f"\nAll {steps + 1} poses safe: no contact with table or pedestal, "
          "robot inside the fence throughout.")


if __name__ == "__main__":
    main()
