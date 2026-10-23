---
name: pcb-placement
description: >
  First-pass placement of a KiCad 10 board with KiCadRoutingTools, then render,
  look, and clean up in pcbnew through computer use where it is available. Gets
  the footprints onto the board from the schematic, turns the mechanical facts
  and the house layout rules into a floorplan intent, runs KRT's placer, grades
  the result, and fixes what the grade and the renders find. Load it for "place
  the board", "do the placement", "place the parts", "first pass placement",
  "floorplan this board", "get the footprints onto the PCB", "update PCB from
  schematic", "autoplace", "where should the parts go", or when a schematic is
  done and the board has no placement yet. Stops before routing (pcb-routing)
  and does not replace layout-review.
---

# PCB placement

Placement decides most of what routing can achieve, and it is the cheapest
point to fix a mistake. So the first pass is done in code, where it is fast and
repeatable, and it is judged twice: by KRT's graders, which measure it, and by
looking at renders, which catch what the graders can't. KRT's own research says
it plainly: from-scratch autoplacement fails for lack of *constraint capture*,
not optimisation power. Most of this skill is getting the constraints that live
in the enclosure, the datasheets and the human's head into a form the placer
can read.

## Contract

Reads:  `<name>.kicad_sch` + netlist; `<name>.kicad_pcb` if it exists; the
        mechanical facts from the human; `datasheets/<MPN>/capture.json`
        (layout guidelines); `project.yaml`; `ee-layout-rules`
Writes: the placed `<name>.kicad_pcb` (only after the human agrees to replace
        theirs; otherwise alongside it as `<name>.placed.kicad_pcb`);
        `<name>.design-brief.json` and `floorplan.json` beside the board;
        `review/placement/` (renders, scores, the per-pass verdicts)
Stops if: `board_rules.py check` fails and the human hasn't accepted the
        difference; or there is no board outline and the human hasn't given one. KRT will
        not invent an outline, and neither should you, because the outline
        belongs to the enclosure, not the layout. It also stops if the
        schematic has unresolved ERC or pin-check failures, since placing a
        wrong netlist wastes the placement.

## Before you start

1. **Bring KiCadRoutingTools up to date.** It changes daily; 241 commits landed
   in the week before this skill was written.
   ```bash
   KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
   cd ~/git/KiCadRoutingTools          # clone github.com/drandyhaas/KiCadRoutingTools if absent
   git status --porcelain              # dirty? stop and tell the human; never stash their work
   git pull --ff-only && "$KPY" build_router.py
   git log -1 --format='%h %ci'        # record this in the report
   ```
   **Run KRT with KiCad's bundled Python (`$KPY`)**, not the system one. On
   this Mac the system `python3` has none of KRT's dependencies (numpy, scipy,
   shapely, Pillow). KiCad's Python has them, and it also has `pcbnew`.
   Everywhere below and in KRT's docs, read `python3` as `$KPY`.
2. **Read KRT's `.claude/skills/pcb-free-agent/SKILL.md` fresh, every run.** It
   is the maintained playbook: toolbox, DONE conditions and traps measured in
   real runs. This skill deliberately doesn't copy it, because a copy would be
   stale within a week. Everything below is what KRT can't know on its own.
3. Load `ee-layout-rules`, then read `ee-layout-rules/rules/layout.md`: L-01…L-05
   (setup) and L-10…L-19 (placement) are the rules this skill places to.

## 0. Set up the board's rules before anything is placed

Do L-01…L-04 before anything moves. The values are in `ee-layout-rules/rules/drc.json` (floors, net
classes and predefined widths and vias, per profile, each with its reason), and
`board_rules.py` puts them on the board.

```bash
S=<ee-skills>/skills/ee-layout-rules/scripts/board_rules.py
# new board: start from a template (rigid_2L / rigid_4L / flex_2L / flex_4L).
# Copy the folder and rename the three files to the project name, or use KiCad's
# "New Project from Template" if the templates are installed
cp -r <ee-skills>/skills/ee-layout-rules/assets/kicad-templates/rigid_4L <project>
# existing board: apply, then read back. The project must be closed in KiCad
$KPY $S apply <name>.kicad_pro --profile rigid --dry-run   # read the changes first
$KPY $S apply <name>.kicad_pro --profile rigid
$KPY $S check <name>.kicad_pcb --profile rigid             # KiCad reads it back; exit 1 on mismatch
```

- **Pick the profile by L-02.**
- **`apply` keeps a floor the board already has if it's stricter**, and says
  so. It warns when a predefined via or width sits below the floor. Resolve
  every warning: either drop the entry, or allow it with a scoped `.kicad_dru`
  rule where the geometry needs it.
- **Assign the rails** (L-03). `pcb-routing` sizes them later.
- **Put in the relaxations you already know you'll need** (L-04), and probe
  them.
- On an existing board, run `kicad-cli pcb drc` after `apply` and read what the
  new floors catch before placing anything. Tightened rules find real problems
  in old copper, such as via holes closer to copper than the fab's minimum.

## 1. Get the footprints onto the board

If the board has no footprints yet, or is behind the schematic:

- **In code (preferred):** `$KPY` can `import pcbnew` without the GUI.
  Load each footprint from the library named in its symbol's `Footprint` field,
  resolved through the project's `fp-lib-table` and `$EE_LIB`. Set the
  reference, value and fields from the netlist, and assign each pad's net. Then
  save.
- **Or Update PCB from Schematic** (F8 in pcbnew), through computer use or by
  the human.

Either way, verify it. `kicad-cli pcb drc --schematic-parity --format json`
must report no parity errors: no missing or extra footprints, and no pad on the
wrong net. A board that disagrees with its schematic isn't worth placing.

## 2. The facts the board can't know

Ask the human for the mechanical facts (L-05), and record each one with its
source.

Write them to `<name>.design-brief.json` (format: KRT `docs/design-brief.md`)
and compile the intent with
`$KPY py_tools/check_floorplan.py <board> --emit-intent floorplan.json --declare-classes`.
Never emit the intent from a badly placed board. It records the damage as the
spec, and it guesses connector edges from wherever the parts happen to sit.
Anything you had to assume is marked as assumed, and it goes in the report
(L-05).

A board with an inter-board connector (cable, flex, B2B, mezzanine) also needs
its pin-to-pin map and mis-install grades from `paper-doll` before layout.

Then add the placement rules to the intent, as far as KRT can express them:
L-10 (decoupling-pin distance), L-11 (hot loops, from the capture's layout
guidelines: switching regulators are placed as cells from the `dcdc-layout`
skill before seeding, and are fixed for the placer), L-12 (zones), L-14 (connectors), and L-15 (test points and debug
header). Lock the mechanically fixed parts (`place_pose` set, then lock) before
seeding, and the fiducials with them (L-17): two in diagonally opposite
corners and the third in another corner, each as near the edge as the edge
rail, the L-38 band and its mask clearance allow. A placer left to put them
anywhere puts them wherever there is room, and that is usually the middle.

## 3. First pass — KRT

Follow KRT's `pcb-free-agent` skill in `place` mode, with this board and this
intent. Use its playbook, work directory (`wk/<run>/` in the KRT checkout) and
stop rules. From a session launched inside the checkout it is the slash command
`/pcb-free-agent place <abs board> <abs floorplan.json>`. From anywhere else,
read its SKILL.md (done above) and follow it.

Or drive the same tools yourself (`place_seed.py --intent`, then refinement)
when you need a narrower step. Its toolbox table says which tool does what.
Copy boards with `py_router/copy_board.py`, never `cp`, because the
`.kicad_pro` next to a board carries its DRC floor. If a careful hand
placement already measures clean, don't polish it; KRT measured the quench
making one worse.

**Done for this pass** is KRT's `place` DONE: `check_assembly` buildable,
`check_floorplan --intent` with zero errors, nothing off the outline, and
mechanical facts met.

## 4. Look at it

The numbers are the verdict, and the pictures are how you find out what the
numbers missed.

```bash
$KPY py_tools/render_placement.py <board> --per-side --labels --ratsnest -o review/placement/
kicad-cli pcb render --side top    --quality high -w 2400 -h 1600 -o review/placement/top.png <board>
kicad-cli pcb render --side bottom --quality high -w 2400 -h 1600 -o review/placement/bottom.png <board>
```

Open every image, and render every layer on its own as well (each copper
layer, Fab and silk), not only the composites (L-46): an illegible Fab layer or
a title block under a part is a placement finding. Zoom into a block with
`--zoom-group` when the whole board is too small to read refdes. Write a verdict for each block, the same way
schematic-capture does for each sheet. It is either **looks good**, or issues
naming the L-rule, refdes, location in board mm, and what is wrong. Judge
against L-10…L-19. For L-16, `board_context.py` flags `CROSSED` pin-order
pairs.

Keep every part's pads out of the edge band (L-38, `drc.json`
`edge_ring.margin_mm`, 1.0 mm rigid) unless the part belongs at the edge:
connectors, overhanging modules and headers, whose courtyards touch the
outline. The band is for the GND ring. A resistor placed 0.5 mm from the edge
leaves a hole in the ring that routing can't close.

A clear pad isn't enough where a bundle has to pass between the part and the
edge. Leave room for the band **plus** the lanes: pad-to-edge ≥
`edge_ring.margin_mm` + n × (track width + clearance), where n is the number
of ratsnest lines that must cross between the pad and the edge. Measured on
a 6x8 array board (2026-09-29): C149 and C150 (10 µF on 3V3_LED) sat 0.99 mm from the
edge with two SDA lanes squeezed between them and the edge at minimum
spacing. The human moved both about 0.5 mm inboard to pull the lanes out of
the band.

Leave room for a via beside every power and ground pad (L-39): each one gets
its own via to its plane, as close as clearance allows (0.5 mm ring to pad
edge, 1.5 mm of track at most), and a high-current pad gets room for
`ceil(I / pin_vias.via_amps)` of them (three 0.6/0.3 vias at 1.5 A). It matters most at the
decoupling caps. Two caps butted pad to pad, or a cap tucked under a
fine-pitch part, can leave no room for the via.

Trace the ratsnest's main bundles, from connector to MCU and from sensor array
to AFEs, and check that nothing drilled or padded sits in their path: mounting
holes, cover or fixture holes, test points, fiducials. Anything in a corridor
makes every lane in the bundle wrap around it (L-25). Move it to the corridor's
edge now. Routing can't fix it later. Measured on a 6x8 sensor-array main board (2026-09-28): a cover
hole placed at the keepout corner, in the middle of the array-to-AFE fan,
bent about 20 lanes into a staircase around it.

Check the fiducials (L-17) on every assembled side: two in diagonally
opposite corners, a third in another corner, none near the middle. Print
each one's distance to its nearest outline corner and the spread of the set
against the board diagonal; layout-review grades it as LAY-53. If a part
sits where a fiducial belongs, move the part. The 2026-10-04 review of the
four encoder test boards found fiducials placed near the middle, where they
give the assembler's camera almost no baseline for rotation and scale.

Then get a fresh opinion: spawn a subagent to run `layout-review` at
`stage: placement` against this board. The session that placed it reads what
it meant rather than what is there.

## 5. Clean up

### 5a. Small parts to their pins (L-61)

A zone placer leaves small parts wherever they fit. Check the decaps, pull-ups, bias and series parts
around each IC: each should sit at the pin it belongs to. Where they don't, run the anchor-pin placer on
that area. It works on a copy, and keeps ICs, connectors, test points and locked parts fixed:

```bash
KV=<KiCadRoutingTools>/.kvenv/bin/python; S=<ee-skills>/skills/pcb-placement/scripts; REG="x0 y0 x1 y1"
$KV $S/anchor_place.py select   board.kicad_pcb --sheets /sheetA/ /sheetB/ --region $REG > movable.txt
$KV $S/anchor_place.py classify board.kicad_pcb --movable movable.txt --region $REG   # read it: owners right?
$KV $S/anchor_place.py rip      board.kicad_pcb base.kicad_pcb --movable movable.txt --region $REG
$KV $S/anchor_place.py place    base.kicad_pcb placed.kicad_pcb --movable movable.txt --region $REG \
      --plan plan.csv --edits moves.txt [--floorplan intent.json] [--hv REGEX] [--power-nets GLOB ...]
$KV $S/anchor_place.py measure  placed.kicad_pcb --movable movable.txt --region $REG
$KV $S/anchor_render.py placed.kicad_pcb after.png --movable movable.txt --region $REG --airwires --no-copper --plan plan.csv
```

- `rip` removes the routed copper of the movable parts' nets inside the box, and their pin taps. It writes
  that removal as DELETE lines, and `place` writes the moves and pin vias in the same edit format.
- Read the `classify` table before placing. A wrong owner (a decap given to a connector, a pull-up whose
  pin sits outside the box) is cheaper to fix there than on the board.
- Judge the result on the nets local to the box: ratsnest, routed vias and opens after a re-route,
  courtyard overlaps, and rail pads with their own via. Report those with before/after renders.


**In code** when the fix is a known move: `py_placer/place_pose.py` (set a pose,
rotate, lock), or a scoped `place_seed --repair` / `--reseat` on just the refs
at fault. KRT notes that freeing two parts cleared both blocking pairs in 63 s,
where whole-board sweeps ran over ten minutes.

**Computer use in pcbnew** when it's available and the fix needs an eye, like
tidying a cluster or nudging parts against the ratsnest. Open with
`open -a KiCad <name>.kicad_pro`, then the PCB editor. Move with `M`, rotate
with `R`, flip with `F`. Keep the grid sensible for the part pitch. Save with
⌘S and **close pcbnew before any script reads or writes the board again**,
because KiCad keeps the board in memory and overwrites a script's edit on its
next save.

After any change, in code or GUI, re-run the grade (`check_assembly`,
`check_floorplan --intent`, copper-free `check_drc`) and re-render. A GUI move
carries no evidence of its own.

**The placement gate** *(review 2026-10-21)*, numbers that must be in the
handoff and that `layout-review` grades again:

- `courtyards_overlap` count from DRC, with each overlapping pair either
  justified (a dense cell the spec names, pad-to-pad still ≥ 0.2 mm) or fixed.
- The pad-to-pad spacing report: every pair under 0.2 mm, by refdes.
- **Repeated cells are identical and not mirrored.** A board with an array of
  the same sub-circuit (an AFE and its caps, a channel, a driver) places every
  copy with the same offsets and rotations unless the spec says why one
  differs. The sensor array's mirrored end cell put two caps pad to pad; identical
  cells cannot.
- **A free band beside every BGA or WLCSP edge ball** for its dogbone via:
  via pad plus two clearances (0.45 mm with a 0.25 mm via at 0.1 mm clearance,
  0.5 mm with one grid step of slack), measured from the ball pad's edge to
  the next copper, on each side the outer ring escapes to (L-47). Without it
  the router puts the via over the ball.
- **A BGA, WLCSP or repeated cell array goes to `hdi-breakout` next**, before
  pcb-routing: its escape and lane budget decide the layer count, and a
  shortfall found here costs a question, not a day of routing.
- Where the GND plane will be tapped: one legal spot per cell for a shared
  buried tap on an HDI stack (L-43), clear of the fanout vias of the other
  side. If no spot exists at placement, none will exist at routing.

**Budget: up to 2 cleanup rounds**, each one fix → re-grade → re-render. Stop
sooner if a round changes nothing, or if what is left is a judgement for the
human. Then hand back what remains, with refdes and reason. Don't start a third
round, and don't re-run the whole-board placer to chase a better score.

## Handoff

- The board, and whether it replaced the human's or sits beside it.
- The DONE table measured (buildable, floorplan errors and warnings, hpwl,
  crossings), with the KRT commit it was produced with.
- Per-block verdicts from the final look, the renders, and the `layout-review`
  findings with what was fixed.
- Every assumed mechanical fact, marked assumed.
- The fiducial positions per side, two or four, with each one's corner
  distance (L-17), and every L-17 exception (none on a panel-rail board, dense
  cells) with its open-item id.
- The placement gate numbers above, and the title block's position (L-46).
- **Layer capacity** from `ee-layout-rules/scripts/layer_capacity.py` on the
  placed board: the worst cut, and whether the layer count leaves room for a
  GND plane (L-37). A placement that needs every layer for signal is cheaper to
  fix now, by spreading the parts or adding layers, than after routing.
- Next: `pcb-routing`.
