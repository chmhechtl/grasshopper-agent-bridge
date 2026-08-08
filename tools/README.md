# Tools

Python helpers that drive the bridge over TCP. **Optional** — the bridge is a socket server,
any language works, and Grasshopper itself needs nothing installed.

Run them from this folder with Rhino open and the bridge listening.

| Script | What it does |
|---|---|
| `gh.py` | Minimal client. `python3 gh.py get_document_info` |
| `gh_layout.py` | Lays out the canvas from the graph. `--compact`, `--align-only`, `--check`, `--fix-overlaps`, `--dry-run` |
| `gh_checkpoint.py` | `save "message"` / `list` / `restore <commit>` — versioned checkpoints of the .gh file via git |
| `gh_preview.py` | Hides helper previews, keeps only what tells a story. `--list`, `--show-all` |
| `gh_play.py` | Steps a slider like an animation. `--loop`, `--pingpong`, `--slider "name"` |
| `gh_fit_slider.py` | Sets a slider's range to the data it indexes |

The remaining scripts are examples of driving a domain-specific chain and assume the robotics
document described in `docs/workflow.md`:

| Script | What it does |
|---|---|
| `gh_export_rapid.py` | Writes robot programs, one file per layer, refusing unsafe ones |
| `gh_export_profile.py` | Exports joint angles and tool position per path point as CSV |
| `gh_check_collisions.py` | Steps the whole program and reports every unsafe pose |

They are included because the patterns transfer: find components by type or nickname rather
than by stored id, step a slider and read a verdict, refuse to write when a check fails.
