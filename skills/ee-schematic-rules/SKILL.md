---
name: ee-schematic-rules
description: >
  The house schematic-stage standard: how to name nets and refdes, how fully a
  part is specified, which passive packages and tolerances to use, how much
  derating to carry, what needs a test point or a debug header, and how a
  schematic sheet is drawn (the D-rules). Load it at the start of schematic
  work and keep it loaded: choosing parts, capturing or drawing a schematic,
  making symbols or footprints, or reviewing a schematic. Also load it whenever
  the question is "what do we do here": how do I name this rail, is 0402
  right, does this need a test point, how much margin does this part need, what
  should this sheet look like. Placement, routing and board rules are
  ee-layout-rules.
---

# EE schematic rules

Apply these. Where a rule has a reason attached, the reason matters more than
the rule: it tells you what to do in the case the rule didn't anticipate.

Rules marked *(draft)* are my proposals or defaults, not yet
signed off. Follow them, but say so if one drives a real decision.

---

## Before anything else: four project questions

These are genuinely project-dependent, so ask them at the start of
`schematic-capture` (or whichever skill first needs one) rather than assuming. Machine-readable form with defaults is in
`references/asks.yaml`; write the answers into `project.yaml`.

1. **Are 0201 passives acceptable on this board?** Default no, 0402 minimum.
2. **What form do signal test points take?** Default a 1mm exposed pad. Depends
   on density.
3. **Where do debug zero-ohm resistors go?** Default all regulator outputs.
4. **What debug header?** Default 2×5 1.27mm Cortex Debug. Depends on board size.

If one goes unanswered, take the default, record it in `project.yaml` as a
default rather than a decision, and log it in `open_items.yaml`. A silent
default is the thing this list exists to prevent.

---

## Naming

**Power rails.** No leading sign — `3V3`, never `+3V3`. Decimal point becomes a
V: `3V3`, `1V8`, `12V`, `0V9`.

**Nets derived from a rail** are voltage first, then device, then pin function:
`1V8_MCU_VDD`, `3V3_ADC_AVDD`. The bare rail is just the voltage: `1V8`.
Voltage-first means every net on a rail sorts together and a prefix match finds
all of them — device-first scatters them.

**Two rails at the same voltage** get a domain qualifier: `3V3` and `3V3_ANA`.
Every rail is labelled with its voltage; never name a rail only by function.

**Grounds.** One `GND`. Do not split grounds. A split (`AGND`, `PGND`) is only
permitted where a part's datasheet requires it, and the split must cite that
part — an unjustified ground split creates return-path problems that layout
cannot fix. The grounds join at exactly one point.

**Buses and peripherals** are bus+index, then what the bus is *for*, then the
signal: `I2C0_SENSORS_SDA`, `I2C1_TELEMETRY_SCL`, `SPI0_FLASH_SCK`. The middle
field names the bus's purpose, not which device is master — a shared multi-drop
net belongs to the bus, so it keeps one name however many devices hang off it.
*(draft)* A per-device signal on a shared bus appends the device:
`SPI0_SENSORS_CS_ADC1`.

**Differential pairs** use `_P` / `_N`. This is what KiCad's diff-pair router and
DRC constraints detect; any other suffix means those constraints silently do
nothing, which looks exactly like a passing board.

**Format.** Uppercase, underscores. No hyphens, dots, spaces or lowercase.

**Reference designators** *(draft — proposed, needs sign-off)*

`R` resistor, including zero-ohm debug and jumpers · `RN` network · `C` capacitor ·
`L` inductor, energy storage · `FB` ferrite bead, filtering · `D` diode including
TVS, Schottky, Zener, LED · `Q` transistor · `U` IC · `Y` crystal or oscillator ·
`J` connector · `TP` test point · `SW` switch · `F` fuse or e-fuse · `K` relay ·
`MH` mounting hole · `FID` fiducial · `NT` net tie · `AE` antenna

Four of those are deliberate rather than conventional. `FB` separate from `L`
because a ferrite in a rail is graded on impedance at frequency and a converter
inductor is graded on saturation current — sharing a prefix means a review can't
tell which check applies. `TP` because test-point coverage is one of the few
debug rules a script can verify outright, and test points drawn as `J` are
invisible to it. `NT` because a permitted split ground has to join at exactly one
point, and a net tie makes that join a real object rather than an intention.
`MH` and `FID` because both must be excluded from the BOM and pick-and-place.

**Refdes are stable across re-runs.** Assign once from the component's identity
and persist. Renumbering invalidates every refdes cited in a past review and
every placement decision recorded against it.

**Sheets** are named after the block they contain.

---

## Every net is named

No auto-generated names reach the netlist. No `Net-(...)`, no `$`, no unnamed
intermediate nodes — including every node of a feedback divider, every node of
an RC filter, and every node between series elements.

This is a hard rule, not a style preference. An unnamed feedback node can't be
checked against the rail voltage it sets, so the review has nothing to reference,
and layout can't classify a net it can't name.

---

## Every part is fully specified

**Every part on the board carries a real MPN and its full descriptor set.** No
generic line items. "0402 100nF X7R" is not a BOM line; a specific
manufacturer part number is.

Descriptors that must be present on every part:

- Manufacturer and manufacturer part number
- Distributor part number (LCSC first, given JLC assembly)
- Package
- Value, where the part has one
- Tolerance
- Voltage rating
- Dielectric, for ceramics
- Temperature grade or range
- Anything else the part is being chosen for — tempco, current rating,
  saturation current, ESR, CTR

The reason is that an unspecified part is an unreviewable one. A line that says
"100nF 0402" can't be checked against derating, can't be checked for DC-bias
capacitance loss, and can't be checked against the rail it sits on — the review
line comes back unanswerable, and the first time anyone finds out is when the
assembler picks something and the rail sags. It also means two builds of the same
board can differ, which is the failure this whole standard exists to prevent.

This does not conflict with resolving commodity parts on price. Substitutable
means an equivalent may be swapped at purchase; it does not mean the design gets
to stay vague. Pick the cheapest part that meets the spec, name it, and mark it
substitutable so purchasing knows it has room.

**Never fill an MPN from memory.** A part number you remember but did not see at
a distributor or in a datasheet is a lead, not a part. Until one is confirmed,
leave the field empty and say so; an empty field gets filled, and an invented
one gets bought.

**The board is fab-ready from the schematic** *(draft — human review
2026-10-04)*. Every BOM part carries `MPN`, `Manufacturer` and `LCSC` symbol
fields, chosen at capture from a live JLC/LCSC lookup with stock confirmed,
JLC basic parts preferred for passives, and a part JLC can't supply marked
`CONSIGNED` with who supplies it (`rules/schematic.md` D-46). The JLC BOM and
CPL come straight from those fields.

**Values are written one way** *(draft — human review 2026-10-04)*: `100nF`,
`1uF`, `10uF`, `2.2uH`, `4.7k`, `10k`, `120R`, `0R`. Units on capacitors and
inductors, a letter at the end of every value, plain ASCII `u` for micro
(`rules/schematic.md` D-45).

---

## Passives and part choice

**0402 is the default capacitor package, including bypass, through 1µF.**

**Package selection is a search, not a table:** the smallest package that meets
both the capacitance and the voltage rating after DC-bias derating. A 1µF 0402
exists at 16V and doesn't at 50V, so a fixed value→package ladder produces an
unbuildable BOM line the first time a rail runs high.

**Decoupling package is minimised on purpose** — a smaller body places closer to
the pin. That makes it a placement constraint too (`ee-layout-rules` L-10), and the rule is only
half-applied if layout doesn't honour it.

**Resistors default to 5%**, 0402 *(draft)*, E24. Tighter tolerance only where the
circuit needs it.

**Dielectric** *(draft)*: X7R up to 1µF, X5R acceptable at 1µF and above, C0G/NP0
where the value is part of a timing, filter or oscillator network. No Y5V or Z5U —
they lose most of their capacitance over temperature and bias, which turns a
bypass cap into an open circuit exactly when the part is working hardest.

**Capacitor voltage rating** *(draft)*: at least 2× working voltage, evaluated
after DC-bias derating rather than on the nameplate. A 6.3V 10µF 0805 can lose
more than half its capacitance at 5V bias.

**Cost.** For commodity passives, resolve on price — a 1k pull-down is a 1k
pull-down, so Murata versus Yageo is decided by cost and availability. But a part
chosen for a real electrical reason (precision, tempco, tolerance, dielectric) is
**not substitutable** and its MPN is binding. Mark it so, or the cheapest-part
rule will swap a 0.1% matched divider for a jellybean and the BOM will still
look fine.

*(draft)* At assembly the bigger lever is usually the number of distinct part
numbers, not unit price. Consolidating three nearby resistor values into one
generally saves more than optimising any single line.

**Approved parts.** There is no hand-curated preferred-parts list. The house
KiCad library (`$EE_LIB`, see `symbol-footprint`) is the approved set — a part
already in it has been used on a board and is vetted by use. Prefer a library
part over an equivalent new one even at slightly higher price: reuse costs
nothing to verify, a new part costs a symbol, a footprint and a verification
pass.

---

## Derating

Derating is taken into account on every part carrying voltage, current or power.
The numbers below are an accepted working reference, not yet ratified *(draft)*:

- Ceramic capacitors: ≤50% of rated voltage, measured after DC-bias derating
- MOSFETs: ≤80% Vds, ≤50% Id
- Resistors: ≤60% rated power
- Electrolytic and polymer caps: ≤80% rated ripple current
- Junction temperature ≤110°C at the project's maximum ambient
- Inductors selected on **saturation** current against **peak** current, not RMS
  against average — peak is load plus half the ripple, and it's peak that
  saturates the core

**Zero-ohm debug resistors are sized for the current they carry**, taken from the
power tree. A 0402 zero-ohm is good for roughly 1A. It sits in the
highest-current path on the board and it's the one part nobody thinks to check.

*(draft)* Derating does not relax at low maturity. A marginal part on a bring-up
board still fails on the bench.

---

## Design for debug

Every design is testable. This is designed in, not added when bring-up goes
wrong.

**Test points** on every voltage rail, on key GPIO, on peripheral bus signals, on
reset and on boot straps. Not every net — the ones someone will actually probe.

**Ground test points are probe loops**, not flat pads. A loop takes a scope ground
spring; a flat pad means the long ground lead comes out, and you spend the
afternoon looking at ringing that isn't on the board.

**Zero-ohm series resistors on regulator outputs** by default, so a rail can be
opened and its current measured.

**Every design has a debug header.** No mandated standard — pick to suit the
board. Not Tag-Connect.

LEDs aren't mandatory but are good practice. A power indicator and an MCU-driven
heartbeat are reasonable where area and power budget allow.

---

## The drawing rules

`rules/schematic.md` holds how a schematic is drawn: flow, clusters, wires vs
labels, power symbols, text, value format and part fields, redraw hygiene
(D-01…D-61). Read it in full before
drawing or reviewing a sheet. Nothing else restates it; skills and reviews cite
it by ID. To change a rule, edit it there and keep its ID.

Placement, routing and the numbers KiCad enforces are in `ee-layout-rules`.

---

## Findings and open items

A default taken from the four project questions goes in `open_items.yaml`. The
shape of that file and of review findings, and how to grade severity while
maturity is undecided, are in
`<ee-skills>/skills/board-doc/references/findings.md`.
