# Pitfalls

Every entry here cost real debugging time. They are ordered by how much.

## Success messages lie

`connect_components` can return `success: true` where no working wire exists: the source
component was deleted moments ago and stays findable briefly. Two more cases are fixed — a
parameter name that does not exist is an error since 0.2.1 (the reply used to wrap the failure
in a success), and names are no longer rewritten by a fuzzy table — but the class of problem
remains.

**Check `get_component_output` after wiring.** An empty list means the wire does nothing. This
one rule would have saved more time than all the others combined.

## Name lookup returns the wrong component

Grasshopper keeps OBSOLETE versions of its own components registered under the same display
name — and parameter containers share names with the components that produce them. Placing
`"Flatten Tree"` by name gets you `GH_FlattenTreeComponent_OBSOLETE`, which behaves subtly
differently.

**Resolve the GUID with `search_components` first** and check the `obsolete` flag. Then verify
the type name in the `add_component` reply.

Vanilla GUIDs can also be extracted from `Grasshopper.dll` — the UTF-16 string cluster of a
component's name, description and parameters is immediately followed by its GUID.

## When the order is wrong, suspect the data tree

Three separate ordering bugs, all the same root cause:

| Symptom | Cause |
|---|---|
| Two output modules instead of one | `Divide Curve` puts points in path `{0;0}`, not `{0}` |
| Layer selection hit nothing | `Contour` nests deeper the more components feed its inputs |
| An inserted point landed twice at the start and never at the end | `Merge` concatenates **per branch**; different branches sit side by side |

`Simplify Tree` and `Flatten Tree` fix these, but the lesson is diagnostic: **when items come
out in the wrong order, look at the branch structure before you look at your logic.**
`get_component_output` lists every branch with its path and item count.

## A modal dialog freezes everything

Some components open a dialog when placed — a plugin's preset picker, for instance. The
command executed, the dialog waits for a human, and every command that triggers a solution
times out. **Read commands still answer.** That asymmetry is the diagnostic: if
`get_document_info` works but `add_component` hangs, look at the Rhino window.

## The `.gha` only loads at startup

.NET Framework cannot unload an assembly. A replaced `.gha` is picked up at the next Rhino
start, never before. Symptom: `No handler registered for command type 'x'` for a command you
just wrote.

**Batch bridge changes.** Collect several additions, build once, restart once.

## Aborted build scripts leave orphans

A script that places components and crashes before saving their ids leaves them on the canvas.
The next run creates a second set. The orphans are unwired, produce warnings, and are easy to
mistake for a bug in the new code — twice this sent debugging in the wrong direction.

**Detection:** components that appear in neither your id map nor in `get_connections`. Sweep
for them after any failed run.

## Panels emit stale values

`set_component_value` used to set the text without expiring the component, so it kept emitting
its previous value — including the placeholder text of a fresh panel. Fixed here, but the same
shape appears elsewhere: after setting a value, read it back before trusting it.

A multi-line panel emits **one string**, not a list. Split it with `Text Split` on a newline
if you meant a table.

## Pivot is not the box corner

`Attributes.Pivot` sits at a different place inside the bounding box for every attribute type.
Overlap detection and alignment computed from pivots produce quiet nonsense. `get_layout`
returns `left`/`top` alongside `x`/`y` for exactly this reason.

## Moving components has no undo

`set_component_position` and `set_component_size` do not create undo records. Ctrl+Z will not
bring the old layout back. Save — or make a checkpoint commit — before any layout pass.

## Delete guards that match on names

The upstream bridge refused to delete anything whose nickname contained `MCP`. That also
caught user groups named "MCP bridge", which then accumulated on every regroup and could never
be removed. **Guard on type, not on a name substring.** (Fixed here; mentioned because it is
an easy mistake to repeat in your own tooling.)

## Not everything is a component

`search_components` finds components. Several capabilities live only in **right-click menus**
and are invisible to it:

- writing a file: a Panel's *Stream contents…* (Rhino 7 for macOS ships **no** file-writing
  component — `Stream Contents` is absent),
- plugin features hidden behind menu toggles, reachable through `add_variable_parameter`.

Twice a capability was declared missing when it existed in a menu. **When a feature seems
absent, check the context menu before building a workaround.**

## Dragging a slider skips values

Grasshopper does not solve for every intermediate value while a slider is dragged. A workflow
that generates one file per slider position will silently miss some. Step the slider
programmatically with a pause, and verify the result count.
