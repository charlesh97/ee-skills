# Frozen Interchange Contracts

Eleven files move between skills. This list is frozen. A skill may create whatever
internal scratch files it likes, but **anything crossing a skill boundary must be
on this list**. If you need a twelfth, stop and report to the human.

All live under the project directory. All are YAML except part records (JSON) and
KiCad-native outputs.

| File | Produced by | Consumed by |
|---|---|---|
| `project.yaml` | human / `requirements` | everything |
| `requirements.yaml` | `requirements` | system-arch, power-arch, arch-review, release |
| `system.yaml` | `system-architecture` | power-arch, part-select, arch-review, sch-capture |
| `power_tree.yaml` | `power-architecture` | part-select, arch-review, sch-capture, layout-constraints |
| `sequencing.yaml` | `power-architecture` | arch-review, sch-capture, sch-review |
| `candidates/<class_id>.yaml` | `part-select` | human approval, part-spec |
| `parts/<mpn>.json` | `part-spec` | symbol-footprint, sch-capture, sch-review, release |
| `netlist.yaml` | `schematic-capture` | sch-review, layout-constraints, release |
| `constraints/` | `layout-constraints` | layout-review, release |
| `findings.yaml` | all three review skills | release |
| `open_items.yaml` | every skill (append) | arch-review, sch-review, release |

## project.yaml

Read by every skill to decide depth. Written once at project start.

```yaml
project_id: "PRJ-0042"
name: "Sensor node rev A"
maturity: v0            # v0 | v1 | production  -- definitions live in house rules
house_rules_version: "2.3.1"
kicad_version: 9        # OPEN QUESTION 2
assembly: jlcpcb        # drives part-select screening
created: 2026-09-03
```

`maturity` is the key field. Rubric lines and gate checks are tagged with the
maturity at which they become expected. Below that maturity, a miss is logged as a
skip rather than a warning.

## requirements.yaml

```yaml
requirements:
  - id: REQ-011
    category: power
    statement: "Operate from 9-36V DC input"
    type: constraint        # constraint | choice | assumption | preference
    priority: must          # must | should | wont
    verify: test            # analysis | inspection | test | demonstration
    source: "customer spec v2, section 4.1"
    asked_of: "J. Kim"
    date: 2026-09-03
coverage:
  power: answered           # answered | deferred | n/a
  compliance: deferred
  wireless: n/a
```

`verify` makes every requirement testable at authoring time and gives `release` its
verification matrix for free. `source` and `asked_of` matter because requirements
churn and you need to know who to go back to.

## system.yaml

A block-and-bus graph. Currents are declared **per operating mode**, and the mode
list is defined once in `requirements.yaml`. This one modelling decision drives
budgets, battery life, input current, and thermal.

```yaml
modes: [off, sleep, idle, active, peak]
blocks:
  - id: U_MCU
    function: "application processor"
    part_class: "Cortex-M33, >=2 SPI, >=1 USB FS, 512KB flash, -40..85C"
    mpn: null                       # set only once a part record exists
    resources: {spi: 3, i2c: 2, uart: 4, gpio: 48}
    loads:
      - rail: "+3V3"
        ma: {off: 0, sleep: 0.1, idle: 12, active: 45, peak: 80}
    requirements: [REQ-003, REQ-011]
buses:
  - id: BUS_I2C0
    type: i2c
    voltage: 3.3
    speed_khz: 400
    members: [U_MCU.I2C0, U_SENS1, U_FUEL]
    addresses: {U_SENS1: 0x48, U_FUEL: 0x55}
```

**MPN rule.** `mpn` may only be non-null if `parts/<mpn>.json` exists. Architecture
emits `part_class` as a requirement; `part-select` and `part-spec` bind an MPN to it.
This is the structural guard against fabricated part numbers.

## power_tree.yaml

A directed graph. Loads reference block ids rather than restating currents.

```yaml
sources:
  - id: SRC_VIN
    type: dc_input
    v: {min: 9.0, nom: 24.0, max: 36.0}
    i_limit_a: 2.0
rails:
  - id: RAIL_3V3
    net: "+3V3"
    v_nom: 3.3
    parent: SRC_VIN
    topology: buck
    part_class: "sync buck, Vin<=40V, Iout>=1A, SOT-23-6 or better"
    mpn: null
    efficiency: {source: assumed, value: 0.88}   # assumed | datasheet | measured
    resolution: estimated                        # estimated | resolved
    loads: [U_MCU, U_SENS1]
```

`resolution` is what makes the architecture <-> part-selection loop mechanical.
`architecture-review` warns on any rail still `estimated` at maturity v1 or above.

## sequencing.yaml

An ordered DAG with per-edge timing. Constraints are **imported from part records**,
never authored by the model.

```yaml
edges:
  - from: RAIL_3V3
    to: RAIL_1V8
    relation: before
    delay_ms: {min: 1.0, max: 50.0}
    constraint_source: "parts/XYZ123.json#sequencing_requirements[0]"
```

## candidates/<class_id>.yaml

```yaml
class_id: RAIL_3V3
part_class: "sync buck, Vin<=40V, Iout>=1A"
searched: [house_approved, parts_db, lcsc, web]
candidates:
  - mpn: "TPS62840DLCR"
    manufacturer: "Texas Instruments"
    lcsc_id: "C2687XXX"
    jlc_status: extended        # basic | extended | not_stocked
    lifecycle: active           # active | nrnd | eol | ltb
    stock: 4200
    price_1k_usd: 0.61
    package: "SON-8"
    temp_grade: "-40..125C"
    second_source: ["..."]
    house_approved: false
    notes: "..."
    tradeoffs: "..."
recommendation: "TPS62840DLCR"
rationale: "..."
approved_by: null               # human sets this
```

Selection is a **choice requiring human sign-off**, never an auto-pick. Cost and
supply consequences are outside what a model can weigh.

## parts/<mpn>.json

The shared, cached part record. Keyed by MPN. Archive the datasheet PDF alongside
it with its revision, because datasheets change and you need the one you designed
against.

```json
{
  "mpn": "TPS62840DLCR",
  "manufacturer": "Texas Instruments",
  "datasheet": {"url": "...", "rev": "SLVSFA4B", "local": "datasheets/..."},
  "package": {"name": "SON-8", "pitch_mm": 0.5, "body_mm": [2.0, 2.0, 0.8]},
  "pins": [{"number": "1", "name": "VIN", "type": "power_in", "function": "..."}],
  "abs_max": {"VIN": {"min": -0.3, "max": 6.5, "unit": "V"}},
  "thermal": {"theta_ja_c_w": 68.0, "tj_max_c": 150},
  "electrical": {"efficiency_curve": [...], "iq_ua": 60},
  "required_externals": [
    {"role": "input_cap", "value": "10uF", "notes": "X7R, >=16V, close to VIN"}
  ],
  "sequencing_requirements": [...],
  "errata": [...],
  "model_3d": {"step": "...", "wrl": "...", "source": "easyeda2kicad",
               "license": "...", "alignment_verified": false},
  "extracted": {"by": "part-spec", "date": "2026-09-03", "confidence": "high"}
}
```

`required_externals` is what lets `schematic-review` check that the bootstrap cap,
feedback divider, and bypass caps are actually present. Without it that rubric line
is unanswerable.

## netlist.yaml

The reviewable connectivity intermediate. Exists under either answer to the HDL
fork, which is why everything downstream depends on it rather than on `.kicad_sch`.

```yaml
components:
  - refdes: U3
    mpn: "TPS62840DLCR"
    value: null
    footprint: "house:SON-8_2x2mm_P0.5mm"
nets:
  - name: "+3V3"
    class: power
    connections: [{refdes: U3, pin: "5"}, {refdes: C12, pin: "1"}]
```

## constraints/

A directory, not one file: `stackup.yaml`, `netclasses.yaml`, `board.kicad_dru`,
`placement_spec.md`, `critical_nets.yaml`.

## findings.yaml

One shape for all three review skills so `release` can aggregate them.

```yaml
review: schematic          # architecture | schematic | layout
reviewed: {netlist: "sha256:...", date: 2026-09-03}
findings:
  - rubric_id: SCH-014
    rubric_text: "Every IC has bypass caps per house rules"
    status: fail           # pass | fail | warn | n/a | unanswerable
    severity: major        # critical | major | minor | info
    evidence: "U3 pin 1 (VIN): no cap within house limit; see netlist.yaml"
    refs: ["U3", "netlist.yaml"]
    expected_at_maturity: v0
```

`unanswerable` is a real status and must be used when an input is missing (e.g. no
part record, so abs-max cannot be checked). It is not a pass.

## open_items.yaml

One ledger for assumptions, deferrals, and skips. Every skill appends; nothing
deletes without a resolution record.

```yaml
items:
  - id: A-014
    kind: assumption       # assumption | deferral | skip
    statement: "Assumed 500mA peak on +5V for the USB host port"
    reason: "Downstream device unspecified"
    raised_by: power-architecture
    owner: requirements
    resolve_by: schematic-review
    justified_by_maturity: v0
    status: open           # open | resolved | accepted
```
