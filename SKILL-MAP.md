# ee-skills — skill map

A fresh read of every file under `skills/`, reviewed on 2026-09-28. It covers what each
skill is for, the files it uses, how it runs, and where it is bounded. §3 records
what was tightened and what is still open.

---

## 1. The shape of the set

```
                       ee-schematic-rules  (loaded by the schematic stage)
                                │
  datasheet-extraction ─────────┼──────────── symbol-footprint
  (PDF → capture.json)          │             (capture → $EE_LIB part)
          │                     │                    │
          ▼                     ▼                    ▼
  schematic-capture ──► schematic-review        (fresh session)
          │
          ▼             ee-layout-rules  (loaded by the board stage)
  pcb-placement ──► layout-review @placement    (subagent)
          │
          ▼
  hdi-breakout     (BGA, WLCSP or a cell array: escape + lane budget, locked fanout)
          │
          ▼
  pcb-routing ───► layout-review @routed / @final
          │
          ▼
      board-doc
```

Six kinds:

| Kind | Skills | Writes |
|---|---|---|
| Standard (data) | `ee-schematic-rules`, `ee-layout-rules` | nothing, except `board_rules.py apply` on a project |
| Acquire / extract | `datasheet-extraction`, `symbol-footprint` | captures, library parts |
| Author (generative loop) | `schematic-capture`, `pcb-placement`, `pcb-routing` | KiCad files |
| Judge (read-only) | `schematic-review`, `layout-review` | `findings/*.yaml`, `open_items.yaml` |
| Publish | `board-doc` | `docs/notion/<board>.md` + assets |
| Joint check | `paper-doll` | pin-to-pin map and mis-install grading for every board-to-board joint (cable, flex, B2B, mezzanine), confirmed in 3D CAD |

Each skill starts from an artifact that already exists, so none of them requires the one
before it. The arrows show the usual order, not a hard dependency.

### Shared state in a project directory

| Path | Written by | Read by |
|---|---|---|
| `datasheets/<MPN>/capture.json` (+ `crops/`, `figures/`, `curves/`) | datasheet-extraction | symbol-footprint, schematic-capture, schematic-review, pcb-placement, pcb-routing, layout-review |
| `project.yaml` (the four house asks) | schematic-capture | schematic-review, pcb-placement, layout-review (all default if absent) |
| `review/…` (netlists, ERC/DRC JSON, renders) | every author and judge | the same skill, on re-run |
| `findings/schematic-<date>.yaml`, `findings/layout-<date>.yaml` | the two reviews | board-doc (errata proposals) |
| `open_items.yaml` (append-only; shape in `board-doc/references/findings.md`) | reviews, defaults taken from the project asks | board-doc |
| `$EE_LIB` (`~/git/kicad-library`) | symbol-footprint | schematic-capture, pcb-placement |
| `~/git/KiCadRoutingTools` (KRT) + `$KPY` (KiCad's Python) | external, pulled each run | pcb-placement, pcb-routing, layout-review §4a |

---

## 2. Per skill

### ee-schematic-rules — the schematic-stage standard

- **Purpose:** the design rules for choosing parts and drawing the schematic. It is
  loaded at the start of schematic work and stays loaded.
- **Files:**
  - `SKILL.md`: naming, every net named, full part descriptors, passives,
    derating, design-for-debug.
  - `references/asks.yaml`: the four project questions (0201, test-point form, zero-ohm
    scope, debug header), each with a default. The board stage reads the answers from
    `project.yaml`, and these defaults where it is missing.
  - `rules/schematic.md`: the D-rules (D-01…D-61), tagged ratified, observed
    or draft (D-45 value format, D-46 part fields, from the 2026-10-04
    review; D-25 local labels, D-47 symbol height, D-48 NOSTUFF options from
    the 2026-10-21 motor-driver review, which also ratified D-14 MCU split by
    function), plus open items O-1…O-3. It is the only copy; skills cite IDs.
- **How it works:** no steps. It is rules with reasons ("the reason matters more than
  the rule"). A rule marked *(draft)* is followed, but the agent has to say so when it
  drives a decision.
- **Bounds:** a silent default is forbidden. An unanswered ask is written as
  `source: default` and logged. An MPN from memory is a lead, never a part.

### ee-layout-rules — the board-stage standard

- **Purpose:** the rules for setting up, placing and routing a board, and every number
  KiCad enforces. It is loaded at the start of board work and stays loaded.
- **Files** (each rule file is the only copy; skills cite IDs):
  - `rules/layout.md`: the L-rules. L-01…05 setup, L-10…19 placement,
    L-20…37 routing, L-40…42 flex.
  - `rules/drc.json`: every number KiCad enforces, per profile, each with a
    `_why`. `scripts/board_rules.py` applies it (`apply`), reads it back (`check`)
    and builds the four templates (`template`). `scripts/check_copper.py`
    grades the copper hygiene DRC and KRT's `check_weird` miss (L-20, L-25, L-26,
    L-32…35) for pcb-routing and layout-review. `scripts/layer_capacity.py`
    measures how many signal layers a board needs and whether its plane survives
    the vias (L-37), for placement, routing and review.
  - `references/fab-and-layout-defaults.md`: fab research only (JLC/PCBWay
    capabilities, when HDI is needed). No house values.
  - `assets/kicad-templates/{rigid,flex}_{2L,4L}/`: starter projects.
- **How it works:** rules with reasons, like `ee-schematic-rules`. Net names come from
  the schematic and are not renamed at layout.
- **Bounds:** a number lives only in `drc.json`. An exception is a scoped `.kicad_dru`
  rule with its reason and a probe (L-04), never a global floor change.

### Shared: findings and open items

`board-doc/references/findings.md` holds the shape of `findings/*.yaml` and
`open_items.yaml`, and the rule for severity while maturity is undefined (grade by
consequence, state the assumption). Both reviews write to it and board-doc reads it.

### datasheet-extraction — PDF → cited capture

- **Purpose:** one job with provenance. Every value carries a page and a bbox.
- **Files:**
  - `scripts/capture.py`: Docling → `capture.json` + `capture.md`; `--crops` renders the
    formula PNGs.
  - `scripts/figures.py` → `digitize.py` → `verify.py`: figure regions, then curve CSVs,
    then an overlay to check them.
  - `references/vendor-notes.md`: what varies by vendor, and known limits.
- **How it works:**
  1. Capture, with the revision read off the PDF.
  2. Cache check: if the sha256 matches, stop.
  3. Digitize only the curves a number depends on, and always look at the overlay.
  4. Answer from `tables`/`texts`, citing the page.
- **Bounds:** stops if there is no PDF, because a capture from memory is worse than
  none. No parallel "extracted values" file. Equations come from the crops, never from
  recall. Gaps are named.
- **Setup:** a venv with docling, pymupdf, numpy, matplotlib and pillow.

### symbol-footprint — part into `$EE_LIB`

- **Purpose:** a verified symbol, footprint and 3D model.
- **Files:** `scripts/ipc7351.py` (land pattern + paste windows),
  `references/kicad10-sym-mod-format.md` (grammar, worked SON-8, an inline pin/pad
  extractor). Needs `easyeda2kicad`, `kicad-cli`, and a capture from
  datasheet-extraction.
- **How it works:** a three-step ladder, going only as far down as needed:
  1. Look in the library (house, vendor, upstream).
  2. Convert with EasyEDA in a scratch dir.
  3. Generate from the datasheet.

  Then verify every time: pins as string sets (EP = N+1, repeated names, BGA naming,
  the package column), pin electrical type, pad set = pin set, dimensions ±0.1 mm,
  pin 1, thermal-pad paste windows, silk. Look at the SVGs. Check the 3D model.
  Write a `LICENSES.md` entry.
- **Bounds:** hard stop if the symbol and footprint pin sets disagree. Pins are never
  read from a PDF by eye. A library hit still gets re-verified. Nothing is merged
  into the shared library until the human has seen the diff and said yes.

### schematic-capture — author the `.kicad_sch`

- **Purpose:** draw in code, render, look, fix. Mode A is a new board from a brief;
  Mode B is a redraw with the netlist frozen.
- **Files:** `references/kicad10-sch-format.md` (s-expr grammar, pin transform, field
  angles, UUIDs, `.kicad_pro`, kicad-cli); `scripts/jlc.py` (live JLC/LCSC
  search, code lookup, and the D-45/D-46 parts check over the netlist, adapted
  from the encoder project's `tools/jlc.py`). Uses the house drawing rules and
  `schematic-review/scripts/pincheck.py` (cross-skill). Writes `sch_build/` (the emitter
  script), `pinmap.md`, `review/…`, and `project.yaml`.
- **How it works:**
  1. Load the rules and ask the four questions.
  2. Get symbols and captures.
  3. Mode A: play back the sheet plan, get `pinmap.md` approved, derive values in
     Python (house value format), name every net, map every part to MPN,
     Manufacturer and LCSC from a live lookup.
  4. Emit from a script.
  5. Connectivity gate: ERC, pincheck, no `Net-(`, and either an empty netlist diff
     (Mode B) or a walk of every stated connection (Mode A). Parts gate:
     `jlc.py check` with zero FAIL.
  6. Render every sheet and write a per-sheet verdict against the D-rules.
  7. Fix in code, or in the GUI via computer use, then re-check.
  8. Hand off to schematic-review in a fresh session.
- **Bounds:** stops when a connection has no source (brief, capture or house rule), and
  asks instead of guessing. There are two human gates, the sheet list and the pin map.
  At most 2 fix rounds after the first render, then it hands back what's left.

### schematic-review — judge a schematic (read-only)

- **Files:** `scripts/pincheck.py` (netlist pins vs the datasheet pin table, resolving
  the package column from the orderable table), `scripts/netlist.py` (netlist loader
  plus the decoupling check, the base for the other electrical checks),
  `references/rubric.md` (sections A–G). E-7/E-8 run
  `schematic-capture/scripts/jlc.py check` live (cross-skill).
- **How it works:**
  1. Fresh-context check.
  2. Hash the files.
  3. Export the netlist and BOM.
  4. Extract any missing captures.
  5. ERC, with every item recorded as a finding; open errors lead the playback.
  6. Pincheck.
  7. Electrical joins in Python.
  8. Render and look.
  9. Walk the rubric, with G (bring-up proposals, 2–3 max) last.
  10. Play back worst-first in sections, waiting between them.
  11. Append to open items.
- **Bounds:** the only stop is that kicad-cli can't open the file. Everything else
  becomes `unanswerable`, which never counts as a pass. Findings are graded by
  consequence, and section A (pins) is weighted heaviest.

### pcb-placement — author placement

- **Files:** none of its own. It places to `ee-layout-rules/rules/layout.md`
  (L-01…19) and sets up with `rules/drc.json` via `scripts/board_rules.py`. It
  also uses the templates, and KRT (`pcb-free-agent` in place mode,
  `check_floorplan`, `place_seed`, `place_pose`, `render_placement`, `board_context`).
  Writes `<name>.design-brief.json`, `floorplan.json` and `review/placement/`.
- **How it works:**
  1. Update KRT (stop if the checkout is dirty) and read its playbook fresh.
  2. §0: set the board rules first (`apply` → `check`).
  3. Get the footprints on and pass schematic parity.
  4. Collect mechanical facts from the human and compile them into the intent, adding
     house and capture constraints.
  5. First pass with KRT, until it reaches KRT's place DONE.
  6. Render and write per-block verdicts.
  7. Spawn a layout-review subagent at `placement`.
  8. Clean up in code or the GUI, then re-grade.
- **Bounds:** stops on a failing board-rules check, no outline, or open ERC or pin
  failures. It won't replace the human's board without agreement. It never invents an
  outline. At most 2 cleanup rounds, and it doesn't re-run the whole-board placer to
  chase a score.

### pcb-routing — author copper

- **Files:** `scripts/copper_render.py` (composited copper render via pcbnew). It
  routes to `ee-layout-rules/rules/layout.md` (L-20…37, L-40…42 on flex). It uses
  KRT (`pcb-free-agent` route mode, `analyze-power-nets`, `identify-diff-pairs`,
  `find-high-speed-nets`, `recommend-stackup`, `recommend-plane-mappings`,
  `diagnose-routing-failures`, and the route and check scripts).
- **How it works:**
  1. Update KRT and check the board rules.
  2. Layer plan first: `layer_capacity.py` sets how many signal layers the board
     needs; at least one GND plane on ≥ 4 layers; layer jobs and directions.
  3. Write a routing spec per item, using the captures instead of KRT's WebSearch, and
     put it into net classes.
  4. First pass in L-36 order: planes and power, fine-pitch breakout, critical nets,
     everything else with the plane priced high; `--no-fix-drc-settings`,
     `--keep-input-copper` and logs teed. Congestion the capacity check confirms
     ends in "needs more layers", not in routing over the plane.
  5. Verify with connectivity, DRC with refill, a score, `check_weird` and
     `check_copper`.
  6. Render per region and layer, with verdicts.
  7. Spawn a layout-review subagent at `routed`.
  8. Clean up.
- **Bounds:** the best-bounded skill in the set. It has an explicit outcome table (done,
  good enough = ≥90% routed with clean copper, out of budget, needs more layers), a budget of 1 first pass, ≤3 re-route attempts, ≤2
  cleanup rounds and ~60 minutes, and it stops early when an attempt doesn't improve
  anything. It keeps `best.kicad_pcb` and asks one question at the end. Hard rules are
  never traded for a lower count.

### layout-review — judge a board (read-only)

- **Files:** `references/rubric.md` (LAY-01…54, staged P+/R+/F; each line names the
  L-rule or `drc.json` it grades),
  `references/kicad10-dru-cookbook.md`. Also KRT `review-routed-board` (§4a).
- **How it works:**
  1. Preconditions: zones filled, and board = schematic.
  2. Triage DRC by root cause.
  3. Audit the `.kicad_dru` by probing on a scratch copy.
  4. Geometric checks by script.
  5. KRT checkers.
  6. Render and look (vision proposes, a script confirms).
  7. Walk the rubric by stage and play back worst-first.
- **Bounds:** stops on missing or unparseable files or a failed precondition. If KRT
  isn't installed, §4a's lines are `unanswerable` rather than a reason to install it.
  It never probes the working copy and never offers to fix. Unencoded intent is a finding against
  the DRU, not against the person who routed it.

### board-doc — the board's page

- **Files:** `scripts/render.py`, `pinout.py`, `facts.py`, `blocks.py`, and `kx.py`
  (vendored parser); `references/template.md` (seven sections).
- **How it works:**
  1. Get the revision number and status.
  2. Generate the assets.
  3. Stop if `facts.py` reports DIRTY.
  4. Write the four human sections.
  5. Assemble the page and list any unfilled placeholders.
- **Bounds:** read-only git; never writes KiCad files. The freeze rule stops assets from
  being regenerated past `routed`. The Mermaid seed must be edited, never shipped raw.
  It never invents a value.

---

## 3. Bounds and simplicity

Every skill has a contract (Reads / Writes / Stops if). The judges are read-only.
Every authoring loop now has a round cap: schematic and placement stop after 2 fix
rounds, and routing has its budget. Every write to something shared (the human's
board, the library) waits for the human to agree.

**Resolved in this pass**

| # | Issue | Fix |
|---|---|---|
| 1 | schematic-capture and pcb-placement loops had no cap | ≤2 fix rounds each, then hand back the remainder |
| 2 | Routing "good enough" was "≤30 unconnected **or** ≥90%" | ≥90% routed, and clean copper |
| 3 | schematic-review said "re-run ERC until empty" while read-only | every ERC item recorded as a finding; open errors lead the playback |
| 4 | Board-Setup clamp stated as fact, contradicted by a later probe | layout-review and the cookbook say to probe it, not assume it |
| 5 | LAY-06 cited IPC-2221 | now IPC-2152, matching the house rules |
| 6 | ee-house-rules referred to the removed architecture chain | replaced with the "an MPN from memory is a lead" rule, and sheet order now comes from the netlist or brief |
| 7 | `asks.yaml` `read_by` named the wrong skills | now lists the skills that actually read `project.yaml` |
| 8 | `_superseded/` and `interview-notes.md` shipped with the install | deleted (still in `git log`) |
| 9 | README pointed at a non-existent `approved.yaml` | gap removed; `$EE_LIB` is the approved set |
| 10 | board-doc description had `<board>` | reworded |
| 11 | symbol-footprint wrote straight into the shared library | shows the diff and waits for a yes |
| 12 | layout-review §4a assumed KRT was installed | skips it and marks those lines `unanswerable` |
| 13 | findings / open-items had no shape | a short YAML example in ee-house-rules |
| — | inline netlist parser in schematic-review | moved to `scripts/netlist.py` |
| — | drawing, layout and DRC rules restated across 5–6 files, with copies that disagreed | one file each in `ee-house-rules/rules/`; skills and rubrics cite IDs |
| — | `ee-house-rules` loaded ~290 lines of schematic-stage rules into every layout skill | split into `ee-schematic-rules` and `ee-layout-rules`; the findings shape moved to `board-doc/references/findings.md` (2026-09-29) |
| — | a KRT-routed 4-layer board came back with signal on every layer and no plane; nothing checked capacity or routing order | L-36 (order: planes and power, breakout, critical, rest, then add layers), L-37 (layer count from `layer_capacity.py`, ≥ 1 GND plane on ≥ 4 layers), plane priced high in KRT, LAY-47 (2026-09-29) |
| — | the org name was baked into the standard, templates and prose | removed; the set is generic. The house library is `$EE_LIB` with `house:` and `house_vendor:` nicknames; a board made against a library with other names needs its lib tables pointed at it (2026-10-22) |
| — | human review of the four encoder test boards (2026-10-04): every board used 0.3/0.15 vias, the house default, which none of them needed and which JLC charges extra for | L-32 rewritten *(draft)*: the 0.6/0.3 via (0.3 drill, no added cost) is the default and the Default and Power class via; 0.2 drill only where geometry forces it, 0.15 only for fine-pitch escape or via-in-pad, each named in the routing spec; 0.1 only on boards < 1 mm. `drc.json` `vias` reordered and annotated, floors unchanged so scoped small vias still pass; templates regenerated; `check_copper.py` `small-via` and LAY-54 grade it; pcb-routing's spec lists the places a smaller via is needed |
| — | same review: a 1.0 mm staggered stitching grid littered the boards with vias | L-43 and `drc.json` `stitch`: `area_pitch_mm` 2.0 with the 0.6/0.3 via, `area_pitch_max_mm` 2.5 for small slow boards, tighter only for a high-speed or RF return path stated in the routing spec; `stitch.py` notes a pitch outside that range; `check_copper.py` fallback follows (2026-10-04) |
| — | same review: fiducials sat near the middle of the boards | L-17 *(draft)*: two in diagonally opposite corners and a third in another, near the edge, parts moved to make room, locked before seeding; LAY-53 grades it, pcb-placement checks and reports it (2026-10-04) |
| — | same review: capacitor values written `1u`/`100n`, and parts not mapped to orderable JLC parts | D-45 *(draft)* value format (`100nF`, `1uF`, `2.2uH`, `4.7k`, `120R`, `0R`; ASCII `u`); D-46 *(draft)* `MPN`, `Manufacturer`, `LCSC` on every BOM symbol from a live lookup, consigned parts marked `CONSIGNED`; schematic-capture Mode A step 6 and a parts gate (`scripts/jlc.py`); schematic-review E-7/E-8 (2026-10-04) |
| — | two encoder boards (2026-10-04): a GND stitching via sat in J1.MP, the mounting tab of a JST GH, and wicked its solder; KiCad DRC, `check_copper.py` and `stitch.py` all passed it, only KRT's `VIA-IN-PASTE` caught it | L-30 *(draft)*: no via in an SMD pad or paste aperture, same net included, unless declared via-in-pad (`allow-via-in-pad:` in the routing spec, paste-window thermal pad, bare test pad); L-43 says the same for stitching. `check_copper.py` `via-in-pad` (fail in paste, warn on land copper only; `--allow-via-in-pad`); `stitch.py` keeps every candidate off SMD lands and paste apertures and counts `smd-pad` / `paste` skips; LAY-55; pcb-routing spec and defect table (2026-10-04) |
| — | human schematic review of a motor-driver board (2026-10-21): global labels on nets that never left the page (`BUCK12_SW`), symbols with pin names on top of each other (UCC27517A, LT6654), optional blocks drawn as fitted | D-25 *(draft)* local labels on the wire for on-sheet nets, globals only off-page; D-47 *(draft)* box symbols sized from pin-name text; D-48 *(draft)* optional blocks NOSTUFF with a fitted 0R bypass and a population note; D-14 *(ratified)* large MCU split into one boxed unit per peripheral group; schematic-capture code-drawing bullets for D-14/D-25/D-47; schematic-review A-8, D-6, F-5 (2026-10-21) |

**Still open**

- None of the new caps and gates has been through a test run yet.
- The 2026-10-04 rules (L-17 corners, L-32, L-43 pitch, D-45, D-46) are
  *(draft)* until signed off. JLC's published price note (re-read 2026-10-23)
  says a 0.2 mm drill with a pad ≥ 0.45 mm costs nothing extra, where the
  review says 0.2 adds cost; L-32 follows the review, so check a quote. `jlc.py` uses JLC's
  unpublished web endpoint and will break if JLC changes it.
- The Board-Setup clamp question needs one clean probe on 10.0.6 to settle it.
- Two items rescued from the cut still have no home: the power-tree arithmetic and the
  forgotten-blocks checklist (see README).

---

## 4. Changes made in this pass

**Generalised.** Development-board names and specific part numbers are gone from
everything under `skills/`. That includes the dev-board and project names and the
specific MPNs and example parts that came from them. Examples that used them now use a
generic part or no name at all. The measured-vendor table now lists part *type*
(LDO, I²C level translator, optical sensor) instead of MPN. The drawing rules' open items
were rewritten as general rules (O-1…O-3), and the board-specific compliance notes were
dropped. Vendor-level notes ("TI numbers its headings") stay, because they apply to any
part from that vendor. Personal names were removed from "not yet signed off".

**Bugs fixed.**
- `digitize.py` and `verify.py` hardcoded `TPS62130_` in output filenames, so any other
  part's curves were misnamed and `verify.py` could not find them. Both now use the part
  name from the figures manifest.
- datasheet-extraction step 2's `verify.py` command left out its directories, so it
  looked in `out/` and not `datasheets/<MPN>/`.

**Not touched.** The README's Status section, `briefs-v1/` and `shared-v2.md` still
name the dev boards. They are history and status records, not skills, and nothing
loads them.
