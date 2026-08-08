---
name: gh-diagnose
description: Diagnose a misbehaving Grasshopper definition through the bridge — components that turn orange or red, wires that report success but carry nothing, items coming out in the wrong order, results that do not match the inputs, or a canvas that stopped responding. Use whenever something on a live canvas is wrong and the cause is not obvious, before changing anything.
---

# Diagnosing a live Grasshopper definition

**Change nothing until you know what is wrong.** Every command here is read-only. The order
matters: it goes from cheapest and most common to rarest.

## 0. Is the bridge even answering?

```bash
nc -z 127.0.0.1 8080
```

| Observation | Cause |
|---|---|
| Connection refused | Toggle `False`, component missing, or Rhino still loading |
| Reads answer, anything that re-solves times out | **A modal dialog is open in Rhino.** Some components open one when placed. The command ran; a human has to dismiss the dialog |
| `No handler registered for command type` | The loaded `.gha` is older than the source. Restart Rhino |

## 1. Read the messages

```python
send("get_errors")
```

Gives every component with a runtime message, its level, and its canvas position.

**Messages persist until the component recomputes.** A warning can outlive its cause and
send you hunting for a problem that is already fixed. Before believing one, check whether the
component currently produces data (step 2). If it does, force a re-solve by nudging any
upstream value and read again.

## 2. Follow the data, not the wires

This is the step that resolves most problems.

```python
send("get_component_output", {"id": suspect, "limit": 10})
```

- **Empty list** → nothing arrives. The wire does not work, whatever the wiring call reported.
- **Data present but wrong** → the wiring is fine, the logic or the input is not.
- **Fewer items than expected** → something upstream filtered or culled.

Walk backwards from the failing component until you find the first one that produces what you
expect. The break is between that one and its consumer.

## 3. When a wire looks connected but is not

```python
send("get_connections")
```

Three causes, all of which report success at wiring time:

- **The source was deleted moments before.** A deleted component stays findable briefly;
  connecting to its id succeeds and does nothing.
- **The output name does not exist.** Comparison components output `Larger than`, not
  `Result`. A wrong name connects nothing.
- **The target parameter name changed between plugin versions.** Read the real names with
  `get_component_info` and wire targets by index.

## 4. Wrong order, wrong grouping, duplicated or missing items

**Suspect the data tree before your logic.** Place a `Tree Statistics` component, feed it the
suspect output, and read `Paths` and `Length`.

Known shapes:

| Symptom | Cause |
|---|---|
| Two outputs where you expect one | Inputs sit in different branches; a downstream generator processes each branch separately |
| A selection by index hits nothing | The tree is deeper than assumed — path `{0;0;3}`, not `{3}`. `Simplify Tree` fixes it robustly |
| An inserted item lands in the wrong position | `Merge` concatenates **per branch**. Different branches sit side by side, not in sequence. `Flatten Tree` before merging |

Path depth is not stable: adding a component upstream of an input can add a level.
`Simplify Tree` survives that, hard-coded paths do not.

## 5. A component you did not expect

After a build script fails partway, it leaves components behind. The next run creates a second
set. The orphans are unwired, produce warnings, and look exactly like a bug in the new code.

```python
known = set(your_id_map.values())
wired = {c["sourceId"] for c in conns} | {c["targetId"] for c in conns}
orphans = [o for o in layout["objects"] if o["id"] not in known and o["id"] not in wired]
```

Also worth checking: some plugins **auto-create a companion component** when you place one
(a value list next to a component with a mode input). If you wire that input differently, the
companion stays behind, orphaned.

## 6. Values that do not match what you set

- A panel emits **one string** for multi-line content, not a list. Split on newline if you
  meant a table.
- A component may emit a **cached** value if it was set without being expired. Read it back
  with `get_component_output` rather than trusting the write call.
- A slider's displayed value and its data are the same, but its **range** is a UI property —
  a value outside the range is clamped silently.

## 7. Geometry in the wrong place

- **Pivot is not the box corner.** `get_layout` returns `x`/`y` (pivot) and `left`/`top` (real
  box). Anything positional computed from pivots is wrong by a component-specific offset.
- A solver that substitutes a **fallback result** for an impossible input will not report the
  impossibility in its output — the values look plausible and are within limits. Compare the
  **commanded** input against the constraint, never the achieved result.

## Reporting what you found

State the measurement, not the impression: *"`get_component_output` on the Move component is
empty, its Geometry input has no source, the previous wire pointed at a component deleted in
the same run"* — not *"the Move component seems broken"*. The measurement tells the human
whether to trust the fix.
