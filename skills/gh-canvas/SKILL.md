---
name: gh-canvas
description: Work on a live Grasshopper canvas through the GH_MCP bridge (TCP port 8080) — place and wire components, read runtime errors, inspect the data that actually flows, lay out the canvas, size panels, and save versioned checkpoints. Use whenever the task involves Grasshopper, Rhino or a parametric definition that is open in the editor — including "tidy the canvas", "why is that component red", "what does it output", "wire X to Y".
---

# Driving a Grasshopper canvas

The bridge is a socket server inside Grasshopper. It answers one line-delimited JSON command
per connection on `127.0.0.1:8080`. Full reference: `docs/commands.md`, protocol details in
`docs/protocol.md`, and **read `docs/pitfalls.md` before building anything non-trivial.**

## Connecting

Rhino must be running with the document open, the **Grasshopper MCP** component on the canvas
and its toggle set to `True`. Check with `nc -z 127.0.0.1 8080`.

```python
import json, socket
def send(command, params=None, timeout=120):
    s = socket.socket(); s.settimeout(timeout); s.connect(("localhost", 8080))
    s.sendall((json.dumps({"type": command, "parameters": params or {}}) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(8192)
        if not chunk: break
        data += chunk
    s.close()
    return json.loads(data.decode("utf-8-sig").strip())
```

`tools/gh.py` is the same thing with a command-line entry point.

## Commands

**Read** — `get_document_info`, `get_component_info` {id}, `get_component_output` {id, limit},
`get_connections`, `get_errors`, `get_layout`, `search_components` {query}

**Build** — `add_component` {type, x, y}, `connect_components` {sourceId, targetId,
sourceParam, targetParamIndex}, `disconnect_components` {targetId, targetParam},
`delete_component` {id}, `add_variable_parameter` {id, index, side}

**Values and labels** — `set_component_value`, `set_param_value` {id, index, value},
`set_slider` {id, min, max, value, digits, name}, `set_nickname`, `set_value_list`,
`set_colour`, `set_script`

**Layout** — `set_component_position` {items:[{id,x,y}]}, `set_component_size`,
`create_group` {name, ids, color}, `set_preview` {id, hidden}

**Document** — `save_document` {path?}, `load_document` {path}, `clear_document`

## The rules that matter

1. **Place by GUID, never by name.** Name lookup returns OBSOLETE twins and parameter
   containers with the same label — in vanilla Grasshopper too. Resolve with
   `search_components` (it reports an `obsolete` flag) and verify the type name in the reply.
2. **Wire targets by index, not by name.** Parameter names differ between plugin versions.
   Read the real names and positions with `get_component_info` first. Output names are often
   surprising (`Larger than`, not `Result`) — a wrong name connects nothing and still reports
   success.
3. **Judge success by the data.** `get_component_output` after every wiring step; an empty
   list means the wire does nothing. Then `get_errors`. Never trust the return message alone.
4. **A deleted component stays findable briefly.** Connecting to it succeeds and does nothing.
   When replacing a chain: place all new components, then rebuild all wiring, then verify.
5. **Wrong order means data trees.** Check branch structure with a `Tree Statistics` component
   before suspecting your logic. `Flatten Tree` and `Simplify Tree` are the usual fixes.
6. **Restart Rhino only after replacing the `.gha`.** Normal canvas work never needs one.
   Batch bridge changes into a single build and restart.
7. **Checkpoint before layout passes and chain replacements** — moving components creates no
   undo record.
8. **Not everything is a component.** `search_components` cannot see right-click menu items.
   When a capability seems missing, check the context menu before building a workaround.

## Tidying up

```bash
python3 tools/gh_layout.py --compact      # columns by data flow, groups as bands
python3 tools/gh_layout.py --align-only   # straighten single-consumer wires only
python3 tools/gh_layout.py --check        # report real overlaps, move nothing
python3 tools/gh_preview.py               # hide helper geometry in the viewport
```

Groups survive being moved — membership is by id, not position. There is no "add to group";
delete the group and recreate it with the full member list.

## Checkpoints

```bash
python3 tools/gh_checkpoint.py save "what changed"
python3 tools/gh_checkpoint.py list
python3 tools/gh_checkpoint.py restore <commit>
```

Saves the document, commits it, and records component count and open warnings in the message —
so the history shows when the definition was healthy. `restore` loads the file back into the
editor.

## Building well

- **Label every control** with `set_slider`/`set_nickname`. A panel reading `4` tells nobody
  what it means.
- **Group by data-flow stage**, numbered with two digits (`01`, `02`, … — `10` sorts before
  `2` otherwise).
- **Couple values that must agree** rather than exposing two inputs for one physical fact.
- **Add cheap parametric checks** (fit, reach, collision, overlap) and let downstream steps
  refuse to run when they fail.
