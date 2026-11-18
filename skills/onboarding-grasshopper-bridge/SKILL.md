---
name: onboarding-grasshopper-bridge
description: Guided tour of the Grasshopper Agent Bridge — what it is, whether it is connected, every command by purpose, how to work with it and what to avoid. Use when the user runs /onboarding-grasshopper-bridge, has just installed the bridge, or asks "what can you do in Grasshopper", "how does the Grasshopper bridge work", "which Grasshopper commands are there".
---

# Onboarding: Grasshopper Agent Bridge

Walk the user through the bridge in their language. Explain, do not dump: short sections, and
after the overview offer to show something live. Sources, in this order: this file, then the
repository's `README.md`, `docs/commands.md` (every parameter), `docs/workflow.md` and
`docs/pitfalls.md` — read them when the user wants depth. If the files are not on disk, they are
at https://github.com/chmhechtl/grasshopper-agent-bridge.

## 1. Check the connection first

Call `get_document_info` (MCP tool of the `grasshopper` server; without MCP, send
`{"type": "get_document_info", "parameters": {}}` as one JSON line to `127.0.0.1:8080`).

- **Answers:** say which document is open and how many components it has.
- **Not reachable:** the tour still runs, but tell the user what is missing: Rhino 7 running,
  Grasshopper open, `GH_MCP.gha` in the Libraries folder (`docs/install.md`), the
  **Grasshopper MCP** component (Params → Util) on the canvas with a Boolean Toggle set to `True`.
- **`No handler registered for command type`:** the installed `.gha` is older than the server.
  Replace it and restart Rhino.

## 2. What it is, in three sentences

A small Grasshopper plugin opens a local socket; an MCP server turns every bridge command into a
tool. The point is the **closed loop**: the assistant does not only place components, it reads
back the data, the wiring, the runtime messages and the geometry of the canvas, and corrects its
own work. It is general-purpose — any definition, any plugin, nothing domain-specific.

## 3. The commands, by what they are for

| Purpose | Commands |
|---|---|
| **See** what is there | `get_document_info`, `get_component_info`, `get_connections`, `get_layout`, `search_components` |
| **Measure** whether it works | `get_component_output` (the data itself, with tree branches), `get_errors`, `recompute` |
| **Build** | `add_component`, `connect_components`, `add_variable_parameter` |
| **Correct** | `disconnect_components`, `delete_component`, `set_enabled` |
| **Set values** | `set_component_value` (panel, slider, toggle), `set_slider`, `set_param_value`, `set_value_list`, `set_colour`, `set_script` |
| **Keep it readable** | `set_nickname`, `create_group`, `add_to_group`, `remove_from_group`, `set_component_position`, `set_component_size`, `set_wire_display`, `set_preview` |
| **Rhino and files** | `bake_component`, `save_document`, `load_document`, `clear_document` |

Give one sentence per group on why it matters, and name the single most important command:
`get_component_output` — success is judged by the data, never by the reply.

## 4. What becomes possible

- Build a definition from an outcome-level brief ("a panel with holes sized by an attractor")
  and verify each step against the real data.
- Diagnose an existing definition: why is this red, why is the list empty, where does the tree
  go wrong — read-only, before anything is changed.
- Modify and extend someone else's canvas without breaking it, then prove it still computes.
- Tidy a canvas: `tools/gh_layout.py` lays it out from measured geometry (columns by data flow,
  groups in bands, no overlaps).
- Checkpoints: `tools/gh_checkpoint.py` versions the `.gh` file with git, any experiment is one
  command from rollback.
- Bake results into Rhino onto named layers.

The companion skills take over from here: `gh-canvas` (building), `gh-diagnose` (something is
wrong), `gh-bridge-dev` (the bridge lacks a command).

## 5. The rules that prevent most damage

1. **Place by GUID, never by name.** `search_components` first; name lookup can return an
   obsolete twin.
2. **Judge by the data.** A wiring call can report success and connect nothing — check with
   `get_component_output`.
3. **Wire by index** for inputs; names change between plugin versions.
4. **Save before layout or large edits.** Moving components creates no undo record.
5. **A modal dialog in Rhino freezes every command that re-solves.** Reads still answer — that
   is how to tell it from a dead bridge.
6. **Changing the bridge itself costs a Rhino restart;** changing the document never does.

## 6. Limits, stated plainly

Rhino 7 (tested on macOS). Values come back as strings the way Grasshopper prints them, not as
geometry. C# script components cannot be filled. Moves are not undoable. The assistant does not
see the canvas as an image — it measures it.

## 7. Close with an offer

End by offering one concrete next step that fits what the connection check found: on an empty
canvas, a two-minute live demo (slider → circle → read the output back → group and label it);
on an existing definition, a read-only health check (`get_errors`, then the data of anything
suspicious).
