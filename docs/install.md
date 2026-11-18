# Installing the bridge

Two parts: one file (`GH_MCP.gha`) goes into Grasshopper's Libraries folder and you place a
component on the canvas; then your assistant connects to it through the MCP server.

**Requirements: Rhino 7 with Grasshopper** for the bridge. The MCP server and the helper
scripts in `tools/` need Python 3.10+ on the same machine.

## Option A: download the build

Take `GH_MCP.gha` from the [latest release](../../releases/latest) and skip to **Install** below.
Built on macOS against .NET Framework 4.8; it should load in Rhino 7 on Windows as well, but
that is untested.

## Option B: build it yourself

Needs the **.NET SDK 8**. It does not have to be installed system-wide — a local copy in
`~/.dotnet` is enough.

```bash
cd bridge
dotnet build GH_MCP/GH_MCP.csproj -c Release
```

The result lands in `bridge/GH_MCP/bin/Release/net48/GH_MCP.gha`.

If the compiler cannot find `Grasshopper.dll` or `RhinoCommon.dll`, point the project at your
Rhino installation. On macOS they live in

```
/Applications/Rhino 7.app/Contents/Frameworks/RhCore.framework/Versions/A/Resources/ManagedPlugIns/GrasshopperPlugin.rhp/
```

## Install

Copy `GH_MCP.gha` into Grasshopper's Libraries folder:

**macOS**
```bash
cp bridge/GH_MCP/bin/Release/net48/GH_MCP.gha \
   ~/Library/Application\ Support/McNeel/Rhinoceros/7.0/Plug-ins/Grasshopper*/Libraries/
```

**Windows**
```
%APPDATA%\Grasshopper\Libraries\
```

macOS quarantines downloaded files, and Grasshopper then ignores them without a word. After
downloading the release, clear it:

```bash
xattr -d com.apple.quarantine <path>/GH_MCP.gha
```

On Windows the equivalent is right-click → Properties → **Unblock**.

The release archive also contains `Newtonsoft.Json.dll`. Copy it into the same folder **only if**
Grasshopper reports that assembly as missing — Rhino ships its own copy, and adding a second one
where it is not needed can collide with other plugins.

## Run

1. **Restart Rhino.** .NET Framework cannot unload an assembly, so a replaced `.gha` is only
   picked up at the next start. This is the one thing that will trip you up repeatedly:
   editing the bridge always costs a restart, editing your Grasshopper document never does.
2. In Grasshopper, find **Grasshopper MCP** under **Params → Util** and place it.
3. Wire a **Boolean Toggle** to its input and set it to `True`.
4. The status output reads `Running on port 8080`.

Verify from a terminal:

```bash
nc -z 127.0.0.1 8080 && echo "bridge is listening"
```

```bash
printf '{"type":"get_document_info","parameters":{}}\n' | nc 127.0.0.1 8080
```

## Connect an MCP client

The MCP server is one Python file, `server/gh_mcp_server.py`. It needs Python 3.10+ and the
`mcp` package; with [uv](https://docs.astral.sh/uv/) the dependency is resolved from the file
itself.

**Claude Code, as a plugin** (MCP server plus skills):

```
/plugin marketplace add chmhechtl/grasshopper-agent-bridge
/plugin install grasshopper-agent-bridge@grasshopper-agent-bridge
```

**Any MCP client**, from a clone of this repository:

```bash
claude mcp add grasshopper -- uv run /path/to/grasshopper-agent-bridge/server/gh_mcp_server.py
```

or in a JSON config:

```json
{"mcpServers": {"grasshopper": {"command": "uv", "args": ["run", "/path/to/server/gh_mcp_server.py"]}}}
```

Without uv: `pip install 'mcp<2'`, then use `python3` as the command (the server is written
against version 1 of the SDK). `GH_BRIDGE_HOST`,
`GH_BRIDGE_PORT` and `GH_BRIDGE_TIMEOUT` override the defaults (`127.0.0.1`, `8080`, 120 s).

Then run `/onboarding-grasshopper-bridge` for a guided tour.

## Notes on the listener

The listener is **static** and bound to `127.0.0.1:8080`. Consequences worth knowing:

- It survives loading another document — the same server keeps serving whatever document is
  active, so a `load_document` does not kill your connection.
- Two Grasshopper documents each holding a bridge component do **not** fight over the port;
  the second one sees the server already running and does nothing.
- It listens on loopback only. Nothing is reachable from the network.

## When something does not answer

| Symptom | Cause |
|---|---|
| Connection refused | Toggle is `False`, component missing, or Rhino still starting |
| Commands hang, reads still work | A modal dialog is open in Rhino — some components open one when placed |
| `No handler registered for command type` | The running `.gha` is older than your source; restart Rhino |
| Component not in the menu at all | Wrong Rhino version target, or the file is quarantined |
