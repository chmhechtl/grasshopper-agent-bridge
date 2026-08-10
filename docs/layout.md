# Laying out the canvas

An agent-built definition works and is unreadable. Components land where they were created,
wires cross at random, panels sit at their 120×60 default with the interesting half of their
content cut off. The definition computes the right answer and no human can check it.

This is not a cosmetic problem. A canvas nobody can read is a canvas nobody can audit, and an
agent that cannot be audited is a liability. Layout is the step that hands the work back.

**And it is the clearest demonstration of what the closed loop buys you.** An agent has no eye
for a canvas. It cannot glance at the screen and see that two components overlap. But it can
*measure*: `get_layout` returns real bounding boxes and connection grips, `get_connections`
returns the graph. Once the geometry is measurable, a good layout stops being a matter of taste
and becomes a computed result — and, more importantly, a **verifiable** one. The script can
state how many overlaps are left and how many wires run dead horizontal, before and after.

## Running it

```bash
python3 tools/gh_layout.py                 # lay out the whole canvas
python3 tools/gh_layout.py --dry-run       # print the plan, change nothing
python3 tools/gh_layout.py --compact       # tighter columns
python3 tools/gh_layout.py --check         # measure only: how many overlaps are there?
python3 tools/gh_layout.py --fix-overlaps  # nudge only what actually collides
python3 tools/gh_layout.py --align-only    # straighten wires, move nothing else
python3 tools/gh_layout.py --panels        # only resize panels
```

Spacing is tunable without editing the file: `--gutter-x=40`, `--gutter-y=20`, `--band-gap=90`.

Start with `--check`. It is read-only and tells you whether there is a problem worth a full
re-layout, which is the expensive and disruptive option.

## What the full pass does

1. **Build the graph** from `get_connections`.
2. **Columns by longest path.** Every component sits one column right of its furthest-back
   input, so data flows left to right with no back-edges.
3. **Pull leaf inputs right.** Without this, every slider and panel piles up in column 0 and
   that column grows thousands of units tall while the rest of the canvas is empty. Sliders
   belong next to what they drive, so they are pushed as late as possible instead.
4. **Order rows by barycenter.** Within a column, components are sorted by the average row of
   their inputs. This is the step that stops wires from crossing.
5. **Group bands.** Each group gets its own horizontal band. Group membership is stored by id,
   not by position, so the group boxes follow their members without any extra work.
6. **Compact each band** horizontally, so a band of four components does not span the width of
   the widest band on the canvas.
7. **Size panels by content.** Panels holding code or long output are widened; panels holding a
   single number stay small. A wall of identical grey rectangles carries no information.
8. **Align single-consumer wires.** Where an output feeds exactly one input, the source is
   nudged so the wire runs dead horizontal. This uses the grip offsets from `get_layout`, not
   the component centres, because a grip sits at its parameter's row, not at the middle.
9. **Detect and repair overlaps** against real bounding boxes, then write every position back
   in **one batched `set_component_position` call** — one solve instead of several hundred.

## The trap that will get you

**A component's pivot is not the corner of its box.** `get_layout` returns both: `x`/`y` is the
pivot, `left`/`top`/`width`/`height` is the actual frame. Overlap tests and alignment must use
the frame; `set_component_position` takes the pivot. Mixing them produces a layout that is
subtly wrong everywhere and obviously wrong nowhere, which is the worst kind.

Convert explicitly when writing back:

```python
{"id": node,
 "x": new_left + (obj["x"] - obj["left"]),
 "y": new_top  + (obj["y"] - obj["top"])}
```

## Two modes worth knowing

`--check` and `--fix-overlaps` are **surgical**. They do not re-layout anything. They look at
the canvas as it stands, report genuine collisions, and — with `--fix-overlaps` — move only the
components that actually collide. Everything a human deliberately placed stays where they put
it. This is the right tool after a hand edit; the full pass is for canvases the agent built.

`--align-only` is likewise surgical: it straightens wires and moves nothing else. It only shifts
leaf inputs, and only into space that is genuinely free. A cascade of shoves would be a
re-layout in disguise, which is exactly what this mode exists to avoid.

## It is only a script

`gh_layout.py` is a local Python file, not part of the bridge protocol, and none of it runs
inside Grasshopper. Any language can do the same thing: read `get_layout` and `get_connections`,
compute positions, write them back with `set_component_position`.

That is the point worth taking away. The bridge does not contain a layout engine and does not
need one. It exposes measurable geometry, and the layout engine falls out of that in 500 lines.
Whatever else you want the agent to reason about on a canvas is the same shape of problem.
