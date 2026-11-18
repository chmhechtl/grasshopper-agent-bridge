#!/usr/bin/env python3
"""Live check: every tool through the MCP server against a running bridge.

Needs Rhino with the bridge component switched on. Works in a far corner of the canvas
(-4000, -4000) with its own components and deletes them again; the document's own objects
are only read. It does bake one circle onto the Rhino layer "gh_bridge_test", and it leaves
save_document, load_document, clear_document and a full recompute alone — those would
touch your document.

    python3 test_live.py
"""
import asyncio, json, sys, time
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
SERVER = str(Path(__file__).parent / "gh_mcp_server.py")
made = []; failed = []
async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable, args=[SERVER])) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        async def call(tool, **a):
            t = time.time(); x = await s.call_tool(tool, a); dt = time.time() - t
            text = x.content[0].text if x.content else ""
            return x.isError, (text if x.isError else json.loads(text)), dt, len(text)
        async def good(label, tool, check=lambda d: True, **a):
            err, d, dt, n = await call(tool, **a)
            okk = (not err) and check(d)
            print(f"{'PASS' if okk else 'FAIL'} {label:42} {dt*1000:6.0f} ms {n:7} chars" + ("" if okk else f"  -> {str(d)[:300]}"))
            if not okk: failed.append(label)
            return d
        async def bad(label, tool, **a):
            err, d, dt, n = await call(tool, **a)
            print(f"{'PASS' if err else 'FAIL'} {label:42} refused: {str(d)[:120]}")
            if not err: failed.append(label)
        # ---- reads on the real document
        info = await good("get_document_info", "get_document_info", lambda d: d["componentCount"] > 0)
        await good("get_errors", "get_errors")
        await good("get_connections", "get_connections", lambda d: "connections" in d)
        lay = await good("get_layout", "get_layout", lambda d: len(d["objects"]) > 0)
        some = [o["id"] for o in lay["objects"][:3]]
        await good("get_layout ids, no grips", "get_layout", lambda d: d["objectCount"] == len(some) and d["objects"][0]["inputs"] is None
                   and all(set(some) & set(g["members"]) for g in d["groups"]), ids=some, grips=False)
        await good("get_connections one object", "get_connections", lambda d: all(some[0] in (c["sourceId"], c["targetId"]) for c in d["connections"]), id=some[0])
        hits = await good("search_components Circle", "search_components", query="Circle")
        hl = hits.get("components", hits) if isinstance(hits, dict) else hits
        g = lambda n: next(h["guid"] for h in hl if h["name"] == n and not h.get("obsolete"))
        async def guid(q, n):
            _, d, *_ = await call("search_components", query=q)
            d = d.get("components", d) if isinstance(d, dict) else d
            return next(h["guid"] for h in d if h["name"] == n and not h.get("obsolete"))
        X, Y = -4000, -4000  # the test's own corner; anything there is a leftover of an aborted run
        stale = [o for o in lay['objects'] if o['x'] < -3500 and o['y'] < -3500]
        print('stale test objects:', [(o['type'], o['nickname']) for o in stale])
        for o in stale: await call('delete_component', id=o['id'])
        try:
          await body(call, good, bad, guid, X, Y)
        finally:
          for i in made: await call('delete_component', id=i)
          _, d, *_ = await call('get_document_info')
          print('cleanup: components', info['componentCount'] - len(stale), '->', d['componentCount'])
async def body(call, good, bad, guid, X, Y):
    if True:
        async def add(q, n, dx, dy=0):
            d = await good(f"add_component {n}", "add_component", lambda d: "id" in d, type=await guid(q, n), x=X+dx, y=Y+dy)
            made.append(d["id"]); return d["id"]
        slider = await add("Number Slider", "Number Slider", 0)
        toggle = await add("Boolean Toggle", "Boolean Toggle", 0, 60)
        panel = await add("Panel", "Panel", 0, 120)
        swatch = await add("Colour Swatch", "Colour Swatch", 0, 200)
        vlist = await add("Value List", "Value List", 0, 260)
        circle = await add("Circle", "Circle", 300)
        series = await add("Series", "Series", 300, 200)
        py = None
        try: py = await add("GhPython Script", "GhPython Script", 300, 400)
        except StopIteration: print("SKIP GhPython not found")
        # ---- values
        await good("set_slider", "set_slider", id=slider, min=0, max=10, value=4, digits=0, name="R")
        await good("set_component_value slider", "set_component_value", id=slider, value="7")
        await good("set_component_value slider NUMBER", "set_component_value", id=slider, value=6)
        await good("set_component_value toggle BOOL", "set_component_value", id=toggle, value=True)
        await good("set_component_value toggle 'true'", "set_component_value", id=toggle, value="true")
        await good("set_component_value panel", "set_component_value", id=panel, value="hello")
        await good("get_component_info panel", "get_component_info", lambda d: d.get("value") == "hello", id=panel)
        await good("get_component_info toggle", "get_component_info", lambda d: d.get("value") is True, id=toggle)
        await good("set_colour", "set_colour", id=swatch, colour="#A0785A")
        await good("set_value_list by index", "set_value_list", id=vlist, value="1")
        await good("set_nickname", "set_nickname", id=circle, name="Test circle")
        await good("set_component_size panel", "set_component_size", id=panel, width=200, height=80)
        await good("set_param_value Series.Count", "set_param_value", id=series, index=2, value=5)
        await good("series output 5 items", "get_component_output", lambda d: d["outputs"][0]["count"] == 5, id=series)
        if py:
            await good("set_script", "set_script", id=py, code="a = 42")
            await good("script output", "get_component_output", lambda d: any("42" in i for o in d["outputs"] for i in o["items"]), id=py)
        # ---- wiring
        await good("connect by index", "connect_components", sourceId=slider, targetId=circle, targetParamIndex=1)
        await good("connect by name, append", "connect_components", lambda d: d.get("targetParam") == "Radius", sourceId=series, targetId=circle, sourceParam="Series", targetParam="Radius", append=True)
        await good("circle output 6 (2 sources)", "get_component_output", lambda d: d["outputs"][0]["count"] == 6, id=circle)
        await good("disconnect one source", "disconnect_components", lambda d: d["removedWires"] == 1 and d["remaining"] == 1, targetId=circle, targetParam="Radius", sourceId=series)
        await good("connect replaces by default", "connect_components", sourceId=slider, targetId=circle, targetParamIndex=1)
        await good("circle output 1 again", "get_component_output", lambda d: d["outputs"][0]["count"] == 1, id=circle)
        await good("set_preview hidden", "set_preview", id=circle, hidden=True)
        await good("set_component_position batch", "set_component_position", lambda d: d["moved"] == 2, items=[{"id": slider, "x": X, "y": Y-50}, {"id": circle, "x": X+350, "y": Y-50}])
        grp = await good("create_group", "create_group", name="mcp selftest", ids=[slider, circle], color="#FFAA00")
        made.insert(0, grp["id"])
        await good("add_to_group", "add_to_group", lambda d: d["members"] == 3, groupId=grp["id"], ids=[panel])
        await good("remove_from_group", "remove_from_group", lambda d: d["members"] == 2, groupId=grp["id"], ids=[panel])
        await good("set_wire_display", "set_wire_display", lambda d: d["changed"] == [circle], id=circle, inputIndex=1, mode="hidden")
        await good("set_enabled off", "set_enabled", id=circle, enabled=False)
        await good("set_enabled on", "set_enabled", ids=[circle], enabled=True)
        await good("recompute ids", "recompute", lambda d: d["expired"] == 1, ids=[circle])
        await good("bake_component", "bake_component", lambda d: d["count"] == 1, id=circle, layer="gh_bridge_test")
        # ---- error paths
        await bad("unknown id", "get_component_info", id="00000000-0000-0000-0000-000000000000")
        await bad("garbage id", "get_component_output", id="abc")
        await bad("missing required arg", "set_nickname", id=circle)
        await bad("bad enum", "set_wire_display", id=circle, mode="dotted")
        await bad("position without args", "set_component_position")
        await bad("set_enabled without ids", "set_enabled", enabled=True)
        await bad("toggle with nonsense", "set_component_value", id=toggle, value="maybe")
        await bad("connect wrong name", "connect_components", sourceId=slider, targetId=circle, targetParam="Nope")
        await bad("add unknown component", "add_component", type="Definitely Not A Component", x=X, y=Y)
        await bad("variable param on plain component", "add_variable_parameter", id=circle, index=0)
        await bad("add_to_group on non-group", "add_to_group", groupId=circle, ids=[slider])
asyncio.run(main())
sys.exit(f"FAILED: {failed}" if failed else print("all passed"))
