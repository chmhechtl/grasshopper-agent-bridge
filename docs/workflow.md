# Working with an assistant on a live canvas

How to use this without producing a mess. The rules come from building a ~285-component
production chain this way (the case study in `examples/robotics/`); the reasoning matters
more than the specific commands.

## The loop

```
search_components   →  resolve the GUID, check obsolete
add_component       →  verify the returned type name
get_component_info  →  read the real input names and indices
connect_components  →  by index
get_component_output→  did data actually arrive?
get_errors          →  did anything turn orange or red?
```

Six steps, not two. Skipping the last two is what produces canvases that look right and
compute nothing.

## Checkpoint before you rebuild

`save_document` plus a git commit of the `.gh` file gives cheap rollback. `tools/gh_checkpoint.py`
does both and records the component count and open warnings in the commit message, so the
history shows when the document was healthy.

Take one **before** any layout pass and before replacing a chain of components — layout moves
create no undo record.

## Keep the canvas readable, mechanically

A canvas built by an assistant becomes unreadable faster than one built by hand, because
nothing forces tidiness. Three habits keep it usable:

- **Group by data-flow stage** and number the groups with two digits (`01`, `02`, … — otherwise
  `10` sorts before `2`). Groups are the reader's table of contents.
- **Label every control.** A panel reading `4` tells nobody it means material thickness.
  `set_slider` sets range, step, and name in one call; use it instead of leaving defaults.
- **Lay out from the graph, not by hand.** `tools/gh_layout.py` assigns columns by longest
  path, orders rows by the barycentre of incoming wires, gives each group its own horizontal
  band, and pushes apart anything that actually overlaps.

## Prefer coupling over discipline

Whenever two values must agree — a base under a machine, a sheet on a table, a working plane
on top of material — **wire them together instead of providing two sliders**. Two independent
inputs for one physical fact is a bug waiting for a distracted moment.

Every time this rule was applied, a pair of sliders disappeared and a class of error with it.

## Let the machine check what the eye cannot

Cheap, parametric checks turn "looks fine" into a verdict: does the result fit inside its
bounds, does anything intersect that must not, is every commanded state actually achievable.
Wire them into a single flag and let downstream steps — especially exports — refuse when the
flag is false. **A file that must not be used is better never written.**

Two subtleties that made such checks honest in practice:

- A test that reports *containment* the same way as *intersection* cannot tell "safely inside"
  from "sticking through the boundary". Containment needs its own test — for an axis-aligned
  box, checking the bounding-box corners is exact and cheap.
- Never judge feasibility from the *achieved* result when the solver substitutes a fallback
  for impossible inputs — measure the **commanded** value against the limit instead. (Inverse
  kinematics is the classic case: out-of-range targets come back as plausible poses.)

## Where to draw the line at scripting

Grasshopper components are readable by the people who inherit the file; scripts are not. This
project used exactly one script component, for the single thing with no native equivalent
(a file name that varies with the data). Everything else is vanilla.

Worth knowing when someone objects to scripts: **GhPython and C# components run inside Rhino**.
They need nothing installed. External Python is only needed for tooling that drives the bridge
from outside — which is an operator's convenience, never a requirement for the document.

## Visualise the thing being made

The parts of this build that paid off most were not the clever ones — they were the ones
that show state: a section plane moving through the model, a path turning red when it leaves
its bounds, a mechanism turning red when a command is infeasible. Cheap to build with
`Custom Preview` plus a colour switch, and each one replaces a paragraph of explanation.
