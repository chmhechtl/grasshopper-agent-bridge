# Command reference

31 commands. Parameters are the keys inside `parameters`.

## Reading

### `get_document_info`
No parameters. → `name`, `path`, `componentCount`, `components[]` with `id`, `type`, `name`.

### `get_component_info`
`id` — → `type`, `name`, `description`, `inputs[]`, `outputs[]` (each with `name`, `nickname`,
`dataType`), and for panels and sliders the current `value`.

**Read the input list before wiring.** Names change between plugin versions; indices are what
you should wire against.

### `get_component_output`
`id`, `limit` (default 50) — the **volatile data** on each output, as strings, plus `count`.

The single most useful command in the set. A component that reports success but produces an
empty list is not wired the way you think.

### `get_connections`
No parameters. → every wire as `sourceId`, `sourceName`, `sourceParam`, `targetId`,
`targetName`, `targetParam`. Sources are resolved to the owning component, not the parameter.

### `get_errors`
No parameters. → every component carrying a runtime message, with `level`
(`Error` / `Warning` / `Remark`), the text, and canvas position.

Run it after every build step. Note that messages **persist until the component recomputes**,
so a stale warning can outlive its cause — check the data before believing it.

### `get_layout`
No parameters. → per object: `x`, `y` (pivot), `left`, `top`, `width`, `height` (the real box),
`inputs[]`/`outputs[]` with wire attachment points, plus all `groups` with their members.

**Pivot is not the box corner** and sits differently per component type. For overlap or
alignment maths use `left`/`top`; convert back to pivot only when writing positions.

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
`sourceParamIndex`/`targetParamIndex`.

Prefer indices for targets. Output names are often not what you expect — a comparison
component's output is `Larger than`, not `Result` — and a wrong name silently connects
nothing while still reporting success.

### `disconnect_components`
`targetId`, plus `targetParam` (**name only**, not an index), optionally `sourceId` to remove
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
(`"0.0 < 5.0 < 100.0"`). Expires the component, so the new value actually propagates.

Does **not** work on boolean toggles or colour swatches — see `set_param_value` and
`set_colour`.

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
`name`, `ids[]`, optional `color` — there is no "add to existing group"; rebuild the group with
the full member list.

### `set_preview`
`id`, `hidden` — hides a component's viewport preview. Essential once a plugin starts drawing
an axis cross per target.

## Document

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
