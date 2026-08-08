#!/usr/bin/env python3
"""Write the RAPID program to file — one layer or all of them.

Offline transfer: the .mod files go on a USB stick and from there into the
IRC5. Every layer becomes its own module, named after the layer, so a student
loads exactly the program for the cardboard in front of them.

    gh_export_rapid.py                  # the layer currently selected
    gh_export_rapid.py --all            # every layer, one file each
    gh_export_rapid.py --all --folder=/Volumes/USB/rapid

**Refuses to write an unsafe program.** The canvas already knows whether the
robot collides, leaves the fence or cannot reach — writing a file that must not
be run would be the one place where being helpful is harmful. Override with
--force if you know what you are doing.
"""
import json
import re
import socket
import sys
import time
from pathlib import Path

HOST, PORT = "localhost", 8080

SAFE_FLAG = "safe overall"        # nickname of the overall safety gate
FIT_FLAG = "all inside"          # nickname prefix of the sheet-fit gate
LAYER_SLIDER = "Layer no."
SOLVE_PAUSE = 1.4                # seconds to let Grasshopper finish a solution


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


def flag(name, default=None):
    for arg in sys.argv:
        if arg.startswith(f"--{name}="):
            return arg.split("=", 1)[1]
    return default


def find(objects, *, type_contains=None, nickname_startswith=None):
    for obj in objects:
        if type_contains and type_contains in obj["type"]:
            return obj["id"]
        if nickname_startswith and (obj["nickname"] or "").lower().startswith(
                nickname_startswith.lower()):
            return obj["id"]
    return None


def first(component_id):
    items = send("get_component_output", {"id": component_id, "limit": 5})["outputs"][0]["items"]
    return items[0] if items else None


def module_text(rapid_id, layer):
    """Read the module and give it a name of its own — MainModule everywhere
    would collide the moment two programs are loaded together."""
    lines = send("get_component_output", {"id": rapid_id, "limit": 200000})["outputs"][0]["items"]
    text = "\n".join(lines)
    return re.sub(r"MODULE\s+\w+", f"MODULE Layer{layer:02d}", text, count=1)


def main():
    objects = send("get_layout")["objects"]
    rapid = find(objects, type_contains="RAPIDGeneratorComponent")
    if rapid is None:
        raise SystemExit("Kein RAPID Generator auf der Leinwand.")
    slider = find(objects, nickname_startswith=LAYER_SLIDER)
    safe = find(objects, nickname_startswith=SAFE_FLAG)
    fits = find(objects, nickname_startswith=FIT_FLAG)

    folder = flag("folder")
    if folder is None:
        document = send("get_document_info").get("path")
        if not document:
            raise SystemExit("Dokument ungespeichert — bitte --folder= angeben.")
        folder = Path(document).parent / "RAPID"
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    if "--all" in sys.argv:
        stats = find(objects, type_contains="Component_TreeStatistics")
        count = int(send("get_component_output", {"id": stats, "limit": 5})["outputs"][2]["items"][0])
        layers = range(count)
    else:
        layers = [int(float(first(slider)))]

    print(f"Ziel: {folder}")
    written, skipped = [], []
    for layer in layers:
        send("set_component_value", {"id": slider, "value": str(layer)})
        time.sleep(SOLVE_PAUSE)

        verdict = first(safe) if safe else "True"
        on_sheet = first(fits) if fits else "True"
        if (verdict != "True" or on_sheet != "True") and "--force" not in sys.argv:
            skipped.append((layer, verdict, on_sheet))
            print(f"  Layer {layer:3}: ÜBERSPRUNGEN "
                  f"(sicher={verdict}, passt aufs Blatt={on_sheet})")
            continue

        target = folder / f"layer_{layer:02d}.mod"
        target.write_text(module_text(rapid, layer), encoding="utf-8")
        moves = sum(1 for line in target.read_text(encoding="utf-8").splitlines()
                    if "Move" in line)
        written.append(target)
        print(f"  Layer {layer:3}: {target.name}  ({moves} Bewegungen)")

    print(f"\n{len(written)} Datei(en) geschrieben.")
    if skipped:
        print(f"{len(skipped)} Layer übersprungen — erst Zelle oder Blattformat korrigieren, "
              f"oder bewusst mit --force erzwingen.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
