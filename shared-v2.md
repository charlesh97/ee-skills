# Shared Brief v2 — read before authoring any skill

Supersedes 00-project-context.md, 01-contracts.md, 02-skill-template.md and
03-elicitation.md. Those were over-built. This is the simplified version the
human asked for: guidelines an agent follows, iterated as errors surface.

## What we are building

A set of skills a Claude agent loads while designing a PCB in KiCad 10, so that
the output is consistent from board to board and follows the house rules.
The skills are guidelines, not a framework. Prefer a clear paragraph explaining
what to do and why over a schema, a script, or a gate.

The first real use is immediately after these are written: the human will design
a PCB with them. Write for that.

## Principles that survive

1. **Three kinds of work.** Generative (write an artifact), judgement (review
   against a rubric), constraint-authoring (encode intent for a human or tool).
   The AI does not place parts or route traces. It writes constraints and reviews
   the result.
2. **Sequence is enforced by data.** Each skill says what it reads and what it
   writes. If a required input is missing, stop and say which skill produces it.
   Do not synthesize it.
3. **Arithmetic is done in Python, not in prose.** When a number matters, compute
   it in a short inline script and show the numbers. Don't estimate in your head.
4. **Review runs in a fresh context.** The session that drew the schematic is the
   worst reviewer of it. If you produced the artifact, say so and suggest a new
   session.
5. **Every finding has evidence.** A refdes, a net name, a file and line. A review
   with no refs is not a review. Report passes too — an empty section is not a
   clean bill.
6. **Warn and log; stop only on structure.** Missing numbers, skipped analyses,
   unresolved estimates: say so loudly, append to `open_items.yaml`, continue.
   Malformed file or a dangling reference (a load on a rail that doesn't exist):
   stop, because the next step would produce silent garbage.
7. **House rules live in the `ee-house-rules` skill.** Load it. Don't restate
   rules in your skill body — point at it.
8. **Elicitation is the brainstorming pattern.** One question per message.
   Multiple choice where the answer is a choice, with trade-offs and a
   recommendation. Play the design back in sections for approval. Don't run
   ahead into the next phase. Ask whether this is a derivative of an existing
   board first; if so, interview only the deltas.

## Decisions already made

- KiCad 10.0. `kicad-cli` is available and does all reading and exporting:
  `sch erc --format json`, `pcb drc --format json`, `sch export netlist`,
  `sch export bom`, `sch export svg/pdf`, `pcb export gerbers/drill/pos/step/
  ipc2581/ipcd356/svg/pdf`, `pcb render`. Native design variants with `--variant`
  handle DNP and stuffing options. There is no separate file-wrapper library;
  call the CLI directly. Writing `.kicad_sym`, `.kicad_mod` and `.kicad_sch` is
  done by emitting s-expressions directly — small, and only where needed.
- Schematic source of truth is the native `.kicad_sch`. Generate it, render it,
  look at it, fix it.
- JLCPCB assembly first. LCSC is the primary part source; DigiKey/Mouser and web
  search are secondary. There are no distributor connectors; search the web and
  distributor sites directly.
- There is no separate part-select skill. Finding a part happens inside
  `part-spec` (search → confirm with the human → extract datasheet) and, at a
  higher level, inside `system-architecture` and `power-architecture` when they
  propose candidate parts.
- Maturity levels and severity definitions are not yet defined. Do not suppress a
  finding on maturity grounds; grade severity by consequence and say what you
  assumed.

## Files that move between skills

All under the project directory. YAML unless noted.

| File | Written by | Read by |
|---|---|---|
| `project.yaml` | `requirements` | everything |
| `requirements.yaml` | `requirements` | system-arch, power-arch, arch-review, release |
| `system.yaml` | `system-architecture` | power-arch, part-spec, arch-review, sch-capture |
| `power_tree.yaml` | `power-architecture` | part-spec, arch-review, sch-capture, layout-constraints |
| `parts/<mpn>.json` | `part-spec` | symbol-footprint, sch-capture, sch-review, release |
| `datasheets/<mpn>/` (PDF + pipeline capture) | `part-spec` | system-arch, power-arch, sch-capture, sch-review |
| `library/` (`.kicad_sym`, `.pretty/`, `.3dshapes/`) | `symbol-footprint` | sch-capture, layout |
| `<name>.kicad_pro`, `.kicad_sch` | `schematic-capture` | sch-review, layout-constraints, release |
| `<name>.kicad_pcb` | the human (layout) | layout-review, release |
| `constraints/` | `layout-constraints` | the human, layout-review, release |
| `findings/<review>-<date>.yaml` | each review skill | release |
| `open_items.yaml` | every skill, append only | arch-review, sch-review, release |
| `releases/<rev>/` | `release` | fab and assembler |

The netlist is not a hand-authored file. Export it when needed:
`kicad-cli sch export netlist --format kicadsexpr <sch> -o netlist.net`.

### project.yaml

```yaml
name: "sensor node rev A"
board_rev: A
kicad_version: 10
assembly: jlcpcb
board_size_mm: [40, 30]        # ask early; it gates 0201s and test-point form
# answers to ee-house-rules/references/asks.yaml land here:
passives: {allow_0201: false}
test_access:
  signal_tp_form: pad_1mm
  zero_ohm_scope: regulator_outputs
  debug_header: cortex_debug_10
derived_from: null             # a prior project dir, if this is a revision
```

### requirements.yaml

```yaml
modes:                         # defined once here; every load downstream uses these names
  - {id: sleep,  duty_pct: 90}
  - {id: active, duty_pct: 10}
environment:                   # the numbers downstream arithmetic needs
  t_ambient_c: {min: -20, max: 60}
  vin_v: {min: 9, nom: 24, max: 36}
  target_unit_cost_usd: 25
  annual_volume: 500
requirements:
  - id: REQ-001
    category: power            # power|io|wireless|sensing|compute|mechanical|compliance|debug|cost
    statement: "Operate from 9-36V DC"
    priority: must             # must | should | wont
    verify: test               # analysis | inspection | test | demonstration
    source: "Charles, interview 2026-09-03"
coverage:                      # every category reaches a terminal state
  power: answered
  compliance: deferred         # with an open_items entry saying who/when
  wireless: n/a
```

### system.yaml

```yaml
blocks:
  - id: MCU
    function: "application processor"
    part_class: "Cortex-M4, >=2 SPI, >=1 I2C, USB FS, -40..85C"
    candidate_mpns: ["STM32L433CCU6"]     # proposals; not bound until parts/<mpn>.json exists
    mpn: null
    loads:
      - {rail: 3V3, ma: {sleep: 0.05, active: 30}, peak_ma: 80}
buses:
  - id: I2C0_SENSORS
    type: i2c
    voltage: 3.3
    speed_khz: 400
    members: [MCU, IMU, TEMP]
    addresses: {IMU: 0x68, TEMP: 0x48}
interfaces:                            # everything that leaves the board
  - {id: USB, type: usb_fs, connector: "USB-C receptacle", protection: "ESD array"}
```

`mpn` is null until `parts/<mpn>.json` exists. That null is the guard against
invented part numbers. `candidate_mpns` is where proposals go.

### power_tree.yaml

```yaml
sources:
  - {id: VIN, type: dc_input, v: {min: 9, nom: 24, max: 36}, i_limit_a: 2.0}
rails:
  - id: 3V3
    v_nom: 3.3
    parent: VIN
    topology: buck                   # buck | boost | ldo | buck_boost | load_switch | charger
    part_class: "sync buck, Vin<=40V, Iout>=1A"
    candidate_mpns: []
    mpn: null
    iq_ua: {source: assumed, value: 50}
    efficiency: {source: assumed, value: 0.88}
    loads: [MCU, IMU, TEMP]
    computed:                        # filled by a Python calc, per mode
      i_out_ma: {sleep: 0.4, active: 61}
      i_peak_ma: 140
      i_in_ma: {sleep: 0.09, active: 9.4}
      p_diss_mw: {active: 27}
      margin_pct: 55
sequencing:
  - {from: 3V3, to: 1V8, relation: before, delay_ms: {min: 1, max: 50}, why: "MCU datasheet §5.2"}
```

### datasheets/<mpn>/

The datasheet itself and the full extraction from the `hardware-ee-skills`
datasheet pipeline: `<mpn>-<rev>.pdf`, `capture_full.json` (every section as
typed blocks with page and bbox), `capture_semantic.md` (equation glossary and
the distilled design procedure), `tables/` (pin, abs-max, electrical), and
`curves/` (efficiency vs load per Vin, as CSV). `parts/<mpn>.json` is the
summary; this directory is the source. **Architecture and schematic work read
this directly** — the design procedure, the application circuit, the pin
function table and the efficiency curves are what the design decisions rest
on, and a one-line summary of them is not enough to make those decisions well.

### parts/<mpn>.json

Everything the datasheet says that a downstream skill needs, as a summary that
points back into `datasheets/<mpn>/` by page. Pins with names,
numbers and electrical type; absolute maximums; thermal; package with land
pattern dimensions; `required_externals` with which pins each attaches to and a
value or a formula; sequencing requirements; datasheet URL, revision, and local
copy; a per-section confidence.

### findings/<review>-<date>.yaml

```yaml
review: schematic
reviewed: {file: "board.kicad_sch", sha256: "...", date: 2026-09-10}
findings:
  - id: SCH-014
    check: "bypass cap on every IC power pin, per house rules"
    status: fail            # pass | fail | warn | n/a | unanswerable
    severity: major         # by consequence; say what you assumed
    evidence: "U3 pin 1 (VIN): nearest cap is C12 at 6.1mm; rule says as close as possible"
    refs: [U3, C12]
```

### open_items.yaml

```yaml
items:
  - id: A-014
    kind: assumption        # assumption | deferral | skip | default_taken
    statement: "Assumed 500mA peak on 5V for the USB host port"
    raised_by: power-architecture
    resolve_by: schematic-review
    status: open
```

## SKILL.md shape

Keep it under about 250 lines. One optional `references/` file for anything
long (a rubric, a format note, a question bank). No scripts unless one is
genuinely reused every run and is under a page. Explain why, not just what.

```markdown
---
name: skill-name
description: >
  What it does AND when to load it. Be pushy: name the phrases an engineer would
  use without saying the skill's name. This is the only trigger.
---

# Skill Name

## Contract
Reads:  ...
Writes: ...
Stops if: ...  (only structural reasons)

## Before you start
Load ee-house-rules. Load the inputs. Say what's missing and who produces it.

## Steps
Numbered, imperative, with the reason attached where it isn't obvious.

## Check yourself
What to verify before handing off. For generative skills, this includes looking
at the output — render it and read it.

## Handoff
What comes next and what it will read.
```

Reviewer skills additionally state: fresh-context requirement, the rubric
location, evidence rule, the five status values, and playback in sections.
