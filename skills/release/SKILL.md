---
name: release
description: >
  Two-phase release skill for a KiCad 10 board. Phase one, preflight, is
  read-only and safe any time: load it when someone asks "are we ready to
  release", "release checklist", "what's still open", "preflight", "can this go
  to fab", "what would block a release", or wants to see the open-items ledger,
  findings by severity, or the requirements verification matrix. Phase two,
  build, writes releases/<rev>/ — gerbers, drill, pos, STEP, PDFs, engineering
  BOM, JLC BOM and CPL, fab notes, bring-up checklist, manifest. Load it for
  "fab package", "gerbers", "BOM for JLC", "CPL", "pick and place", "release
  package", "cut rev B". Build runs ONLY on a direct instruction that names the
  revision ("generate the release package for rev B"). A clean layout review,
  "looks good", "ship it", "I think we're done", or the end of a session is not
  that instruction — on those, run preflight and stop.
---

# Release

Nothing earlier in this pipeline blocks. Reviews warn and log; assumptions go
into `open_items.yaml` and the work continues. That is the right trade during
design, and it means release is the one place where everything deferred is
forced into daylight and given a disposition. Preflight is that forcing
function. Build is the mechanical part, done by `kicad-cli` so that two runs on
the same board produce the same package.

## Contract

Reads:   `project.yaml`, `requirements.yaml`, `power_tree.yaml`, `parts/*.json`,
         `datasheets/`, `<name>.kicad_sch` (+ sub-sheets), `<name>.kicad_pcb`,
         `constraints/stackup.yaml`, `findings/*.yaml`, `open_items.yaml`,
         previous `releases/<rev>/` if any. Format note: `references/jlcpcb-package.md`.
Writes:  preflight — nothing (print only). build — `releases/<board_rev>/` and
         appends dispositions to `open_items.yaml`.
Stops if: `.kicad_sch` or `.kicad_pcb` missing or unparseable (kicad-cli errors);
         no `findings/schematic-*.yaml` or `findings/layout-*.yaml` at all (name
         `schematic-review` / `layout-review`); any findings file whose
         `reviewed.sha256` does not match the current file — a review of an
         older file is not a review of this board; any open `critical` finding;
         `project.yaml` missing (name `requirements`). Build additionally stops
         without an explicit authorising instruction that names the rev.

## Before you start

1. Load `ee-schematic-rules`. The part-spec rule (every part carries MPN + full
   descriptors + LCSC) and the refdes rule (MH, FID, TP excluded from BOM and
   CPL) are checked here; the definitions live there.
2. Say which phase you are in. If the request is not an explicit build
   instruction, you are in preflight, whatever the wording. State that plainly.
3. `kicad-cli version --format about` — record it. Check `project.yaml`
   `kicad_version` matches the major version.
4. Read `references/jlcpcb-package.md` before running any export. The flags
   there were verified against the KiCad 10 CLI docs; do not improvise others.

## Steps — phase 1, preflight (read-only)

Run every step and print every result, including the ones that pass. Then stop.

1. **Freshness.** `sha256sum` the root `.kicad_sch`, every sub-sheet, and the
   `.kicad_pcb`. For each `findings/*.yaml`, compare `reviewed.sha256` against
   the file it names. Any mismatch is a hard stop: the file changed after it
   was reviewed, so the review says nothing about the board in front of you.
   Report which review is stale and by how many saves if git history exists.
2. **Re-run the checkers yourself.** `kicad-cli sch erc --format json
   --severity-all` and `kicad-cli pcb drc --format json --schematic-parity
   --severity-all --refill-zones`. Parity is the check that the board matches
   the schematic in front of you; a stale netlist passes DRC and ships wrong.
   Count errors and warnings; list every error with its refs.
3. **Findings by severity.** Aggregate across all `findings/*.yaml`: a table
   of review × severity × status. List every `fail` at critical or major with
   id, check, evidence. Any open critical is a stop. Majors do not stop — but
   each must appear in the disposition list in step 4.
4. **The ledger.** Print `open_items.yaml` in full, grouped by status, then by
   kind. For every item still `open`, propose one disposition and ask the human
   to confirm or change it: `resolved` (say by what), `accepted` (name an
   owner and a reason), or `deferred` (to which rev). Do not close items
   yourself. This list is the release record an engineer will read in a year
   to answer "did we skip thermal on purpose?" — write it so it answers that.
5. **Parts.** Export the engineering BOM (`references/`, "engineering BOM").
   Every line must have Manufacturer, MPN, LCSC, package, value, tolerance,
   rating, dielectric, temperature grade as applicable. List violations by
   refdes. Confirm every `MPN` has a `parts/<mpn>.json` and an archived
   datasheet; list those without. Confirm no MH, FID, or TP refdes appears in
   the BOM or pos exports; if one does, the footprint is missing its
   exclude-from-BOM / exclude-from-position attributes — name it.
6. **Requirements verification matrix.** For every `priority: must` in
   `requirements.yaml`: id, statement, `verify` method, and the evidence — a
   findings id whose `check` or `refs` cites the REQ, an analysis in
   `power_tree.yaml.computed`, or a bring-up test. `none` where nothing cites
   it. Unverified musts do not stop the release; they go in the bring-up
   checklist as tests, and you say so.
7. **Summary and stop.** One block: freshness, ERC/DRC counts, findings by
   severity, open items with proposed dispositions, part-spec violations,
   unverified requirements, tool versions. End with: "Preflight complete. To
   build, say: generate the release package for rev <X>." Then wait. Do not
   start any export.

## Steps — phase 2, build (explicit instruction only)

Precondition: the human wrote an instruction that names the rev, and preflight
passed its hard stops in this session on the current file hashes. Record the
authorising name and the instruction verbatim; they go in the manifest. If the
name is not known, ask before writing anything.

1. `mkdir releases/<board_rev>/`. Refuse to overwrite an existing rev dir —
   a rev that shipped is immutable; cut a new letter.
2. Run the exports in `references/jlcpcb-package.md`, in its order: gerbers,
   drill, IPC-D-356 netlist, pos, STEP, board PDF, schematic PDF, engineering
   BOM, JLC BOM, netlist. Every one is a `kicad-cli` call; the model writes no
   fab data. Pass `--variant <name>` to every export that accepts it when
   `project.yaml` names a stuffing variant.
3. **JLC CPL** — `python3 scripts/emit_cpl.py` on the pos CSV. It drops MH/FID/
   TP, renames columns, and applies the per-footprint rotation offset. Print
   which footprints matched a `to-be-verified` offset; those go in the fab
   notes as things to check in JLC's placement preview before paying.
4. **Fab notes** — `fab_notes.md` from `constraints/stackup.yaml`: layer count,
   finished thickness, copper weights, finish, min trace/space, min drill,
   impedance targets, and the JLC order options those imply. Include any
   unverified rotation offsets from step 3.
5. **Bring-up checklist** — `bring_up.md` from `power_tree.yaml`: one row per
   rail in sequencing order — rail, parent, expected voltage, test point refdes
   (the TP whose net is the rail, from the netlist), zero-ohm refdes to open
   for current, expected current per mode from `computed.i_out_ma`. Add a row
   per unverified must-requirement from preflight step 6. This costs minutes
   and is the first thing anyone wants at the bench.
6. **Datasheets** — copy `datasheets/<mpn>-<rev>.pdf` for every MPN in the BOM
   into `releases/<rev>/datasheets/`. The record must survive a vendor moving
   the PDF.
7. **Diff against the previous release**, if `releases/` has an earlier rev:
   BOM lines added / removed / changed (by refdes and by MPN), netlist nets
   added / removed / membership changed. Write `diff_from_<prev>.md`. A change
   that is not in the diff is a change nobody meant to make.
8. **Manifest** — `manifest.yaml`: SHA-256 of every input file and every
   output, `kicad-cli version --format about`, Python version, the
   `ee-schematic-rules` and `ee-layout-rules` SKILL.md hashes, board_rev, variant, date, `authorized_by`,
   `instruction` verbatim, and the disposition of every open item. Gerber,
   drill and STEP headers carry timestamps; hash them with those lines stripped
   (snippet in `references/`) so two builds of the same board compare equal.
   Record PDF hashes as-is and say they are not expected to match.
9. Append the confirmed dispositions to `open_items.yaml` with
   `resolved_in: <rev>` and the release date. Append only.

## Check yourself

- Open the gerbers in a viewer (`kicad-cli pcb render` or gerbview) and look:
  Edge.Cuts present, mask openings on every pad, silk not on pads. Read the
  board PDF and the schematic PDF — every page rendered, title block filled.
- Refdes sets: BOM refdes set ∪ excluded MH/FID/TP = every footprint on the
  board; CPL refdes set = BOM refdes set minus THT parts JLC will not place.
  Compute this in Python and print the three set differences.
- IPC-D-356 exported without error. Its net count equals the netlist's.
- Manifest lists every file in the directory and nothing more.
- Build a second time into a scratch dir; every normalised hash matches.
- If you authored the schematic or constraints in this session, say so; the
  freshness check is objective but the disposition proposals are not.

## Handoff

`releases/<rev>/` goes to the fab and assembler as-is. `bring_up.md` goes to
whoever powers it on. The dispositions appended to `open_items.yaml` are the
starting ledger for the next rev; `requirements` reads them when a derivative
board is started.
