---
name: gh-canvas
description: Arbeite an der Grasshopper-Leinwand über die GH_MCP-Brücke (Port 8080) — Bausteine platzieren, verdrahten, Fehler auslesen, RAPID prüfen, Leinwand automatisch anordnen und Panels passend dimensionieren. Nutze diesen Skill, sobald es um Grasshopper, Rhino, Robot Components, die Roboterkette oder RAPID-Ausgabe im China-Kursprojekt geht — auch bei "räum die Leinwand auf", "ordne das an", "warum ist der Baustein rot", "was kommt im RAPID raus".
---

# Grasshopper-Leinwand über die MCP-Brücke

Die Brücke ist ein selbst gebauter Fork mit Inspektionsbefehlen. Quellcode:
`11_Robotics_Operation_and_Programming/02_Praxis/grasshopper-mcp` (Branch `china`).
Stand und Fallen: `../MCP-BRIDGE-STATUS.md` — **vor dem Bauen lesen.**

## Verbindung

Rhino/Grasshopper muss laufen, GH_MCP-Komponente auf der Leinwand, Toggle auf True.
Prüfen mit `nc -z 127.0.0.1 8080`. Befehle gehen als eine JSON-Zeile über TCP:

```python
import json, socket
def send(cmd, params=None, timeout=120):
    s = socket.socket(); s.settimeout(timeout); s.connect(("localhost", 8080))
    s.sendall((json.dumps({"type": cmd, "parameters": params or {}}) + "\n").encode())
    data = b""
    while True:
        chunk = s.recv(8192)
        if not chunk: break
        data += chunk
        if data.endswith(b"\n"): break
    s.close()
    return json.loads(data.decode("utf-8-sig").strip())
```

Fertiges Hilfsskript: `grasshopper-mcp/tools/gh.py` (falls vorhanden), sonst obiges einbetten.

## Befehle

Lesen: `get_document_info`, `get_component_info` {id}, `get_connections`, `get_errors`,
`get_component_output` {id, limit}, `get_layout`, `search_components` {query}

Bauen: `add_component` {type, x, y}, `connect_components` {sourceId, targetId, sourceParam,
targetParamIndex}, `disconnect_components` {targetId, targetParam|targetParamIndex},
`delete_component` {id}, `set_component_value` {id, value}, `set_value_list` {id, value},
`add_variable_parameter` {id, index}, `create_group` {name, ids, color}

Layout: `set_component_position` {items:[{id,x,y}]} (Batch), `set_component_size` {id, width, height}

Speichern/Laden: `save_document` {path?} (ohne Pfad = an den Ort des Dokuments),
`load_document` {path} — lädt die Datei in den Editor.

## Eiserne Regeln

1. **Bausteine nur per GUID platzieren, nie per Name.** Die Namenssuche erwischt bevorzugt
   OBSOLETE-Altversionen oder Parameter-Container mit identischem Namen. GUID immer erst über
   `search_components` holen (liefert `obsolete`-Flag) und den Typnamen der Antwort prüfen.
2. **Eingänge per `targetParamIndex` verdrahten, nicht per Name** — sicherer bei gleichnamigen
   oder umbenannten Anschlüssen (z. B. Move: „Translation" hieß früher so, heute „Motion").
   Indizes vorher mit `get_component_info` ablesen.
3. **Nach dem Löschen bleibt ein Baustein kurz auffindbar.** Ein connect auf eine gelöschte ID
   meldet Erfolg, erzeugt aber keinen wirksamen Draht. Beim Ersetzen verketteter Bausteine:
   erst alle neuen platzieren, dann die Verdrahtung komplett neu aufbauen.
4. **Erfolg immer an den Daten prüfen, nie an der Rückmeldung.** `get_component_output` zeigt,
   was wirklich fließt; leere Liste = der Draht wirkt nicht. Nach jedem Bauschritt `get_errors`.
5. **Rhino-Neustart ist nur nach Austausch der .gha nötig** (net48 entlädt keine Assemblies).
   Normales Bauen braucht keinen. Nach einem .gha-Build: bauen, in den Libraries-Ordner kopieren,
   den Nutzer um Neustart bitten — und mehrere .gha-Änderungen zu einem Neustart bündeln.

## Leinwand aufräumen

```bash
python3 11_Robotics_Operation_and_Programming/02_Praxis/grasshopper-mcp/tools/gh_layout.py --dry-run
python3 11_Robotics_Operation_and_Programming/02_Praxis/grasshopper-mcp/tools/gh_layout.py
```

Spalten nach Datenfluss, Zeilen nach Schwerpunkt der Eingänge, Gruppenmitglieder bleiben
beieinander. `--panels` passt nur die Panelgrößen an (RAPID-Panels groß, Wertepanels klein).
Gruppen überleben das Verschieben, weil ihre Mitgliedschaft an IDs hängt, nicht an Positionen.

## Versionierte Checkpoints

**Vor jedem größeren Umbau einen Checkpoint setzen** — dann ist jeder Fehlgriff eine
Kommandozeile weit vom Rückweg entfernt. Checkpoints sind normale Git-Commits der .gh-Datei.

```bash
python3 .../grasshopper-mcp/tools/gh_checkpoint.py save "Papier verdrahtet"
python3 .../grasshopper-mcp/tools/gh_checkpoint.py list
python3 .../grasshopper-mcp/tools/gh_checkpoint.py restore <commit>
```

`save` speichert das laufende Dokument, committet es und schreibt Bausteinzahl sowie alle
offenen Meldungen in die Commit-Nachricht — der Verlauf zeigt also, wann die Leinwand sauber
war. `restore` holt die Datei zurück und lädt sie direkt in den Editor.

Wichtig: **Verschieben und Größenänderungen erzeugen keinen Rückgängig-Eintrag in
Grasshopper.** Vor `gh_layout.py` und vor jedem Ersetzen verketteter Bausteine daher immer
erst einen Checkpoint setzen.

## Robot Components

Reiter „Robot Components ABB", v3.2.1. GUIDs aus dem Quellcode auf GitHub, Tag `3.2.1` (ohne v),
`ComponentGuid`-Property der jeweiligen .cs — oder bequemer per `search_components`.

Kette im Kursprojekt: Kurve → Divide → Ebenen → Flip Plane X → **Orient ins Work-Object-System**
→ Robot Target → Move → Merge → **Flatten Tree** → Path Generator (Slider 0–1) und RAPID Generator.

Zwei Stolpersteine, die im Kurs Lerninhalt sind:
- **Divide Curve legt Punkte in Pfad {0;0}.** Ohne Flatten hinter dem Merge entstehen zwei Äste
  und damit zwei RAPID-Module.
- **RC liest Zielebenen als bereits im Work-Object-System liegend.** Weltkoordinaten plus Work
  Object ergibt doppelten Versatz. Orient-Baustein (Source = Objektebene, Target = WorldXY)
  rechnet um.
