# Attribution

## Upstream

This project is a fork of **[grasshopper-mcp](https://github.com/alfredatnycu/grasshopper-mcp)**
by Alfred Chen, MIT licensed, forked in August 2026 at commit `1e5360e`.

Kept from upstream: the component architecture, the TCP command loop inside the Grasshopper
component, the command registry pattern, and the handlers for `add_component`,
`connect_components`, `set_component_value`, `get_component_info`, `get_document_info`,
`clear_document`, the geometry commands and the intent/pattern commands.

Changed in this fork:

- Retargeted the project to **Rhino 7 / .NET Framework 4.8**. The upstream binary was linked
  against Rhino 8 and loaded silently as nothing on Rhino 7.
- `save_document` and `load_document` were disabled stubs returning an error message; both
  are implemented (`GH_DocumentIO`), and loading closes the previous document.
- `connect_components` no longer rewrites parameter names through a fuzzy table
  (`length` → `Y Size` broke wiring silently) and now verifies the wire exists before
  reporting success.
- `set_component_value` expires the component, otherwise it kept emitting its cached value.
- `delete_component` protects the bridge component by **type**, not by a name substring —
  the substring test also caught user groups named after it, which could then never be deleted.
- Added: `get_errors`, `get_connections`, `get_layout`, `get_component_output`,
  `search_components`, `delete_component`, `disconnect_components`, `create_group`,
  `set_component_position`, `set_component_size`, `set_nickname`, `set_slider`,
  `set_param_value`, `set_value_list`, `set_preview`, `set_colour`, `set_script`,
  `add_variable_parameter`, `add_to_group`, `remove_from_group`, `set_wire_display`,
  `set_enabled`, `recompute`, `bake_component`, `describe_document`, `get_documents`,
  `new_document`, `activate_document`.
- Added an MCP server (`server/gh_mcp_server.py`) that replaces the upstream Python bridge and
  exposes every document command as a tool.

## Dependencies not included

- **Rhino / Grasshopper** (McNeel) — commercial, required to build and run.
- **Newtonsoft.Json** — referenced by the bridge, ships with Grasshopper.
