#!/usr/bin/env python3
"""Export the robot's motion profile from the live Grasshopper document as CSV.

One row per path point: the six joint angles in degrees plus the TCP position in
world millimetres. Plotting happens outside — matplotlib, Excel, whatever; a
chart drawn into the Grasshopper canvas was unreadable and in the way.

    gh_export_profile.py                        # next to the .gh file
    gh_export_profile.py path/to/profile.csv    # explicit target

Finds its data by component nickname, so the canvas can be rearranged freely:
  "Deconstruct Robot Joint Position" (any nickname) -> joint angles
  the Deconstruct Point fed by the TCP pose        -> TCP x/y/z
"""
import csv
import json
import socket
import sys
from pathlib import Path

HOST, PORT = "localhost", 8080

JOINT_PREFIX = "Robot joint position"
TCP_COMPONENT = "Component_DeconstructPoint"
TCP_SOURCE = "Component_DeconstructPlane"


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


def numbers(items):
    """Grasshopper hands numbers back as strings; anything unparseable is a gap."""
    values = []
    for item in items:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            values.append(None)
    return values


def find_joint_component(objects):
    for obj in objects:
        if "DeconstructRobotJointPos" in obj["type"]:
            return obj["id"]
    raise SystemExit("No 'Deconstruct Robot Joint Position' on the canvas — "
                     "without it there is no axis data.")


def find_tcp_component(objects, connections):
    """The Deconstruct Point fed by a Deconstruct Plane is the TCP tap."""
    planes = {o["id"] for o in objects if o["type"] == TCP_SOURCE}
    for conn in connections:
        if conn["sourceId"] in planes:
            for obj in objects:
                if obj["id"] == conn["targetId"] and obj["type"] == TCP_COMPONENT:
                    return obj["id"]
    return None


def main():
    layout = send("get_layout")
    objects = layout["objects"]
    connections = send("get_connections")["connections"]

    joint_id = find_joint_component(objects)
    joint_out = send("get_component_output", {"id": joint_id, "limit": 100000})["outputs"]
    axes = [numbers(o["items"]) for o in joint_out if o["name"].startswith(JOINT_PREFIX)]
    if len(axes) != 6:
        raise SystemExit(f"Expected 6 axes, found {len(axes)}.")

    tcp_id = find_tcp_component(objects, connections)
    tcp = []
    if tcp_id:
        tcp_out = send("get_component_output", {"id": tcp_id, "limit": 100000})["outputs"]
        tcp = [numbers(o["items"]) for o in tcp_out[:3]]

    count = len(axes[0])
    if any(len(a) != count for a in axes):
        raise SystemExit("Axes have different lengths — check the chain.")

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if target is None:
        document = send("get_document_info").get("path")
        if not document:
            raise SystemExit("The document has not been saved yet — give a target path.")
        target = Path(document).with_suffix("").with_name(
            Path(document).stem + "_motion_profile.csv")

    header = ["point", "A1_deg", "A2_deg", "A3_deg", "A4_deg", "A5_deg", "A6_deg"]
    if tcp:
        header += ["TCP_x_mm", "TCP_y_mm", "TCP_z_mm"]

    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for i in range(count):
            row = [i] + [axes[a][i] for a in range(6)]
            if tcp:
                row += [series[i] if i < len(series) else None for series in tcp]
            writer.writerow(row)

    print(f"{count} Bahnpunkte -> {target}")
    for a in range(6):
        values = [v for v in axes[a] if v is not None]
        if values:
            print(f"  A{a + 1}: {min(values):8.2f} .. {max(values):8.2f} Grad")


if __name__ == "__main__":
    main()
