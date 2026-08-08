# Grasshopper Agent Bridge

**An AI assistant can only build what it can verify.** This bridge turns a live Grasshopper
document into something an assistant can not only write to, but **observe, measure and
correct** — a closed loop instead of blind generation:

```
act        place a component, wire it, set a value
measure    what data is flowing? what turned red? where did it land?
correct    delete, disconnect, re-wire, lay out — and prove it worked
```

The difference sounds small and is everything. Without the measuring half, an assistant
produces canvases that look plausible and compute nothing, and a human has to read the screen
aloud to it after every step. With it, the assistant catches its own mistakes — wrong
components, dead wires, wrong data-tree branches — before you ever look up.

[alfredatnycu/grasshopper-mcp](https://github.com/alfredatnycu/grasshopper-mcp) (MIT) built
the server and the write half: an assistant could place and connect components. **What was
missing was the closed loop — that is the part this fork delivers.** With it, whatever you
build on a canvas, the assistant can verify against reality instead of against its own
intentions.

## What the loop is made of

| | Commands | Why it matters |
|---|---|---|
| **Observe** | `get_errors`, `get_connections`, `get_layout`, `get_component_output`, `search_components` | The assistant sees runtime warnings, real wiring, and the **data itself** — the only honest success check |
| **Correct** | `delete_component`, `disconnect_components` | A mistake can be undone instead of buried under a workaround |
| **Keep it legible** | `create_group`, `set_nickname`, `set_slider`, `set_component_position/size`, `set_preview`, `set_colour` | The canvas stays readable for the humans who inherit it |
| **Keep it safe** | `save_document`, `load_document` | Versioned checkpoints; any experiment is one command from rollback |
| **Reach everything** | `add_variable_parameter`, `set_value_list`, `set_param_value`, `set_script` | Plugin parameters hidden in right-click menus, list selections, embedded scripts |

31 commands in total, JSON over a local socket, no dependencies inside Grasshopper.
Full reference in [docs/commands.md](docs/commands.md).

## What is in here

```
bridge/             the .gha source (C#, targets Rhino 7 / .NET Framework 4.8)
docs/               install, protocol, command reference, workflow, pitfalls
skills/             three agent skills — build, diagnose, extend (see below)
tools/              optional operator helpers: layout, checkpoints, preview control
examples/robotics/  the case study this was built on (see below)
```

The Python tools run on the operator's machine and are optional — the bridge speaks plain
JSON over a socket, any language works, and Grasshopper itself needs nothing installed.

## Quickstart

1. Build and install the bridge → [docs/install.md](docs/install.md)
2. Drop the **Grasshopper MCP** component on the canvas (Params → Util), toggle to `True`.
   The status panel reads `Running on port 8080`.
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

4. Give your assistant the skills.

## The skills

Drop them into your agent's skills folder (for Claude Code: `.claude/skills/`). Each is a
single `SKILL.md`; they load on their own when the situation matches.

| Skill | For |
|---|---|
| [gh-canvas](skills/gh-canvas/SKILL.md) | **Building.** Connect, place by GUID, wire, verify the data, keep the canvas readable |
| [gh-diagnose](skills/gh-diagnose/SKILL.md) | **Something is wrong.** A read-only procedure: messages → data → wires → trees → orphans, before anything is changed |
| [gh-bridge-dev](skills/gh-bridge-dev/SKILL.md) | **The bridge is missing a command.** Handler, registration, build, redeploy — and how to reach plugin internals by reflection |

## The rules that made it work

Learned over one long build; the full list with evidence is in
[docs/pitfalls.md](docs/pitfalls.md). The three that prevent most damage:

1. **Place components by GUID, never by name.** Name lookup happily returns an OBSOLETE twin
   or a parameter container with the same label — in vanilla Grasshopper too.
2. **Judge success by the data, not by the reply.** A wiring call can report success and
   connect nothing. `get_component_output` shows what actually flows.
3. **When the order is wrong, look at the data tree** before you look at your logic.

## The case study

The loop was built and hardened on a real project: an industrial-robot programming chain of
~285 components — model slicing, cell geometry, tool calibration, collision and reach
checking, simulation, and machine-code export, assembled and debugged almost entirely through
this bridge. [examples/robotics/](examples/robotics/) contains the domain scripts from that
project; they double as patterns for driving any domain-specific chain (find components by
type instead of stored id, step a slider and read a verdict, refuse to export when a check
fails).

Nothing else in this repository depends on robotics.

## Status and scope

Working tool, not polished product: the API is stable enough to build on, the code still
carries its origins. Tested on **Rhino 7 for macOS**; the project targets .NET Framework 4.8
and should build for Rhino 7 on Windows unchanged (unverified).

## License and attribution

MIT, see [LICENSE](LICENSE) — inherited from the upstream project by Alfred Chen and kept.
[NOTICE.md](NOTICE.md) lists what came from where.
