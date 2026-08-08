---
name: gh-bridge-dev
description: Extend the Grasshopper bridge itself — add a command to the .gha, reach a plugin capability the current commands cannot touch, rebuild and redeploy. Use when a needed operation has no command yet, when a command misbehaves, or when a plugin feature is only reachable through Grasshopper's internal API. Not for ordinary canvas work.
---

# Adding a command to the bridge

The bridge is a small C# Grasshopper plugin. Adding a command is two edits and a rebuild —
but the rebuild costs a Rhino restart, so **plan several changes at once.**

## Before writing anything: does it need a command?

Work down this list and stop at the first hit:

1. **Can an existing command do it?** `set_param_value` writes into unwired inputs;
   `add_variable_parameter` reveals parameters hidden in a plugin's right-click menu;
   `set_component_value` handles panels and sliders.
2. **Is it a right-click menu item rather than a component?** `search_components` only sees
   components. File writing, plugin toggles and save dialogs often live in menus and need no
   code at all.
3. **Can it be done on the canvas?** A few vanilla components usually beat a new command, and
   they stay visible to whoever inherits the document.

Only then write a command.

## The two edits

**1. A handler** in `bridge/GH_MCP/Commands/InspectionCommandHandler.cs` (or a new file):

```csharp
public static object DoTheThing(Command command)
{
    string idStr = command.GetParameter<string>("id");
    if (string.IsNullOrEmpty(idStr) || !Guid.TryParse(idStr, out var id))
    {
        throw new ArgumentException("Valid component id is required");
    }

    return RunOnUiThread(doc =>
    {
        var obj = doc.FindObject(id, true);
        if (obj == null)
        {
            throw new ArgumentException($"Component with ID {idStr} not found");
        }
        // ... do the work ...
        doc.NewSolution(false);
        return new { id = idStr, whatHappened = "..." };
    });
}
```

`RunOnUiThread` is mandatory — everything touching the document must run on Rhino's UI thread.
Throw on bad input; the registry turns exceptions into `success: false` with the message.

**2. Register it** in `Commands/GrasshopperCommandRegistry.cs`:

```csharp
RegisterCommand("do_the_thing", InspectionCommandHandler.DoTheThing);
```

## Build, deploy, restart

```bash
cd bridge
dotnet build GH_MCP/GH_MCP.csproj -c Release
cp GH_MCP/bin/Release/net48/GH_MCP.gha \
   ~/Library/Application\ Support/McNeel/Rhinoceros/7.0/Plug-ins/Grasshopper*/Libraries/
```

Then **restart Rhino**. .NET Framework cannot unload an assembly; a replaced `.gha` is only
read at startup. Symptom of forgetting: `No handler registered for command type`.

Because every bridge change costs a restart, **collect them**. Ask what else is missing before
building, and deploy once.

## Reaching plugin internals

Plugins hide capabilities behind menu handlers. Reflection reaches them, but the method names
are not standardised — one plugin used three different ones in the same release:

| Purpose | Seen as |
|---|---|
| Reveal a hidden input | `AddParameter(int)`, `AddInputParameter(int)` |
| Reveal a hidden output | `AddOutputParameter(int)` |

Probe several candidates rather than assuming one:

```csharp
var candidates = new[] { "AddParameter", "AddInputParameter" };
string name = candidates.FirstOrDefault(c => obj.GetType().GetMethod(c,
    BindingFlags.NonPublic | BindingFlags.Instance, null, new[] { typeof(int) }, null) != null);
```

To find the index and the method, read the plugin's source: the menu handler
(`MenuItemClickSomething`) shows both. Component sources also carry `ComponentGuid`, which is
the reliable way to place a component.

## Writing properties

Types differ more than they look. A property called `Code` is a plain string on one script
component and a wrapper object on another. Check before assuming:

```csharp
var property = obj.GetType().GetProperty("Code") ?? obj.GetType().GetProperty("ScriptSource");
if (property == null || !property.CanWrite) { throw new ArgumentException("..."); }
```

## Guards

Protect the bridge component from deletion **by type, not by name**:

```csharp
if (obj is GrasshopperMCPComponent) { throw new InvalidOperationException("..."); }
```

A name-substring guard also catches user groups that mention the bridge — they then become
undeletable and accumulate.

## Verify from outside

Never trust the build. After the restart, call the command and read the result:

```python
send("do_the_thing", {"id": some_id})
```

Then check the canvas with `get_component_output` or `get_layout` — the command may report
success while changing nothing, which is exactly the failure mode the loop exists to catch.

## Keep the contract

- Return a small object describing **what changed** (`{moved: 12, missing: []}`), not just
  `true`. Callers use it to verify.
- Accept a batch where it saves solutions: `set_component_position` takes `items[]` so one
  layout pass is one solve instead of hundreds.
- Document the command in `docs/commands.md`, including the trap that will bite the next user.
