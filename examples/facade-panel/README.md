# Example: a perforated facade panel

A panel with a grid of holes whose diameters follow an attractor point. Vanilla Grasshopper
only — no plugins, nothing to install. This is the example to read first: it is short enough to
follow end to end, and every claim in it was measured rather than assumed.

The brief given to the agent was the outcome, not the components:

> a rectangular panel, 2000 x 1200 mm · a regular grid of holes, count driven by sliders ·
> an attractor point on two sliders · hole diameter following the distance to the attractor,
> between 4 and 30 mm · the holes cut as real openings, so the result is visible in the viewport

Result: 28 components in five named groups, built in about nine minutes.

Open [`facade-panel.gh`](facade-panel.gh) to see the finished definition. Two screen recordings
of the actual sessions, unedited apart from being sped up:

| | |
|---|---|
| [`build.mp4`](build.mp4) · 82 s | From an empty canvas to the verified panel |
| [`modify.mp4`](modify.mp4) · 65 s | Recolour, rotate 90°, annotate — and the two limitations below |

## What makes it worth reading

Not that it worked. That the agent knew it worked, and knew *why*, at each step.

**It checked the cut instead of trusting it.** A boolean operation reporting success proves
nothing about whether material was removed:

> Face area 2 331 300 mm² measured vs 2 331 272.8 expected — 68 700 mm² of material actually
> removed, delta 27 mm² is the bridge's 6-digit output rounding. Holes are real.

**It verified a rotation by its result, not by its input.** Feeding π/2 into a Rotate component
is not evidence that anything rotated:

> Exact match {1002.98, −25.5, 792.845} = (x, −z, y), volume unchanged — a true +90° about
> world X.

**It noticed a human had been editing.** Between two sessions the sliders had been dragged by
hand. The numbers no longer matched what the agent remembered, and instead of "fixing" them it
worked out what had happened:

> Nothing is broken — the sliders have been moved by hand. Panel height 1580 (not 1200),
> Holes Y 8 (not 12), thickness 51 (not 30). The geometry matches those values exactly:
> centroid z = 25.5 = 51/2, and 2000×1580×51 minus 2.08e6 of holes = the measured 1.5908e8.
> I'll leave your slider positions alone.

This is the part that is hard to get without measurement. A generating-only agent has no way to
tell "my code is wrong" from "the human changed something", so it silently overwrites the
human's work.

## Two limitations it found, both real

**The bridge cannot write Scribble text.** Not a guess — a measurement:

> Scribble box stays 182.363 × 28.201 for `"1"` and for `"a much longer caption"` — identical
> to a fresh one. A scribble resizes to its text, so `set_nickname` is not reaching it.

Panels are used for the on-canvas annotations instead.

**`gh_layout.py` ignores group cohesion.** The full layout pass optimises per component. Group
rectangles are drawn around whatever their members happen to occupy, so they end up stacked on
top of each other even though no two components overlap:

| | before | after |
|---|---|---|
| group rectangle vs group rectangle | 6 overlaps | 0 |
| components inside a foreign group's rectangle | 27 | 0 |
| component vs component (`--check`) | 0 | 0 |

Note the third row: `--check` reported a clean canvas throughout, because it compares component
boxes and never looks at the group rectangles drawn around them. The canvas was visibly a mess
and the measurement said it was fine — a reminder that a check is only as good as what it
measures.

`block_layout.py` in this folder is the fix: it lays out **one block per group** — members
ordered by data-flow depth inside the block, blocks placed as units, annotation panel as the
block header, ungrouped strays parked clear. Final state: 43 objects, 38 wires, 5 groups,
0 overlaps, 0 errors.

It is deliberately not in `tools/`. The block arrangement at the end (`ORDER[:3]` stacked,
the rest chained) is specific to this definition's five groups. Read it as a pattern, not a
utility — about 80 lines, and the useful half is the idea that a group is the unit you place.

## Running it

```bash
python3 block_layout.py    # needs tools/gh.py on the path and a canvas with named groups
```
