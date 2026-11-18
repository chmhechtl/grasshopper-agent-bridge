# Tools

Optional operator helpers. The bridge itself is the product — a socket server speaking JSON,
usable from any language with nothing to install inside Grasshopper. For MCP clients, see
`../server/`.

| Script | What it does |
|---|---|
| `gh.py` | Minimal client. `python3 gh.py get_document_info` |
| `gh_layout.py` | Lays out the canvas from the graph — columns by data flow, wires straightened, overlaps repaired. `--check`, `--fix-overlaps`, `--align-only`, `--compact`, `--panels`, `--dry-run`. Walkthrough: [docs/layout.md](../docs/layout.md) |
| `gh_checkpoint.py` | `save "message"` / `list` / `restore <commit>` — versioned checkpoints of the .gh file via git |
| `gh_preview.py` | Hides helper previews in the viewport, keeping the types you name. `--keep=TypeA,TypeB`, `--list`, `--show-all` |
