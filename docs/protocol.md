# Protocol

One TCP connection per command, line-delimited JSON, `127.0.0.1:8080`.

## Request

```json
{"type": "get_document_info", "parameters": {}}
```

Terminated by `\n`. The server reads one command, executes it on Rhino's UI thread, replies,
and closes.

## Response

```json
{"success": true, "data": { }, "error": null}
```

```json
{"success": false, "data": null, "error": "Error executing command 'x': ..."}
```

Also terminated by `\n`. The payload may carry a UTF-8 BOM — decode with `utf-8-sig`.

## Minimal client

```python
import json, socket

def send(command, params=None, timeout=120):
    sock = socket.socket()
    sock.settimeout(timeout)
    sock.connect(("localhost", 8080))
    sock.sendall((json.dumps({"type": command, "parameters": params or {}}) + "\n").encode())
    chunks = b""
    while not chunks.endswith(b"\n"):
        chunk = sock.recv(8192)
        if not chunk:
            break
        chunks += chunk
    sock.close()
    return json.loads(chunks.decode("utf-8-sig").strip())
```

`tools/gh.py` is this, plus a command-line entry point.

## Threading and timeouts

Every command runs on Rhino's UI thread and blocks until the solution finishes. Two things
follow:

- **Set a generous timeout.** A heavy document takes seconds per solve. Commands that trigger
  a re-solve (`set_component_value`, `connect_components`, …) are the slow ones; pure reads
  are fast.
- **A modal dialog freezes everything that re-solves.** Some components open a dialog when
  placed — a plugin's preset picker, for example. The command was executed, the dialog is
  waiting for a human, and your client sits in a timeout. Read commands still answer, which is
  a good way to tell this apart from a dead bridge.

## Data model

Values come back as **strings**, formatted the way Grasshopper prints them:

```
"{800, 0, 0}"                         a point
"O(1188.50,7.00,924.50) Z(0,0,1)"     a plane
"Circular Curve"                       a curve — type name only, no geometry
"12"                                   a number
```

This is deliberate: the bridge reports what the canvas shows, it is not a geometry
serialisation format. For numbers, parse; for geometry, use it as an identity check, not as
data. If you need real geometry out, write it to a file from inside Grasshopper.

Trees are flattened in `get_component_output`; the `count` field is the total across all
branches. When branch structure matters, put a `Tree Statistics` component on the canvas and
read its `Paths` output — the bridge has no separate tree inspection command.
