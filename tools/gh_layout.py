#!/usr/bin/env python3
"""Auto-layout for a Grasshopper canvas, driven through the GH_MCP bridge.

Sorts components into columns by data flow (longest-path layering), orders each
column by the average row of its inputs to keep wires short, then writes all
positions back in one batch. Groups stay intact because their membership is by
id, not by position.

Usage:
    python3 gh_layout.py            # lay out the whole canvas
    python3 gh_layout.py --dry-run  # print the plan only
    python3 gh_layout.py --panels   # only resize panels, no repositioning
"""
import json
import socket
import sys

HOST, PORT = "localhost", 8080

# Spacing in Grasshopper units. These are gaps between component edges, not a
# fixed grid pitch: every column is only as wide as its widest member, so a
# column of sliders no longer reserves the width of an RC component.
PAD = 6         # collision padding for the surgical alignment pass
GUTTER_X = 70   # horizontal air between two columns (room for the wires)
GUTTER_Y = 14   # vertical air between two components in the same column
BAND_GAP = 70   # air between two group bands — must clear the group box frame plus its name tab
MARGIN_X, MARGIN_Y = 60, 60

# ponytail: panels default to 120x60, too small for RAPID output. Widen the ones
# that carry code, keep value panels compact.
PANEL_SMALL = (110, 26)
PANEL_LARGE = (420, 340)
LARGE_PANEL_MIN_CHARS = 200


def send(command_type, params=None, timeout=120):
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


def build_graph(layout, connections):
    ids = {o["id"] for o in layout["objects"]}
    incoming = {i: [] for i in ids}
    outgoing = {i: [] for i in ids}
    for conn in connections["connections"]:
        src, dst = conn["sourceId"], conn["targetId"]
        if src in ids and dst in ids and src != dst:
            incoming[dst].append(src)
            outgoing[src].append(dst)
    return incoming, outgoing


def assign_columns(ids, incoming, outgoing):
    """Longest path from any source, then pull input-only nodes to the right.

    Without the second pass every panel and slider piles up in column 0, which
    makes that column several thousand units tall while the rest of the canvas
    is empty. Sliders belong next to what they drive.
    """
    column = {i: 0 for i in ids}
    for _ in range(len(ids) + 1):
        changed = False
        for node in ids:
            for parent in incoming[node]:
                if column[parent] + 1 > column[node]:
                    column[node] = column[parent] + 1
                    changed = True
        if not changed:
            break

    for node in ids:
        if incoming[node] or not outgoing[node]:
            continue
        column[node] = min(column[c] for c in outgoing[node]) - 1

    shift = -min(column.values())
    return {node: col + shift for node, col in column.items()}


def order_rows(columns, incoming, row_of):
    """Barycenter ordering: a node sits at the average row of its inputs."""
    for _ in range(4):
        for col in sorted(columns):
            nodes = columns[col]
            keyed = []
            for node in nodes:
                parents = [row_of[p] for p in incoming[node] if p in row_of]
                keyed.append((sum(parents) / len(parents) if parents else row_of[node], node))
            keyed.sort()
            for rank, (_, node) in enumerate(keyed):
                row_of[node] = rank
            columns[col] = [node for _, node in keyed]
    return columns


def resolve_overlaps(placed, objects, pad):
    """Push apart only the boxes that actually collide, leaving the rest alone.

    The band layout works from nominal sizes, but a component's real box can be
    taller than expected (variable inputs, long nicknames). Rather than adding
    global air for the worst case, find genuine collisions and shift just the
    lower box down, cascading within its own column.

    placed: {id: [left, top]} — real box corners, not pivots.
    Returns the number of collisions resolved.
    """
    def box(node):
        left, top = placed[node]
        return left, top, left + objects[node]["width"], top + objects[node]["height"]

    columns = {}
    for node, (left, _) in placed.items():
        columns.setdefault(round(left), []).append(node)

    fixed = 0
    for _ in range(50):
        collisions = 0
        for nodes in columns.values():
            nodes.sort(key=lambda n: placed[n][1])
            for upper, lower in zip(nodes, nodes[1:]):
                _, _, _, upper_bottom = box(upper)
                lower_left, lower_top, _, _ = box(lower)
                if lower_top < upper_bottom + pad:
                    placed[lower] = [lower_left, upper_bottom + pad]
                    collisions += 1
        # Different columns can still clash when a wide panel bleeds sideways.
        items = sorted(placed, key=lambda n: (placed[n][0], placed[n][1]))
        for i, first in enumerate(items):
            f_left, f_top, f_right, f_bottom = box(first)
            for second in items[i + 1:]:
                s_left, s_top, s_right, s_bottom = box(second)
                if s_left >= f_right + pad:
                    break
                if s_left < f_right + pad and s_right + pad > f_left \
                        and s_top < f_bottom + pad and s_bottom + pad > f_top:
                    placed[second] = [s_left, f_bottom + pad]
                    collisions += 1
        fixed += collisions
        if not collisions:
            break
    return fixed


def grip_offsets(objects):
    """Wire attachment points as offsets from a box's top edge.

    Grips come back in canvas coordinates; as offsets they stay valid no matter
    where the layout later puts the box.
    """
    offsets = {}
    for node, obj in objects.items():
        for side in ("inputs", "outputs"):
            for grip in obj.get(side, []):
                offsets[(node, side, grip["name"])] = grip["y"] - obj["top"]
    return offsets


def count_horizontal(placed, objects, wires, offsets, tolerance=1.0):
    """How many wires actually end up dead horizontal — the metric that matters."""
    horizontal = 0
    for wire in wires:
        source_offset = offsets.get((wire["sourceId"], "outputs", wire["sourceParam"]))
        target_offset = offsets.get((wire["targetId"], "inputs", wire["targetParam"]))
        if source_offset is None or target_offset is None:
            continue
        if wire["sourceId"] not in placed or wire["targetId"] not in placed:
            continue
        source_y = placed[wire["sourceId"]][1] + source_offset
        target_y = placed[wire["targetId"]][1] + target_offset
        if abs(source_y - target_y) <= tolerance:
            horizontal += 1
    return horizontal


def count_overlaps(placed, objects, pad=0.0):
    """Independent check — used to prove the canvas is clean afterwards."""
    hits = []
    items = list(placed)
    for i, first in enumerate(items):
        f_left, f_top = placed[first]
        f_right, f_bottom = f_left + objects[first]["width"], f_top + objects[first]["height"]
        for second in items[i + 1:]:
            s_left, s_top = placed[second]
            s_right, s_bottom = s_left + objects[second]["width"], s_top + objects[second]["height"]
            if s_left < f_right + pad and s_right + pad > f_left \
                    and s_top < f_bottom + pad and s_bottom + pad > f_top:
                hits.append((first, second))
    return hits


def read_flag(name, default):
    """--gutter-x=40 style overrides, so spacing is tunable without editing code."""
    for arg in sys.argv:
        if arg.startswith(f"--{name}="):
            return float(arg.split("=", 1)[1])
    return default


def check_or_fix(dry_run, repair):
    """Look at the canvas as it is: report real collisions, optionally nudge only those.

    No re-layout, no reordering — everything that does not collide stays exactly
    where the user put it.
    """
    layout = send("get_layout")
    objects = {o["id"]: o for o in layout["objects"]}
    if not any("left" in o for o in layout["objects"]):
        raise SystemExit("Die .gha liefert noch keine Rahmenmaße — Rhino einmal neu starten.")

    placed = {o["id"]: [o["left"], o["top"]] for o in layout["objects"]}
    hits = count_overlaps(placed, objects)
    print(f"{len(objects)} Bausteine geprüft, {len(hits)} echte Überlappungen")
    for first, second in hits[:12]:
        print(f"  {objects[first]['type'][:28]:28} überlagert {objects[second]['type'][:28]}")
    if not hits or not repair:
        return

    original = {node: list(pos) for node, pos in placed.items()}
    repaired = resolve_overlaps(placed, objects, pad=min(GUTTER_Y, 10))
    moved = [n for n in placed if placed[n] != original[n]]
    print(f"{repaired} Verschiebungen, {len(moved)} Bausteine betroffen, "
          f"{len(count_overlaps(placed, objects))} Überlappungen übrig")
    if dry_run:
        return

    items = [{"id": n,
              "x": placed[n][0] + (objects[n]["x"] - objects[n]["left"]),
              "y": placed[n][1] + (objects[n]["y"] - objects[n]["top"])}
             for n in moved]
    result = send("set_component_position", {"items": items})
    print(f"verschoben: {result['moved']}")


def align_only(dry_run):
    """Straighten single-consumer wires on the canvas as it is — nothing else moves."""
    layout = send("get_layout")
    objects = {o["id"]: o for o in layout["objects"]}
    if not any(o.get("outputs") for o in layout["objects"]):
        raise SystemExit("Die .gha liefert noch keine Anschlusspunkte — Rhino einmal neu starten.")

    wires = send("get_connections")["connections"]
    offsets = grip_offsets(objects)
    placed = {o["id"]: [o["left"], o["top"]] for o in layout["objects"]}
    original = {node: list(pos) for node, pos in placed.items()}
    group_of = {m: g["name"] for g in layout["groups"] for m in g["members"]}

    # Strictly surgical: only leaf inputs move, and only when the new spot is
    # genuinely free. A cascade of shoves would be a re-layout in disguise, which
    # is exactly what this mode exists to avoid.
    incoming = {node: 0 for node in placed}
    outgoing = {}
    for wire in wires:
        if wire["targetId"] in incoming:
            incoming[wire["targetId"]] += 1
        outgoing.setdefault(wire["sourceId"], []).append(wire)

    def collides(node, top):
        left = placed[node][0]
        right, bottom = left + objects[node]["width"], top + objects[node]["height"]
        for other in placed:
            if other == node:
                continue
            o_left, o_top = placed[other]
            o_right = o_left + objects[other]["width"]
            o_bottom = o_top + objects[other]["height"]
            if o_left < right + PAD and o_right + PAD > left \
                    and o_top < bottom + PAD and o_bottom + PAD > top:
                return True
        return False

    before = count_horizontal(placed, objects, wires, offsets)
    blocked = 0
    moved_labels, blocked_labels = [], []
    for node, wires_out in outgoing.items():
        if node not in placed or incoming.get(node) or len(wires_out) != 1:
            continue
        wire = wires_out[0]
        source_offset = offsets.get((node, "outputs", wire["sourceParam"]))
        target_offset = offsets.get((wire["targetId"], "inputs", wire["targetParam"]))
        if source_offset is None or target_offset is None or wire["targetId"] not in placed:
            continue
        if group_of.get(node) != group_of.get(wire["targetId"]):
            continue  # Ausrichtung endet an der Gruppengrenze — Bänder bleiben heil
        wanted = placed[wire["targetId"]][1] + target_offset - source_offset
        if abs(wanted - placed[node][1]) <= 0.5:
            continue
        label = f"{objects[node]['nickname'] or objects[node]['name']} -> {wire['targetName']}.{wire['targetParam']}"
        if collides(node, wanted):
            blocked += 1
            blocked_labels.append(label)
            continue
        placed[node][1] = wanted
        moved_labels.append(label)
    after = count_horizontal(placed, objects, wires, offsets)

    moved = [n for n in placed if placed[n] != original[n]]
    for label in moved_labels:
        print(f"  ausgerichtet: {label}")
    for label in blocked_labels:
        print(f"  blockiert:    {label}")
    print(f"Waagerechte Drähte: {before} -> {after} von {len(wires)}")
    print(f"{len(moved)} Bausteine verschoben, "
          f"{len(count_overlaps(placed, objects))} Überlappungen")
    if dry_run or not moved:
        return

    items = [{"id": n,
              "x": placed[n][0] + (objects[n]["x"] - objects[n]["left"]),
              "y": placed[n][1] + (objects[n]["y"] - objects[n]["top"])}
             for n in moved]
    print(f"verschoben: {send('set_component_position', {'items': items})['moved']}")


def main():
    global GUTTER_X, GUTTER_Y, BAND_GAP
    dry_run = "--dry-run" in sys.argv
    panels_only = "--panels" in sys.argv
    if "--compact" in sys.argv:
        GUTTER_X, GUTTER_Y, BAND_GAP = 45, 8, 55
    GUTTER_X = read_flag("gutter-x", GUTTER_X)
    GUTTER_Y = read_flag("gutter-y", GUTTER_Y)
    BAND_GAP = read_flag("band-gap", BAND_GAP)

    if "--check" in sys.argv or "--fix-overlaps" in sys.argv:
        check_or_fix(dry_run, repair="--fix-overlaps" in sys.argv)
        return

    if "--align-only" in sys.argv:
        align_only(dry_run)
        return

    layout = send("get_layout")
    objects = {o["id"]: o for o in layout["objects"]}

    # Panels first — sizing is independent of position.
    resized = 0
    for obj in layout["objects"]:
        if obj["type"] != "GH_Panel":
            continue
        info = send("get_component_info", {"id": obj["id"]})
        text = str(info.get("value") or "")
        width, height = PANEL_LARGE if len(text) > LARGE_PANEL_MIN_CHARS else PANEL_SMALL
        if not dry_run:
            send("set_component_size", {"id": obj["id"], "width": width, "height": height})
        resized += 1
    print(f"Panels {'geplant' if dry_run else 'angepasst'}: {resized}")
    if panels_only:
        return

    if not dry_run and resized:
        layout = send("get_layout")
        objects = {o["id"]: o for o in layout["objects"]}

    connections = send("get_connections")
    incoming, outgoing = build_graph(layout, connections)

    ids = list(objects)
    column_of = assign_columns(ids, incoming, outgoing)

    columns = {}
    for node in ids:
        columns.setdefault(column_of[node], []).append(node)

    row_of = {}
    for col in columns:
        for rank, node in enumerate(sorted(columns[col])):
            row_of[node] = rank
    columns = order_rows(columns, incoming, row_of)

    # Each group gets its own horizontal band, at the same height in every column,
    # so the didactic blocks read as clean stripes instead of ragged clusters.
    group_of = {}
    for group in layout["groups"]:
        for member in group["members"]:
            group_of[member] = group["name"]
    ungrouped = "Z · ohne Gruppe"

    cells = {}
    for col, nodes in columns.items():
        for node in nodes:
            cells.setdefault((group_of.get(node, ungrouped), col), []).append(node)
    for nodes in cells.values():
        nodes.sort(key=lambda n: row_of[n])

    # Column x from real widths — a column of sliders stays narrow.
    column_x, cursor_x = {}, MARGIN_X
    for col in sorted(columns):
        column_x[col] = cursor_x
        cursor_x += max(objects[n]["width"] for n in columns[col]) + GUTTER_X

    # Squeeze the empty columns out of each band. On the global grid a group with
    # members in column 0 and column 12 draws a nearly empty frame across half the
    # canvas; per band we only reserve the columns that group actually uses. The
    # band still starts at its true column, so the flow stays readable.
    band_x = {}
    compact_bands = "--no-band-compact" not in sys.argv
    for group in sorted({g for g, _ in cells}):
        used = sorted({c for g, c in cells if g == group})
        x = column_x[used[0]]
        for col in used:
            band_x[(group, col)] = x if compact_bands else column_x[col]
            x += max(objects[n]["width"] for n in cells[(group, col)]) + GUTTER_X

    offsets = grip_offsets(objects)
    wires = connections["connections"]
    wires_by_source = {}
    for wire in wires:
        wires_by_source.setdefault(wire["sourceId"], []).append(wire)

    do_align = "--no-align" not in sys.argv and bool(offsets)

    def wanted_y(node, group, placed):
        """Box top that makes this node's wire dead horizontal — or None.

        Only single-consumer nodes whose target sits in the SAME group and is
        already placed. Cross-group alignment was tried and smeared members into
        neighbouring group boxes; the bands must stay intact.
        """
        if not do_align:
            return None
        node_wires = wires_by_source.get(node, [])
        if len(node_wires) != 1:
            return None
        wire = node_wires[0]
        target = wire["targetId"]
        if target not in placed or group_of.get(target, ungrouped) != group:
            return None
        source_offset = offsets.get((node, "outputs", wire["sourceParam"]))
        target_offset = offsets.get((target, "inputs", wire["targetParam"]))
        if source_offset is None or target_offset is None:
            return None
        return placed[target][1] + target_offset - source_offset

    # Place band by band; inside a group right-to-left, so a source can align to
    # its already-placed target. Greedy stacking keeps the cell overlap-free: a
    # node lands on its wanted height when free, else right below its neighbour.
    # Band heights come from what was actually placed, not from an estimate.
    placed, band_y = {}, {}
    cursor_y = MARGIN_Y
    groups_in_order = sorted({g for g, _ in cells})
    for group in groups_in_order:
        band_y[group] = cursor_y
        band_bottom = cursor_y
        for col in sorted({c for g, c in cells if g == group}, reverse=True):
            nodes = cells[(group, col)]
            provisional = {}
            y = cursor_y
            for node in nodes:  # already in barycenter order
                provisional[node] = y
                y += objects[node]["height"] + GUTTER_Y
            entries = sorted(
                ((wanted_y(n, group, placed), provisional[n], n) for n in nodes),
                key=lambda e: e[1] if e[0] is None else e[0])
            floor = cursor_y
            for wanted, fallback, node in entries:
                top = max(wanted if wanted is not None else fallback, floor)
                placed[node] = [band_x[(group, col)], top]
                floor = top + objects[node]["height"] + GUTTER_Y
                band_bottom = max(band_bottom, floor)
        cursor_y = band_bottom + BAND_GAP

    straight_before = count_horizontal(
        {o["id"]: [o["left"], o["top"]] for o in layout["objects"] if o["id"] in placed},
        objects, wires, offsets)

    before = len(count_overlaps(placed, objects))
    repaired = resolve_overlaps(placed, objects, pad=min(GUTTER_Y, 10))
    remaining = count_overlaps(placed, objects)
    straight_after = count_horizontal(placed, objects, wires, offsets)

    items, plan = [], []
    for node, (left, top) in placed.items():
        obj = objects[node]
        # pivot offset inside the box, measured from the live canvas
        offset_x = obj["x"] - obj.get("left", obj["x"])
        offset_y = obj["y"] - obj.get("top", obj["y"])
        items.append({"id": node, "x": left + offset_x, "y": top + offset_y})
        plan.append(f"  ({left:5.0f},{top:6.0f})  {obj['type'][:30]:30} {group_of.get(node, '')[:28]}")

    width = max(placed[n][0] + objects[n]["width"] for n in placed)
    height = max(placed[n][1] + objects[n]["height"] for n in placed)
    print(f"{len(items)} Bausteine, {len(columns)} Spalten, {len(band_y)} Bänder — "
          f"Fläche {width:.0f} × {height:.0f}")
    print(f"Überlappungen: {before} gefunden, {repaired} Verschiebungen, {len(remaining)} übrig")
    print(f"Waagerechte Drähte: {straight_before} -> {straight_after} von {len(wires)}")
    for first, second in remaining[:5]:
        print(f"  ! {objects[first]['type']} / {objects[second]['type']}")
    if dry_run:
        print("\n".join(plan))
        return

    result = send("set_component_position", {"items": items})
    print(f"verschoben: {result['moved']}, nicht gefunden: {len(result['missing'])}")

    errors = send("get_errors")
    print(f"Meldungen nach dem Layout: {errors['count']}")


if __name__ == "__main__":
    main()
