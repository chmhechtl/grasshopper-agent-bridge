---
name: gh-canvas
description: Work on a live Grasshopper canvas through the Grasshopper bridge (MCP tools of the `grasshopper` server, or its socket on port 8080) — place and wire components, read runtime errors, inspect the data that actually flows, lay out the canvas, size panels, and save versioned checkpoints. Use whenever the task involves Grasshopper, Rhino or a parametric definition that is open in the editor — including "tidy the canvas", "why is that component red", "what does it output", "wire X to Y".
---

# Driving a Grasshopper canvas

Every command below is an MCP tool of the same name on the `grasshopper` server — call it
directly. Full reference: `docs/commands.md`, and **read `docs/pitfalls.md` before building
anything non-trivial.**

## Connecting

Rhino must be running with the document open, the **Grasshopper MCP** component on the canvas
and its toggle set to `True`. Call `get_document_info`; if it answers, you are connected.

Without an MCP client the same commands go over a socket, one line-delimited JSON object per
connection on `127.0.0.1:8080` — `tools/gh.py` is a ready client, `docs/protocol.md` has the
details. The examples in these skills write calls as `command {arguments}`; that is the tool
call and the socket payload alike.

## Commands

**Read** — `get_document_info`, `get_component_info` {id}, `get_component_output` {id, limit},
`get_connections` {id?}, `get_errors`, `get_layout` {ids?, grips?}, `search_components` {query},
`describe_document` {clusterId?} — a whole definition in one call; large, save it to a file

On a large document `get_layout` and `get_connections` return tens of thousands of characters.
Ask for what you need: `get_layout` {ids, grips: false}, `get_connections` {id}.

**Build** — `add_component` {type, x, y}, `connect_components` {sourceId, targetId,
sourceParamIndex, targetParamIndex, append?}, `disconnect_components` {targetId,
targetParamIndex, sourceId?}, `delete_component` {id}, `add_variable_parameter` {id, index, side}

**Values and labels** — `set_component_value` {id, value} for panels, sliders and toggles,
`set_param_value` {id, index, value}, `set_slider` {id, min, max, value, digits, name},
`set_nickname`, `set_value_list`, `set_colour`, `set_script`

**Layout and display** — `set_component_position` {items:[{id,x,y}]}, `set_component_size`,
`create_group` {name, ids, color}, `add_to_group` / `remove_from_group` {groupId, ids},
`set_wire_display` {id|ids, inputIndex?, mode}, `set_preview` {id, hidden},
`set_enabled` {id|ids, enabled}

**Solution and Rhino** — `recompute` {id?|ids?}, `bake_component` {id, layer?}

**Document** — `save_document` {path?}, `load_document` {path}, `clear_document`,
`new_document`, `get_documents`, `activate_document` {name}

## The rules that matter

1. **Place by GUID, never by name.** Name lookup returns OBSOLETE twins and parameter
   containers with the same label — in vanilla Grasshopper too. Resolve with
   `search_components` (it reports an `obsolete` flag) and verify the type name in the reply.
2. **Wire targets by index, not by name.** Parameter names differ between plugin versions.
   Read the real names and positions with `get_component_info` first. Output names are often
   surprising (`Larger than`, not `Result`). A new wire **replaces** the ones already on that
   input; pass `append: true` to keep them.
3. **Judge success by the data.** `get_component_output` after every wiring step; an empty
   list means the wire does nothing. Then `get_errors`. Never trust the return message alone.
4. **A deleted component stays findable briefly.** Connecting to it succeeds and does nothing.
   When replacing a chain: place all new components, then rebuild all wiring, then verify.
5. **Wrong order means data trees.** `get_component_output` lists the branches (`path`,
   `count`) — read them before suspecting your logic. `Flatten Tree` and `Simplify Tree` are the usual fixes.
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

Groups survive being moved — membership is by id, not position. Change membership with
`add_to_group` and `remove_from_group`.

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
