# Command reference

41 commands. Parameters are the keys inside `parameters`. The MCP server
(`server/gh_mcp_server.py`) exposes each one as a tool of the same name with the same keys.

## Reading

### `get_document_info`
No parameters. → `name`, `path`, `componentCount`, `components[]` with `id`, `type`, `name`.

### `get_component_info`
`id` — → `type`, `name`, `description`, `inputs[]`, `outputs[]` (each with `name`, `nickname`,
`dataType`), and for panels, sliders and boolean toggles the current `value`.

**Read the input list before wiring.** Names change between plugin versions; indices are what
you should wire against.

### `get_component_output`
`id`, `limit` (default 50) — the **volatile data** on each output, as strings, plus `count`,
`branchCount` and `branches[]` (`path`, `count`) — the tree structure, so a branch mismatch is
visible without placing a Tree Statistics component.

The single most useful command in the set. A component that reports success but produces an
empty list is not wired the way you think.

### `get_connections`
Optional `id` — only the wires into or out of that object. → every wire as `sourceId`, `sourceName`, `sourceParam`, `targetId`,
`targetName`, `targetParam`. Sources are resolved to the owning component, not the parameter.

### `get_errors`
No parameters. → every component carrying a runtime message, with `level`
(`Error` / `Warning` / `Remark`), the text, and canvas position.

Run it after every build step. Note that messages **persist until the component recomputes**,
so a stale warning can outlive its cause — check the data before believing it.

### `get_layout`
Optional `ids[]` (only these objects and the groups they belong to) and `grips: false` (omit `inputs`/`outputs`). → per object: `x`, `y` (pivot), `left`, `top`, `width`, `height` (the real box),
`inputs[]`/`outputs[]` with wire attachment points, plus all `groups` with their members.

On a large document the full reply runs to tens of thousands of characters, most of it wire
grips. An assistant should ask for `ids` and `grips: false` unless it is doing layout maths.

**Pivot is not the box corner** and sits differently per component type. For overlap or
alignment maths use `left`/`top`; convert back to pivot only when writing positions.

### `describe_document`
Optional `clusterId`. → `scope`, `objectCount`, `objects[]` — everything needed to understand or
rebuild a definition. Per object: `id`, `componentGuid` (pass it to `add_component`), `type`,
`name`, `nickname`, `x`, `y`, `enabled`, `isCluster`, `value` (panel text, slider
`min < value < max`, toggle, value list, script source, expression, scribble text), `members`
for groups, and `inputs[]` / `outputs[]`. Per parameter: `mapping` (`None` / `Flatten` /
`Graft`), `reverse`, `simplify`, `expression`, `persistent[]` (values typed or internalised
into it, first 20 of `persistentCount`) and `sources[]` with the owning object's `id` and
`paramIndex`.

With `clusterId` the reply describes the **inside** of that cluster; nested clusters are found
by their own id. A password-protected cluster is refused — the bridge does not go around the
lock.

The reply is large (about 160,000 characters for 190 objects). Write it to a file and query
that, rather than reading it whole.

### `get_documents`
No parameters. → every document open in the editor: `index`, `name`, `path`, `objectCount`,
`modified`, `active`.

### `search_components`
`query` — searches Grasshopper's own registry. → `guid`, `name`, `category`, `subCategory`,
`obsolete`.

Always the first step before placing something. Note it finds **components only, never
right-click menu items** — several capabilities live in menus and are invisible here.

## Building

### `add_component`
`type` (GUID or name), `x`, `y` — → the new `id` and its `type`.

**Use a GUID.** Name lookup falls back to fuzzy matching and cheerfully returns an OBSOLETE
twin or a parameter container of the same name.

### `connect_components`
`sourceId`, `targetId`, and either `sourceParam`/`targetParam` (names) or
`sourceParamIndex`/`targetParamIndex`. Optional `append: true`.

**A new wire replaces the wires already on that input** — like dragging one on the canvas.
`append: true` is the shift-drag: existing sources stay.

Prefer indices for targets. Output names are often not what you expect — a comparison
component's output is `Larger than`, not `Result`. Since 0.2.1 a name that does not exist is
reported as an error; before, the reply said `success: true` with the error buried in `data`.

### `disconnect_components`
`targetId`, plus `targetParam` (name) or `targetParamIndex`, optionally `sourceId` to remove
a single wire instead of all of them.

### `delete_component`
`id` — refuses to delete the bridge component itself. Also deletes groups.

**A deleted component stays findable for a moment.** Connecting to a deleted id reports
success and produces nothing. When replacing a chain: place all new components first, then
rebuild the wiring from scratch, then verify with `get_component_output`.

### `add_variable_parameter`
`id`, `index`, optional `side: "output"` — toggles a parameter that a plugin hides in its
right-click menu.

Plugins are inconsistent about the method name behind it; the bridge tries `AddParameter`,
`AddInputParameter` and `AddOutputParameter`.

## Values and labels

### `set_component_value`
`id`, `value` — panels take text, sliders take a number or an init string
(`"0.0 < 5.0 < 100.0"`), boolean toggles take `true` / `false`. Expires the component, so the new value actually propagates.

Does **not** work on colour swatches — see `set_colour`. Do not switch off the toggle that
feeds the bridge component: the listener stops and nothing can switch it back on.

### `set_param_value`
`id`, `index`, `value` — writes a persistent value into an input that has no wire. Works for
`Param_Integer`, `Param_Number`, `Param_Boolean`, `Param_String`.

Fails on the generic inputs most maths components use. When you need a constant there, feed it
from a `Number` parameter object instead.

### `set_slider`
`id`, `min`, `max`, `value`, `digits` (0 = integer), optional `name`.

A slider's range is a UI property — no wire can drive it. Re-run this when your data changes
size.

### `set_nickname`
`id`, `name` — works on components **and groups**.

### `set_value_list`
`id`, `value` — selects an entry by name or index.

### `set_colour`
`id`, `colour` (e.g. `#A0785A`) — sets a colour swatch.

### `set_script`
`id`, `code` — fills a script component's source. Works on GhPython; the C# component stores
its source differently and is not supported.

## Layout and display

### `set_component_position`
`id`, `x`, `y` — or `items: [{id, x, y}, ...]` for a batch, which is one solution instead of
hundreds.

**Moving components creates no undo record.** Save first.

### `set_component_size`
`id`, `width`, `height` — mainly for panels; the default box is too small for generated code.

### `create_group`
`name`, `ids[]`, optional `color`.

### `add_to_group`
`groupId`, `ids[]` — adds existing objects to an existing group. → `added`, `skipped`
(already members or not found), `members`.

### `remove_from_group`
`groupId`, `ids[]` — takes objects out of a group; they stay on the canvas. → `removed`,
`skipped`, `members`.

### `set_wire_display`
`mode` (`default` / `faint` / `hidden`), and `id` or `ids[]`, optional `inputIndex` — how the
wires **into** a parameter are drawn. Without `inputIndex` the target must be a standalone
parameter (relay, number, panel); with it, that input of a component. → `changed`, `skipped`.

Long wires that cross the whole canvas are the usual candidates for `faint`. Hidden wires still
carry data — `get_connections` keeps reporting them.

### `set_enabled`
`enabled`, and `id` or `ids[]` — the canvas' Enabled switch. A disabled component computes
nothing and passes no data on. → `changed`, `skipped`. The bridge component itself is skipped.

### `set_preview`
`id`, `hidden` — hides a component's viewport preview. Essential once a plugin starts drawing
an axis cross per target.

## Solution and Rhino

### `recompute`
No parameters: expire and recompute the whole document. With `id` or `ids[]`: only those
objects and everything downstream. → `all`, `expired`, `missing`.

The cure for stale runtime messages — `get_errors` after a `recompute` shows what is true now.

### `bake_component`
`id`, optional `layer` — bakes the object's geometry into the active Rhino document. The layer
is created when missing. → `count`, `objects[]` (Rhino object ids).

Baking twice gives two copies; the bridge does not track what it baked before.

## Document

### `new_document`
No parameters. Opens an empty document next to the ones already open and makes it active.
Nothing is closed, and the listener keeps running — the new document needs no bridge component.

### `activate_document`
`name` or `index` — switches the active document. All other commands act on the active one.

**Prefer `name`.** The order of `get_documents` changes when the active document changes, so an
index is only good until the next switch.

### `save_document`
optional `path` — without one, saves where the document came from.

### `load_document`
`path` — loads into the editor and closes the previous document. Closing matters: some plugins
enforce unique names across all open documents.

### `clear_document`
Removes everything except the bridge component, toggles and panels.

## Inherited from upstream

`create_point`, `create_curve`, `create_circle` (compute only, they do not add to the
document), `create_pattern`, `get_available_patterns`.
