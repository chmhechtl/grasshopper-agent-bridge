# Tools

General-purpose helpers that drive the bridge over TCP. **Optional** — the bridge is a socket
server, any language works, and Grasshopper itself needs nothing installed.

Run them with Rhino open and the bridge listening.

| Script | What it does |
|---|---|
| `gh.py` | Minimal client. `python3 gh.py get_document_info` |
| `gh_layout.py` | Lays out the canvas from the graph. `--compact`, `--align-only`, `--check`, `--fix-overlaps`, `--dry-run` |
| `gh_checkpoint.py` | `save "message"` / `list` / `restore <commit>` — versioned checkpoints of the .gh file via git |
| `gh_preview.py` | Hides helper previews, keeps only what tells a story. `--list`, `--show-all` |
| `gh_play.py` | Steps a slider like an animation. `--loop`, `--pingpong`, `--slider "name"` |
| `gh_fit_slider.py` | Sets a slider's range to the data it indexes |

Domain-specific scripts from the robotics case study live in `../examples/robotics/`.
