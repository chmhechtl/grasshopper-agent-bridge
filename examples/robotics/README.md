# Case study: robot programming chain

These scripts drove the project the bridge was hardened on — a ~285-component Grasshopper
chain from CAD model to executable robot code. They assume that specific document and will
not run against yours; they are here because the **patterns** transfer to any domain:

| Script | Pattern it demonstrates |
|---|---|
| `gh_export_rapid.py` | Batch export driven by a slider; **refuses to write when an on-canvas safety flag is false**; one file per data slice with a name derived from the data |
| `gh_export_profile.py` | Pull numeric series out of the live document into CSV for analysis elsewhere — instead of building charts on the canvas |
| `gh_check_collisions.py` | Step through every state of a parametric model and collect a verdict per state; exit non-zero if any fails, so it can gate a release |

Common to all three: components are found **by type or nickname, not by stored id**, so the
canvas can be rearranged freely without breaking the tooling.
