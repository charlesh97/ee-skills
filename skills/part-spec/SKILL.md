---
name: part-spec
description: >
  Find a real, buyable part for a block or rail and turn its datasheet into a
  machine-readable part record. Load this whenever the question is "find a part",
  "which regulator / MCU / sensor / MOSFET should we use", "what's the part
  number", "is this on LCSC", "is it a JLC basic part", "is this part available /
  in stock / EOL", "pull the datasheet", "what are the pins", "what's the abs max",
  "what externals does this need", "what package is it", or any time a
  system.yaml block or power_tree.yaml rail has a part_class but mpn is null.
  Also load it ad hoc when someone hands you an MPN and wants it specified.
---

# Part Spec

Two phases in one skill. **Find**: turn a `part_class` into 2–4 real candidates
and get the human to pick one. **Extract**: fetch that part's datasheet and write
`parts/<mpn>.json`, the record every downstream skill reads instead of the PDF.
They live together because a candidate is only worth showing if you can also
extract it, and an extraction is only worth doing on a part someone has agreed to
buy. Selection needs the human — cost and supply are their call. Extraction does
not, but it is the highest-hallucination-risk task in the whole set, so most of
this skill is discipline about where numbers come from.

## Contract

```
Reads:   system.yaml / power_tree.yaml  (part_class, candidate_mpns, loads and
         computed currents, sequencing), project.yaml (assembly, allow_0201,
         board_size, volume), requirements.yaml (t_ambient, vin range),
         ee-schematic-rules, the house KiCad library, existing parts/*.json
Writes:  parts/<mpn>.json (the summary), datasheets/<mpn>/ (the PDF plus the
         full pipeline capture — see step 8; this is what architecture and
         schematic capture actually read), the `mpn` field of the block or rail
         it was run for, open_items.yaml (append)
Stops if: the block or rail named does not exist, or has no part_class; or no
         datasheet can be obtained (a record written from memory is worse than
         none — the downstream skills would trust it)
```

Entry points: (a) a block/rail id with `mpn: null` — run Find then Extract;
(b) a bare MPN from the human — skip the candidate comparison but still confirm
the part exists at a source and is buyable before extracting; (c) a re-run on a
part that already has a record — cache check first (step 7).

## Before you start

Load `ee-schematic-rules`. It owns derating, the "every part fully specified"
descriptor set, the cheapest-commodity rule with `substitutable`, and "the
libraries are the approved set". Do not restate them; apply them.

Load the yaml the block or rail lives in. Pull the numbers the screen needs:
Vin min/max, per-mode and peak current, maximum ambient, and for regulators the
`computed` block from power-architecture. If those are missing, say so and name
the skill that produces them (`system-architecture`, `power-architecture`,
`requirements`). Do not invent a load to search against.

Check `project.yaml` for `assembly` and `passives.allow_0201` — both change
which candidates are even eligible.

## Steps — Find

1. **Turn the part_class into numeric screens, in Python.** Apply the house
   derating before searching, not after: a 12V rail wants a ≥25V ceramic, a 36V
   input wants a ≥45V MOSFET, an inductor is screened on saturation current
   against peak (load plus half ripple), and junction temperature is checked at
   the project's maximum ambient, not 25°C. Print the thresholds. Anything that
   fails them is not shown to the human — showing a part that derating rejects
   just invites picking it.

2. **Search the house library first.** A part already in the library has been
   built and is vetted by use; it wins over a slightly cheaper new part because
   a new part costs a symbol, a footprint, and a verification pass. Grep the
   `.kicad_sym` files for the class. If the library path has not been supplied,
   say so once and move on.

3. **Then LCSC / JLCPCB.** JLC assembles the board, so LCSC stock and the JLC
   *basic* vs *extended* status are screening criteria, not footnotes: an
   extended part adds a per-reel loading fee and a basic part does not, which for
   a 500-unit run can outweigh the unit price difference. Use web search and
   fetch (`site:lcsc.com <term>`, `jlcpcb.com/parts` component search). The
   pages are script-heavy; if a fetch comes back empty, use the browser tools
   rather than guessing what the page would have said. Record for each hit: LCSC
   id (Cnnnn), JLC status, stock, price at the project's volume, MOQ.

4. **Then DigiKey / Mouser, then the open web.** Distributors give lifecycle
   (active / NRND / EOL / last-time-buy), datasheet links, and a second source.
   The web gives what parametric search cannot: reference designs, app notes,
   "problems with X", and errata. Search for errata here even if you find
   nothing — you will record that you looked.

5. **Screen what you found.** Drop on: derating thresholds from step 1;
   lifecycle NRND/EOL (unless the human already knows and accepts); stock below
   roughly three builds' worth; MOQ above the build; package the assembler or
   the project forbids; temperature grade below the ambient range; missing RoHS.
   Keep a one-line list of what you dropped and why — the human may disagree
   with a screen, and that list is how they find out one fired.

6. **Present 2–4 candidates and stop.** One message, a table with: MPN,
   manufacturer, LCSC id, JLC status, lifecycle, stock, unit price at volume,
   package, temperature grade, the one or two parameters that decided the
   screen. Under it, the trade-offs in plain words and a recommendation with
   its reason. Then the question: which one. Never auto-pick — cost, supply
   and second-source risk are consequences the human carries, not you. If they
   say "you choose", state the pick and its consequence and get an explicit ok.

   Commodity passives resolve on price: pick the cheapest that meets spec, name
   the MPN, mark it `substitutable: true`. A part chosen for an electrical
   reason — precision, tempco, dielectric, a specific controller — is
   `substitutable: false`, and say what the reason was so a later BOM pass
   doesn't swap it.

   **Anti-hallucination rule.** Every candidate in the table was retrieved this
   session from a URL you fetched or a search result you read, and the URL is
   in the record. An MPN you remember but did not see at a source is a *lead*:
   go look it up, and if it isn't there, it isn't a candidate. Model recall of
   part numbers is confidently wrong often enough that this is the single most
   important rule in the Find phase.

## Steps — Extract

7. **Get the datasheet and archive it.** Prefer the manufacturer's site; the
   LCSC copy is convenient but is often a revision behind. Read the revision
   and date off the first page or footer (TI: "SLVSxxxB – MONTH YEAR"; ST:
   "DSnnnnn Rev n"). Save to `datasheets/<mpn>-<rev>.pdf`. Datasheets change,
   and the review has to be against the one the design was done from.

   Cache check: if `parts/<mpn>.json` exists and its `source.datasheet_rev`
   matches, report that and stop — re-extraction only adds a chance to
   disagree with a record that has already been reviewed. If the revision has
   moved, keep the old record as `parts/<mpn>.<oldrev>.json`, extract fresh,
   and write a `revision_diff` listing what changed (abs max, pins, thermal,
   externals). Downstream skills that consumed the old record need that list.

8. **Run the datasheet extraction pipeline.**

   The pipeline lives in the `hardware-ee-skills` repo at
   `tools/datasheet-pipeline/`. It is deterministic-first: every number comes
   from the PDF's text or vector layer with a page and bounding box, and the
   AI stage (you) only interprets. Set it up once per machine:

   ```bash
   PIPE=<path to hardware-ee-skills>/tools/datasheet-pipeline
   cd $PIPE && python3 -m venv .venv && .venv/bin/pip install pymupdf numpy matplotlib pillow
   ```

   Then per part, with the archived PDF copied to `$PIPE/pdf/<MPN>.pdf`:

   ```bash
   cd $PIPE
   .venv/bin/python tools/full_capture.py pdf/<MPN>.pdf       # -> out/capture/<MPN>_full.json + .md
   .venv/bin/python tools/text_tables.py pdf/<MPN>.pdf --pages <pin,absmax,elec pages> --out out/text
   .venv/bin/python tools/figures.py  pdf/<MPN>.pdf --pages <efficiency pages> --out out/figures --vectors
   .venv/bin/python tools/digitize.py pdf/<MPN>.pdf <fig-id> --out out/digitized   # per efficiency curve
   ```

   What each gives you and where it goes in the part record:
   - `out/capture/<MPN>_full.json` — every section as typed blocks
     (prose / table / equation / figure / list) with `page` and `bbox`. Search
     the `sections` tree for the pin-functions, abs-max, recommended-operating,
     thermal, and mechanical sections instead of reading the PDF linearly.
     Cite the page on every value you copy out; the block gives it to you.
   - `out/text/*.json` — tables rebuilt from word positions. Use this for the
     pin table and abs-max table, then cross-check against the `_full.json`
     blocks for the same page — two independent reads of the same table is
     your pin-truth check.
   - `out/digitized/*.csv` — efficiency vs load per Vin, as calibrated
     polylines. Put the curve in `electrical.efficiency_curve` so
     `power-architecture` can switch a rail from `source: assumed` to
     `source: datasheet` and recompute. This is the single most valuable
     thing the pipeline produces for the power budget.
   - Equations are glyph-garbage in the PDF text layer, so the pipeline crops
     them to PNGs (`crop_equations.py`) and builds a prompt bundle
     (`semantic_prompt.py`). You are the AI stage: read the crops, write the
     equation glossary and the design procedure, and `merge_semantic.py`
     validates that every equation is present and every step is cited before
     it folds them in. The feedback-divider formula and inductor-selection
     equations for `required_externals` come from this step.

   Copy the pipeline outputs into the project so downstream skills find them
   without knowing where the pipeline lives:

   ```
   datasheets/<MPN>/
     <MPN>-<rev>.pdf
     capture_full.json        from out/capture/<MPN>_full.json
     capture_semantic.md      from out/capture/<MPN>_semantic.md (after the AI stage)
     tables/                  from out/text/
     curves/                  from out/digitized/ (efficiency CSVs)
     figures/                 from out/figures/ (application circuit, package drawing crops)
   ```

   The part record you write in step 10 is a summary of this directory, and
   every value in it carries the page it came from. `power-architecture` reads
   `curves/` and the design-procedure equations; `schematic-capture` reads the
   application circuit, the design procedure and the pin function table;
   `system-architecture` reads the pin/alternate-function table when checking
   a candidate MCU. Don't make them re-derive from the PDF what you already
   extracted.

   The pipeline was developed on TI-style two-column datasheets (TPS62130,
   TPS5430). On a vendor with a different page layout, `full_capture.py` may
   mis-order columns or miss captions; if the pin table comes back mangled,
   fall through to step 9 for that section and say so in `confidence`.

   Whatever the pipeline returns, the shape you write is the one in
   `references/part-record-format.md` — map into it, don't dump raw output.

9. **Fallback: read the PDF directly, page-targeted.** Do not read the whole
   thing linearly. Find the page numbers first (`pdftotext -layout` piped to
   grep, or the table of contents), then Read those pages:
   - pin configuration / pin functions table — every pin's number, name, type,
     one-line function;
   - absolute maximum ratings and recommended operating conditions — per pin
     or pin group, with the condition (e.g. "SW, transient <10ns");
   - thermal information — θJA *with its board condition* (JEDEC 2s2p high-K
     vs 1s0p differ by 2×; the number is meaningless without it), Tj max, ψJT
     if given;
   - electrical characteristics — the parameters the design leans on: Vref,
     Iq, switching frequency, current limit, dropout;
   - package / mechanical drawing, usually the last pages — pitch, body,
     **lead span, lead width, lead length, each with tolerance**, thermal pad.
     `symbol-footprint` checks the land pattern against these, so a footprint
     can only be verified if you captured them;
   - typical application circuit and its component-selection section — this
     is where `required_externals` comes from;
   - power-up / sequencing / enable notes, if the part has them.

10. **Write `parts/<mpn>.json`** per `references/part-record-format.md`. The
    fields that earn their place downstream:
    - `pins` — number, name, electrical type (power_in, power_out, input,
      output, bidirectional, passive, nc), function.
    - `abs_max` — one entry per pin or pin group with `condition` and page.
    - `thermal` — θJA with `board`, `tj_max_c`, `psi_jt` when given.
    - `package` — name, pin count, pitch, body, lead span/width/length with
      tolerances, thermal pad; `land_pattern_source` (datasheet page or IPC).
    - `required_externals` — role, value **or formula**, and which pins it
      attaches to. A feedback divider depends on Vout, so emit
      `R1/R2 = Vout/Vref - 1` with Vref, not a number for one rail. A bootstrap
      cap goes between named pins. This is what lets `schematic-review` say
      "C_BST missing between U3.6 and U3.2" instead of "looks fine".
    - `sequencing` — verbatim requirements with section reference; you import
      these, you never author one.
    - `errata` — tri-state: `not_searched`, `searched_none_found`, or a list.
      Errata are separate documents, not in the datasheet; "none in the PDF"
      is not "none".
    - `source` — datasheet URL, revision, local path, LCSC id and URL, the
      candidate URLs from Find.
    - `confidence` — per section, with a reason for anything below high.
    Missing is `null` with a `_reason`. A plausible number is never right.

11. **Self-check the pins against a second source.** Pull the EasyEDA/LCSC
    symbol for the LCSC id (`easyeda2kicad --symbol --lcsc_id=Cnnnn`, or the
    EasyEDA components API) and diff pin numbers and names against yours in a
    short Python block: count, unique numbers, count equals `package.pins`,
    name per number. Agreement is not proof (EasyEDA symbols have errors) but
    disagreement is a real signal: go back to the datasheet page and decide.
    Record the outcome in `checks.pin_crosscheck`. The reason for the effort:
    a wrong pin table here is exactly what `symbol-footprint` verifies against,
    so it would bless a wrong symbol and the error surfaces at bring-up.

12. **Play back the abs-max and pins to the human, briefly**, then **bind**:
    write the MPN into the `mpn` field of the block or rail in `system.yaml` /
    `power_tree.yaml`. This skill is the one allowed to, because writing the
    record is what proves the part exists. Leave `candidate_mpns` as history.
    Report the datasheet Iq and efficiency so `power-architecture` can replace
    its assumed values — that field is theirs to update, not yours.

## Check yourself

- Every candidate shown had a URL it was seen at this session.
- Screens were computed from the project's numbers with derating, not eyeballed.
- The human chose; you did not.
- `datasheets/<mpn>-<rev>.pdf` exists and `source.datasheet_rev` matches it.
- Pin count equals package pin count; pin numbers unique; crosscheck recorded.
- Every abs-max, thermal and package number has a page reference.
- `required_externals` entries name pins, and any value that depends on the
  rail is a formula.
- `errata.status` is not `not_searched` unless you say why.
- Confidence is honest — a uniform "high" on a scanned datasheet is a lie.
- `mpn` in the yaml equals the record filename.

## Handoff

`symbol-footprint` reads `pins` and `package` to acquire and verify a symbol,
footprint and 3D model. `schematic-capture` reads `pins` and
`required_externals` to draw the block. `schematic-review` reads `abs_max`,
`required_externals` and `sequencing` to check it. `release` reads `source` and
`substitutable` for the BOM. `power-architecture` re-runs its arithmetic with
the datasheet Iq and efficiency you reported.
