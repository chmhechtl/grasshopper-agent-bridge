#!/usr/bin/env python3
"""Lay the canvas out as group blocks: each group is one rectangle, blocks placed
by data-flow stage. gh_layout.py optimises per component and lets group rectangles
collide; this keeps a group's members together and the groups apart."""
import json
from gh import send

GAP_X, GAP_Y, GUTTER, PAD = 40.0, 18.0, 90.0, 12.0

lay = send("get_layout")["data"]
objs = {o["id"]: o for o in lay["objects"]}
groups = {g["name"]: [m for m in g["members"] if m in objs] for g in lay["groups"]}
cons = send("get_connections")["data"]["connections"]

# longest-path depth over the component graph -> wires run left to right
parents = {}
for c in cons:
    parents.setdefault(c["targetId"], set()).add(c["sourceId"])
depth_cache = {}
def depth(n, seen=()):
    if n in depth_cache: return depth_cache[n]
    if n in seen: return 0
    d = max((depth(p, seen + (n,)) + 1 for p in parents.get(n, ())), default=0)
    depth_cache[n] = d
    return d

def block(members, note):
    """-> {id: (dx, dy)} relative to block origin, plus block width/height."""
    body = [m for m in members if m != note]
    cols = {}
    for m in body:
        cols.setdefault(depth(m), []).append(m)
    head_h = objs[note]["height"] + GAP_Y if note else 0.0
    head_w = objs[note]["width"] if note else 0.0
    pos, x = {}, 0.0
    if note: pos[note] = (0.0, 0.0)
    for d in sorted(cols):
        col = sorted(cols[d], key=lambda m: objs[m]["top"])
        w = max(objs[m]["width"] for m in col)
        y = head_h
        for m in col:
            pos[m] = (x, y)
            y += objs[m]["height"] + GAP_Y
        x += w + GAP_X
    bw = max(head_w, x - GAP_X if cols else 0.0)
    bh = max((pos[m][1] + objs[m]["height"] for m in pos), default=0.0)
    return pos, bw, bh

ORDER = sorted(groups)                      # 01..05
blocks = {n: block(groups[n], next((m for m in groups[n]
                                    if objs[m]["type"] == "GH_Panel"), None)) for n in ORDER}

# 01/02/03 stack in the input band, 04 and 05 follow as their own columns
STACK, CHAIN = ORDER[:3], ORDER[3:]
place, x0, y0 = {}, 60.0, 60.0
y = y0
for n in STACK:
    place[n] = (x0, y)
    y += blocks[n][2] + GUTTER + 2 * PAD
x = x0 + max(blocks[n][1] for n in STACK) + GUTTER + 2 * PAD
for n in CHAIN:
    place[n] = (x, y0)
    x += blocks[n][1] + GUTTER + 2 * PAD

items, bottom = [], y
for n in ORDER:
    pos, _, _ = blocks[n]
    bx, by = place[n]
    for m, (dx, dy) in pos.items():
        o = objs[m]
        items.append({"id": m,
                      "x": bx + dx + (o["x"] - o["left"]),
                      "y": by + dy + (o["y"] - o["top"])})

# ungrouped strays (bridge component, toggle, status panel) parked well clear
loose = [i for i in objs if not any(i in ms for ms in groups.values())]
ly = bottom + GUTTER
for m in sorted(loose, key=lambda m: objs[m]["top"]):
    o = objs[m]
    items.append({"id": m, "x": x0 + (o["x"] - o["left"]), "y": ly + (o["y"] - o["top"])})
    ly += o["height"] + GAP_Y

r = send("set_component_position", {"items": items})
print("moved %d objects, success=%s" % (len(items), r["success"]))
