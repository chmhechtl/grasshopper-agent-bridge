# Grasshopper MCP Bridge — robotics edition

Drive a live Grasshopper document from an AI assistant: place components, wire them,
**read back what actually happened**, and iterate. Built while preparing an industrial
robotics course, so it is aimed at chains that end in real machine code — but nothing in it
is course-specific.

The bridge is a fork of [alfredatnycu/grasshopper-mcp](https://github.com/alfredatnycu/grasshopper-mcp)
(MIT). The original could place and connect components. This fork adds what turns that into
a usable working loop: **observation, repair, layout and persistence.**

## Why a fork

The original bridge is write-only in practice. It can create things, but the assistant cannot
see whether the result works — that job falls to the human, who has to read the canvas aloud.
Everything added here serves one goal: close the loop.

| Added | What it makes possible |
|---|---|
| `get_errors` | Read every runtime warning and error, with component and position |
| `get_connections`, `get_layout` | See the actual wiring, positions, sizes, group membership |
| `get_component_output` | See the **data** flowing out of a component — the only honest success check |
| `search_components` | Resolve a component GUID from the live registry, with an `obsolete` flag |
| `delete_component`, `disconnect_components` | Undo a mistake instead of piling another one on top |
| `set_component_position/size`, `create_group` | Lay out and annotate the canvas mechanically |
| `set_nickname`, `set_slider`, `set_colour`, `set_param_value` | Label controls so a human can read them |
| `save_document`, `load_document` | Versioned checkpoints — the originals were disabled stubs |
| `set_preview` | Hide helper geometry so the viewport stays readable |
| `add_variable_parameter` | Reach parameters that plugins hide in the right-click menu |

## What is in here

```
bridge/           the .gha source (C#, targets Rhino 7 / .NET Framework 4.8)
tools/            Python helpers that drive the bridge over TCP
skills/gh-canvas/ an agent skill: connection, commands, and the rules that matter
docs/             install, protocol, command reference, workflow, pitfalls
```

The Python tools are for the operator's machine. **They are not required to use the bridge** —
the bridge speaks plain JSON over a socket, and Grasshopper itself needs nothing installed.

## Quickstart

1. Build and install the bridge → [docs/install.md](docs/install.md)
2. Drop the **Grasshopper MCP** component on the canvas (Params → Util), set its toggle to True.
   The status panel should read `Running on port 8080`.
3. Talk to it:

```python
import json, socket

def send(command, params=None):
    s = socket.socket(); s.connect(("localhost", 8080))
    s.sendall((json.dumps({"type": command, "parameters": params or {}}) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(8192)
        if not chunk:
            break
        data += chunk
    s.close()
    return json.loads(data.decode("utf-8-sig").strip())

print(send("get_document_info"))
```

4. Give your assistant [skills/gh-canvas/SKILL.md](skills/gh-canvas/SKILL.md).

## The rules that made it work

Learned the hard way over one long build. The full list with evidence is in
[docs/pitfalls.md](docs/pitfalls.md); these three prevent most of the damage:

1. **Place components by GUID, never by name.** Name lookup happily returns an OBSOLETE
   twin or a parameter container with the same label — in vanilla Grasshopper too, not just
   in plugins.
2. **Judge success by the data, not by the reply.** A `connect_components` call can report
   success and produce no working wire. `get_component_output` shows what is really flowing;
   an empty list means the wire does nothing.
3. **When the order is wrong, look at the data tree.** Three separate ordering bugs in one
   project traced back to branch structure, not to logic.

## Status and scope

Used daily to build a robot programming chain of ~285 components: model slicing, cell
geometry, tool definition, collision and reach checking, simulation, and RAPID export for an
ABB IRC5. It is a working tool, not a polished product — the API is stable enough to build
on, the code still carries its origins.

Tested on **Rhino 7 for macOS**. The bridge targets .NET Framework 4.8 and should build for
Rhino 7 on Windows unchanged; nobody has verified that yet.

## License and attribution

MIT, see [LICENSE](LICENSE) — inherited from the upstream project by Alfred Chen and kept.
See [NOTICE.md](NOTICE.md) for what came from where.

[Robot Components](https://github.com/RobotComponents/RobotComponents) (GPL v3) is used by the
example workflow but is **not** redistributed here; install it yourself if you want the
robotics parts.
