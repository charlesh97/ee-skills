# Schematic review rubric

One finding per line, passes included. *How* says where the answer comes from:
**script** (Python over `review/netlist.net`, `review/bom.csv`,
`datasheets/<MPN>/capture.json`), **visual** (the rendered PNGs), **judgement**
(you, with the house rule and its reason in front of you).

Rules live in `ee-schematic-rules`; this lists only what to check. A line needing a
capture that does not exist is `unanswerable`, and the missing capture is itself
a finding under E-4 — extract it rather than grading around it.

---

## A. Pins and symbol integrity

The only defect class that survives every later check. ERC, DRC and the fab all
pass a wrong symbol.

| # | Check | How | Evidence |
|---|---|---|---|
| A-1 | Every IC's pin number → pin name matches the datasheet pin table for **its package**, resolved from the orderable-parts table | script (`pincheck.py`) | refdes, MPN, package, pin, datasheet name vs symbol name, capture page |
| A-2 | The package column used was resolved, not guessed. Any `PACKAGE COLUMN UNCONFIRMED` is chased by hand before any A-1 row is trusted | judgement | refdes, package, column label |
| A-3 | Pin count on the symbol equals the datasheet's; every pin the datasheet lists exists on the symbol | script | refdes, absent pins |
| A-4 | Thermal pad / exposed pad present, numbered per house rule, and on the net the datasheet requires | script + judgement | refdes, pad pin, net, capture page |
| A-5 | `pintype` is right per pin: supplies `power_in`, regulator outputs `power_out`, open-drain `open_collector`, NC `no_connect`. A supply typed `passive` disables the ERC check that matters | script | refdes, pin, type |
| A-6 | Alphanumeric (BGA/CSP) pins compare as strings — `A1` ≠ `A01`; JEDEC skips I, O, Q, S, X, Z, so a pin `I3` is a transcription error | script | refdes, pin |
| A-7 | Multi-package parts: the footprint on the symbol is the package whose column was used | script | refdes, footprint, package |
| A-8 | No pin name overprints another inside a symbol body (D-47): estimate each name's box at 1.27 mm per character plus the 1.016 mm offset, and check every pair | script + visual | symbol, the two pins, sheet |

## B. Electrical parameters

| # | Check | How | Evidence |
|---|---|---|---|
| B-1 | Every pin's applied voltage within absolute maximum, from the capture's abs-max table, at the worst-case rail | script | refdes, pin, net voltage, abs-max, page |
| B-2 | Recommended operating conditions met, not merely abs-max: input voltage range, common-mode range, logic thresholds | script | refdes, parameter, value, page |
| B-3 | Logic level compatibility across every domain boundary: VOH/VOL of the driver against VIH/VIL of the receiver, both directions | script + judgement | net, driver, receiver, the four numbers |
| B-4 | Level shifting or documented tolerance wherever a net spans two I/O voltages; a 1V8 part on a 3V3 bus with pull-ups looks fine on the bench and is out of spec | script + judgement | net, members, rails |
| B-5 | Feedback divider gives the intended output within the regulator's reference tolerance: Vref × (1 + Rtop/Rbot), checked at both resistor extremes | script | regulator, R refdes, computed V, target |
| B-6 | Pull-up and pull-down values sized, not defaulted: I²C against bus capacitance and rise time, and against the driver's sink current | script | net, R refdes, value, computed rise time |
| B-7 | Current limits: every driven load within the pin's source/sink rating; LED series resistors computed from Vf at the intended current | script | refdes, pin, mA, rating |
| B-8 | Crystal load caps computed from the part's CL: C = 2(CL − Cstray), Cstray stated; drive level within spec | script | Y refdes, CL, C refdes, value |
| B-9 | Every value the vendor's design procedure determines (inductor, Cin/Cout, compensation, soft-start) matches the equation for this operating point; read the equation from the capture's formula crops, not the empty text layer | script + judgement | refdes, equation page, computed vs drawn |
| B-10 | Power dissipation and junction temperature at maximum ambient within the house limit for every regulator and driver | script | refdes, mW, θJA + its board condition, Tj |

## C. Decoupling and power integrity

| # | Check | How | Evidence |
|---|---|---|---|
| C-1 | Every `power_in` pin has a decoupling cap to GND on its own net; count and value per the datasheet's application circuit, not a habit | script | refdes, pin, net, cap refdes, value, page |
| C-2 | Each cap's voltage rating ≥ 2× the rail after DC-bias derating; dielectric per house rule (no Y5V/Z5U) | script | cap refdes, rating, rail, dielectric |
| C-3 | Bulk capacitance at each regulator output and at each far-end load cluster | script + judgement | rail, refdes, total µF |
| C-4 | Every component in the datasheet's typical application circuit is present, or its omission is written down with a reason | judgement, from the capture | refdes, figure page, what differs |
| C-5 | Every unused pin terminated the way the pin-functions table says — tied, pulled, or genuinely open. "Leave unconnected" and "must be tied to GND" look identical on a symbol | script + judgement | refdes, pin, net, page |
| C-6 | No floating inputs: every unconnected input or bidirectional pin carries an explicit no-connect; unused gates terminated | script | refdes, pin, pintype |
| C-7 | Every IC power and ground pin on the intended rail, not a signal net and not the wrong rail | script | refdes, pin, net |
| C-8 | Single `GND`; any split cites a datasheet requirement and joins at exactly one point | script + judgement | net names, refdes, page |

## D. Protection and external interfaces

| # | Check | How | Evidence |
|---|---|---|---|
| D-1 | Every net reaching a connector footprint has ESD protection, a series element, or an explicit "none, because…" | script + judgement | J refdes, net, D refdes |
| D-2 | Protection sized for the interface: clamp voltage below the victim pin's abs-max, capacitance low enough for the data rate | script | D refdes, Vclamp, pin abs-max, pF vs rate |
| D-3 | Input protection on anything leaving the board: reverse polarity, overvoltage, inrush on hot-plug | judgement | net, refdes |
| D-4 | Connector pinout and polarity: pin 1, shield, power and ground where the mating part expects them | visual + judgement | J refdes, pin → net |
| D-5 | A connector that can be plugged in reversed or off-by-one is either keyed or survives it | judgement | J refdes, consequence |
| D-6 | An optional block is NOSTUFF with its bypass fitted and a population note (D-48): every part DNP-flagged, the box title says NOSTUFF, the note says what is given up | script + visual | block, refdes, DNP flags, bypass refdes |

## E. Naming, descriptors and traceability

| # | Check | How | Evidence |
|---|---|---|---|
| E-1 | No auto-generated net names: no `Net-(`, `unconnected-`, `$`, lowercase, hyphens or spaces. Every divider, filter and series node named | script | net name, sheet |
| E-2 | Rails voltage-first with no leading sign; same-voltage rails carry a domain qualifier; derived nets `<V>_<DEVICE>_<PIN>` | script | net name |
| E-3 | Buses named per house rule; differential pairs end `_P`/`_N` and both halves exist | script | net names |
| E-4 | Every part carries manufacturer, MPN, LCSC (graded live under E-7), package, value, tolerance, voltage, dielectric and temperature grade as applicable; every IC MPN has a `datasheets/<MPN>/capture.json` | script | refdes, missing fields / missing capture |
| E-5 | Refdes prefixes per the house table; `MH`, `FID`, `TP` excluded from BOM and position files | script | refdes, footprint |
| E-6 | DNP and stuffing options expressed as KiCad variants, with a BOM per variant; no part DNP in the base with nothing explaining it | script | refdes, variant |
| E-7 | Fab-ready from the schematic (D-46): every BOM part has `MPN`, `Manufacturer` and `LCSC` on its symbol; each LCSC code exists in JLC's library **today**, its MPN is the symbol's MPN, and stock covers the build; a part without JLC stock is `LCSC` = `CONSIGNED` with a `Consigned` field naming who supplies it. Missing fields, a code that doesn't exist or is another part, or zero stock on an unconsigned part is `fail`; stock short of the build or an extended part where a basic passive meets the spec is `warn` | script (`schematic-capture/scripts/jlc.py check`, live) | refdes, field, LCSC code, JLC's MPN and stock, lookup date |
| E-8 | Value text in the house format (D-45): `100nF`, `1uF`, `2.2uH`, `4.7k`, `120R`, `0R`; units on C and L, ASCII `u`, no bare numbers, no RKM. Any R, C, L or FB value off the format is `fail` | script (`jlc.py check`, `value`) | refdes, value as drawn, value as it should read |

## F. Drawing

The drawing rules are `ee-schematic-rules/rules/schematic.md`. Grade against them by
ID rather than restating them here: one finding per D-rule, citing the sheet and
refdes. A broken *ratified* rule can `fail`, and a broken *observed* one is a
`warn`.

| # | Check | How | Evidence |
|---|---|---|---|
| F-1 | ERC clean, or every remaining item excluded with a reason you accept (D-52; one finding per exclusion) | script + judgement | erc.json item, reason |
| F-2 | D-04 (no four-way junctions), checked over the `.kicad_sch` | script + visual | sheet, coordinate |
| F-3 | D-01…D-03, D-10…D-14, D-20…D-25, D-30…D-32, D-40…D-44, D-47, D-48: one line per rule | visual + judgement | sheet, D-rule, refdes |
| F-4 | D-50: after a redraw, the netlist diff against the previous revision is empty or every change is accounted for | script | net, pins before → after |
| F-5 | D-25: no global label on a net that appears on one sheet only (and is not a power net, and not on a multi-instance sheet). `warn` per net | script (global-label names per sheet file) | net, sheet |

## G. Bring-up and de-risking — proposals, not defects

Run last, when you know what the board does. Findings are `info` or `minor`,
each naming the failure it de-risks and its cost. **Propose the two or three that
matter**; fifteen optional additions get ignored as a block, and the one that
would have saved the bring-up goes with them.

| # | Check | How | Evidence |
|---|---|---|---|
| G-1 | Every part in series with a bus or rail that could be wrong or dead has a bypass: DNP 0 Ω pads across a mux, translator, buffer, load switch or ideal-diode. Name what is stranded without it | judgement | refdes, what it strands, proposed pads |
| G-2 | Every rail can be broken for current measurement — a 0 Ω or ferrite in series, per the house zero-ohm rule, sized for the rail's peak | script + judgement | rail, R refdes or absent |
| G-3 | Test points on every rail, reset, boot strap and bus; GND points are probe loops; form per `project.yaml` or the house default | script | net, TP refdes or absent |
| G-4 | Straps and address pins land on pads or resistors, not hard wires — an address collision found at bring-up is then a rework, not a respin | script + judgement | refdes, pin, net |
| G-5 | Pull-up and series values that may need tuning (I²C, clocks, terminations) are discrete parts, not omitted or buried in an IC | judgement | net, refdes |
| G-6 | Unused channels, gates and spare GPIO reach a pad, test point or header rather than dying at the package | script + judgement | refdes, pins |
| G-7 | The board can be powered from a bench supply, and its rails isolated from the host, without cutting a trace | judgement | net, how |
| G-8 | Debug and programming access present even where "we will never need it", and reachable with the enclosure the board ships in | script + judgement | J refdes, pins |
| G-9 | Anything that will be measured under load — current sense, a scope ground near the fast node — has somewhere to attach | judgement | net, refdes |

---

Lines marked *visual* are `unanswerable` if you did not open the image. Lines in
section A are `unanswerable` if the capture for that MPN does not exist — extract
it and re-run rather than passing the line.
