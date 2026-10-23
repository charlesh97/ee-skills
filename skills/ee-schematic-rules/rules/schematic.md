# Schematic drawing rules

How a schematic is drawn, as distinct from what it connects.
`schematic-capture` draws to these rules and `schematic-review` grades against
them by ID. This file is the only copy.

Edit a rule here, and keep its ID. Skills and review findings cite IDs, so a
renumbered rule breaks every past finding. Retire a rule by marking it
*(retired)*, never by reusing its number.

## Where these came from

A board was redrawn by hand from a machine-drawn schematic of the same design:
same netlist, same 42 parts, same two sheets. So the diff between them is
drawing style with the circuit held constant, which is the cleanest evidence we
are going to get.

Status tags:

- **ratified** — signed off (2026-09-03 interview, or a later review). A
  broken ratified rule can `fail` in a review.
- **observed** — inferred from the redraw. One board, one redraw: these are a
  strong signal, not a ruling, so a broken one is a `warn`. Confirm or overturn
  on the next board.
- **open** — a conflict or gap that needs a decision before it can be a rule.
- **draft** — set by a human design review, not yet signed off as a house
  rule. Follow it, and say so when it drives a decision. The review line
  that grades it says how hard it fails.

The reason attached to a rule matters more than the rule. It is what tells you
what to do in the case the rule did not anticipate.

---

## Flow and sheet structure

**D-01 Flow within a sheet: inputs left, outputs right, power in from the top,
ground to the bottom.** *(ratified)* Consistent flow is what lets a reviewer
follow a circuit they have never seen without tracing every wire.

**D-02 Sheet order follows the power and signal path** — a topological sort of
the power and bus connections in the netlist or the brief. *(ratified)* Computable, so a deviation is
reported as a specific swap rather than a complaint.

**D-03 Prefer few coherent sheets over a deep hierarchy.** *(ratified)* Boards
here are small. Depth two is a smell.

**D-04 No four-way junctions.** A junction joins at most three wires; draw two
offset tees. *(ratified)* A four-way dot that renders faintly when scaled or
printed turns a connection into a crossing and the reader cannot tell which was
meant.

---

## Clustering

**D-10 Every function is a self-contained cluster: the IC together with its
decoupling, its pull-ups, and the series parts in its path.** *(observed)* A
reviewer checks a cluster by looking at one region of the page instead of
chasing four labels to four corners. In the redraw each level translator carries its
own decoupling and both its pull-up banks — 3V3 pull-ups on the host side, 1V8
pull-ups on the sensor side, so the translator's two domains are visually
separate.

**D-11 The sheet reads as a left-to-right band of clusters along the signal
path.** *(observed)* Host connectors, then the 3.3 V domain, then translation,
then the 1.8 V sensor side. This is D-01 applied at the level of blocks rather
than pins.

**D-12 Repeated circuits are drawn identically and aligned.** *(observed)* Two
copies of the same circuit, same internal geometry, one directly above the
other. A reviewer verifies one and pattern-matches the second; any difference
between them is then visible as a difference rather than hidden in a different
arrangement.

**D-13 Box each subsystem.** Draw each cluster inside a dashed grey rectangle
with a bold title above its top-left corner, naming what the block does and its
main refdes (`I2C bus 0: MCU 3.3 V ↔ sensor #0, 1.8 V (U13)`). *(ratified —
review of the 2026-09-28 redraw test)* The box turns D-10 from an
arrangement the reader has to infer into one they can see: which parts belong
together, and where one function ends. Boxes don't replace wires. Inside a box
D-20 still applies, and wires and labels may cross a box edge where a signal
leaves the cluster. No box edge runs through a symbol, a label or text (D-44).
A sheet that is one cluster still gets its box and title.

**D-14 A large MCU is drawn as a multi-unit symbol split by function, one unit
per peripheral group, each unit in its own D-13 box.** *(ratified — human review
2026-10-21, motor-driver board: "excellent … continue to do this")* Group the pins the
way the firmware uses them, not the way the package orders them: PWM and break
inputs, analog inputs, each SPI/SAI/QUADSPI client, comms, safety I/O, debug
and boot, and one unit for every supply and ground pin with its decoupling. The
box title names the peripheral and the client (`SPI3 to AD4630-24 via level
shifter (U4E)`), and a short note under the unit says what the firmware must
know (AF number, boot-time gotcha). One 100-pin rectangle hides which pins
belong to which peripheral; split by function, a reviewer checks the pin map
one peripheral at a time against `pinmap.md`. The symbol is the house's own,
generated from the datasheet pin table (symbol-footprint step 3); the footprint
stays the stock package.

---

## Wires versus labels

This is where machine-drawn and hand-drawn schematics diverged most.

**D-20 Inside a cluster, connect with wires. Labels are for crossing clusters
and crossing sheets.** *(observed)* A label pair is an invisible wire: correct
in the netlist, unreadable on the page. The redraw cut local labels 6 → 3 and
raised junctions 0 → 7 on the same circuit.

**D-21 A local label is a name on a wire and appears once.** *(observed)* Two
stubs carrying the same name in place of a wire is not a label, it is a hidden
connection. If a net needs naming and both ends are in view, draw the wire and
label it once.

**D-22 Series and pull-up resistors are drawn inline in the path they sit in.**
*(observed)* A pull-up is drawn between the rail and the node it pulls; a series
resistor between the two nodes it separates. Not as a floating part with a rail
symbol on one end and a label on the other — that hides the topology the part
exists to create.

**D-23 A decoupling cap is wired to the pin it decouples and joined into the
rail with a junction.** *(observed)* Supersedes the old capture skill's "own
short wires to rail and GND symbols", which produced one rail symbol per cap and
no visible shared rail. Drawing the rail makes "which pin does this cap serve"
answerable from the page.

**D-24 A column of parts hanging off rail symbols with labels underneath is
permitted only for multi-drop nets that already carry a global label elsewhere,
and the column sits beside the cluster that owns the net.** *(observed)* The I²C
pull-up banks are the legitimate case: the net genuinely goes several places, so
a wire would cross the page. Everything else uses D-20.

**D-25 Global labels only for nets that leave the sheet. A net that stays on
the sheet carries a local label, sitting on its wire.** *(draft — human review
2026-10-21, motor-driver board)* A switch node, a divider tap, a gate drive or a filter
node is named with a local label placed on the wire (`BUCK12_SW` on the LX
run), not a global-label flag. Global labels are for off-page connections: the
I/O between sheets (`USB_D_P`/`USB_D_N` from the connector sheet to the MCU),
and buses. A global label tells the reader "this goes somewhere else, look for
it"; on a net that never leaves the page it sends them hunting across every
sheet for a partner that does not exist. Decide it from the netlist, not by
eye: a name that appears on one sheet only is local. Exceptions: a net that
matches a power symbol anywhere (KiCad makes power nets global), and a sheet
used more than once (a local label there splits the net per instance, which is
usually what a per-channel net wants; a shared net uses a hierarchical or
global label). Local nets export as `/<Sheet>/<NAME>`, so expect those renames
in the D-50 diff and nothing else.

---

## Power symbols

**D-30 One rail symbol per cluster, shared through junctions — not one per
pin.** *(observed)* Rail symbols fell 18 → 14 on the same circuit. A rail symbol
per pin makes every pin look like a separate supply.

**D-31 A supply flag may be rotated horizontal to feed a horizontal inline
element, flag pointing away from the part. GND is never rotated.** *(observed)*
All 13 grounds upright in the redraw; VDD_3V3 rotated 90° only where it feeds an
inline series resistor. Upright ground is the fastest thing to scan for, so it
stays invariant.

**D-32 A `PWR_FLAG` on every rail that enters the board from a connector or
through a passive**, grouped in one block rather than scattered. Without it ERC
reports the rail undriven, and the fix is a flag, not an exclusion.

---

## Symbols and text

**D-40 A part's orientation follows the path it is in** — horizontal when inline
in a horizontal run, vertical in a pull-up column. *(observed)*

**D-41 Field text rotates with the symbol.** *(observed)* A generator that pins
fields at 0° while rotating the symbol puts the reference and value on top of
each other. KiCad's own default for `Device:R` is worse — it places Value at the
body centre — so field positions are worth setting explicitly.

**D-42 Values are visible.** *(observed)* Hiding a value hides the one thing a
reviewer checks a passive for.

**D-43 Connectors are mirrored so pins face into the sheet, pin 1 at the top.**
*(observed)* Pin 1 at the top makes the drawn pin order the same as the
connector's physical order, which is what a technician compares against.

**D-44 Nothing overlaps: no symbol over a symbol, no label across a body, no
text collision.** Everything on the 1.27 mm grid. *(ratified, from capture §7)*

**D-47 A box symbol is tall enough that no pin name overprints another.**
*(draft — human review 2026-10-21, motor-driver board: UCC27517A `VDD` over `GND`,
LT6654 `GND` into `VOUT`)* A 5- or 6-pin part with one pin on top and one on
the bottom at the same x needs a body taller than both vertical names, and a
bottom-row name must clear the side-pin names it sits under. Size it from the
text, not the pin count: KiCad 10 draws a 1.27 mm pin name at about 1.27 mm per
character, plus the 1.016 mm name offset. Grow the body downward first, so the
side pins keep their rows and existing wiring still lands. D-44 says no text
collides; this is where generated symbols break it most, because a pin-count
heuristic sizes the body and the names never enter the sum.

**D-48 An optional circuit is drawn complete and marked NOSTUFF, with its
bypass fitted where the path must still conduct.** *(draft — human review
2026-10-21, motor-driver board)* When a block may not be wanted on the first build — a
port current limiter, a regen brake chopper, a protection stage whose need is
decided at bring-up — draw every part of it, set KiCad's DNP flag on each, and
where the signal or power has to pass anyway, fit a 0R bypass beside it
(`R706 0R` across the TPS2553 port switch). Say `NOSTUFF` in the box title and
put a population note under the block: what is fitted, what is not, what the
board gives up (a shorted encoder cable now loads 5V directly), and how to
swap. "NOSTUFF" and KiCad's DNP are the same thing; the flag drives the BOM and
CPL, the title tells the reader. The circuit stays reviewed and laid out, so
fitting it later is a BOM change, not a respin.

---

## Values and part fields

From the human review of the four encoder test boards, 2026-10-04, which
found capacitor values written `1u` and `100n`, and parts that could not go
to JLC assembly from the schematic as drawn.

**D-45 Value text has one format, with the unit on capacitors and
inductors.** *(draft — human review 2026-10-04)* The `Value` field of an R,
C, L or FB is a number, an SI prefix and, for C and L, the unit letter, in
plain ASCII:

| Part | Form | Examples | Not |
|---|---|---|---|
| Capacitor | number, `p`/`n`/`u`/`m`, `F` | `22pF`, `100nF`, `1uF`, `4.7uF`, `10uF` | `100n`, `1u`, `0.1uF`, `1µF`, `100 nF` |
| Inductor | number, `n`/`u`/`m`, `H` | `100nH`, `2.2uH`, `10uH` | `10u`, `10µH` |
| Resistor | number, then `R`, `k` or `M` (`mR` below 1 Ω); no Ω | `0R`, `22R`, `120R`, `4.7k`, `10k`, `1M`, `10mR` | `10kΩ`, `10K`, `4k7`, `120`, `0`, `10 k` |
| Ferrite bead | impedance `R` `@` frequency | `600R@100MHz` | `600` |

The number is in 1 to 999 (zero is `0R`) with the largest prefix that keeps it there
(`100nF`, not `0.1uF`; `1k`, not `1000R`), and a decimal point, never the
RKM form (`4.7k`, not `4k7`). Every value ends in a letter, so a bare
number never reaches the BOM: on a resistor below 1 kΩ that letter is `R`.
Prefixes are lower case except `M` (mega). `u` stands for micro, because
`µ` is not ASCII and breaks BOM tools, CSV and grep. Voltage, tolerance,
dielectric and power go in their own fields (`Voltage`, `Tolerance`,
`Dielectric`, `Power`), not in the value. The reason: a value is what a
reviewer checks a passive for (D-42) and what a technician reads off the
BOM at the bench. `1u` on a capacitor is one dropped letter away from
ambiguity, and two spellings of one value split a BOM line in two and hide
that they are the same part.

**D-46 Every part carries its MPN, Manufacturer and LCSC fields, from a live
lookup, at capture.** *(draft — human review 2026-10-04)* Every symbol that
reaches the BOM (everything but `MH`, `FID`, `TP`, `NT`, power symbols and
parts marked exclude-from-BOM) has three fields filled during
`schematic-capture`, not later:

- `MPN`: the manufacturer part number, exactly as the distributor lists it;
- `Manufacturer`;
- `LCSC`: the LCSC / JLC part code (`C1525`), for a part JLC assembles from
  its own stock.

Each is chosen from a live distributor lookup made in the session (JLC's
parts library first; for passives, a JLC *basic* part where one meets the
spec, since extended parts carry a per-part loading fee), with stock
confirmed for the build quantity. Never from memory: a remembered LCSC code
reads exactly like a looked-up one, and it may be a different part, or
discontinued. The `LCSC` code's MPN must be the symbol's MPN. A DNP part is
specified the same way, so it can be fitted later.

A part JLC can't supply (no LCSC code, or none in stock) is **consigned**:
`LCSC` is `CONSIGNED`, and a `Consigned` field says who supplies it and how
(`customer-supplied, 5 pcs from Broadcom samples`). MPN and Manufacturer are
still required. A blank `LCSC` is never a way of saying consigned.

The reason: the board must be fab-ready from the schematic. The JLC BOM and
CPL are generated from these fields, so a part without them is a part
someone looks up by hand at order time, under time pressure, against a
value string. That is where the wrong dielectric, package or voltage gets
bought. These fields are the distributor half of the full descriptor set
in `ee-schematic-rules` ("Every part is fully specified").

---

## Process

**D-50 After redrawing or restructuring an existing schematic, diff the netlist
against the previous revision and account for every change.** *(observed —
learned the hard way)* The redraw was tidier in every respect and still dropped
two global labels, leaving `INT0_3V3` and `INT1_3V3` connected to one pin each,
and swapped J2 pins 3 and 4 — putting 5 V on the net a XIAO expects to be
ground. Both survive a visual read because the page looks right. ERC caught the
first as two `isolated_pin_label` warnings; nothing but a diff catches the
second.

**D-51 Render every sheet and read it.** ERC passes a page with the LDO drawn on
top of the MCU. A check you did not look at did not happen.

**D-52 ERC is zero before handoff**, or every remaining item carries a written
justification. Fix the schematic, not the severity.

---

## File hygiene

Not drawing rules, but they produce noisy diffs and misleading files. Belongs in
the format reference rather than the house standard.

**D-60 Never copy a `.kicad_pro` from another project.** A copied project
carries the old `top_level_sheets` name and root UUID, so the sheet
instance paths do not match the project file and KiCad silently re-keys them
on first save — a diff that had nothing to do with the design.

**D-61 Emitted symbol instances carry `(body_style 1)` and `(in_pos_files yes)`**
so the first save in KiCad produces no diff.

---

## Open — needs a decision

**O-1 Existing boards often don't follow the naming rule.** `ee-schematic-rules`
says rails are `3V3`, `1V8` and buses are `I2C0_SENSORS_SDA`; older boards use
forms like `VDD_3V3` and `I2C0_SDA_1V8`. On a redraw (Mode B) the net names are
frozen, so decide per board whether to rename — renaming touches the schematic
and any routed layout, and keeping the old names costs the prefix-matching and
sort-together properties the rule was written for. Record the choice.

**O-2 A dropped label shows up as an auto-generated net name.** In the redraw
the two nets that lost their labels (D-50) reappeared as `Net-(Q1-D)` and
`Net-(Q2-D)`. So enforcing "every net is named" is a second, independent check
on the failure D-50 describes, not just tidiness.

**O-3 Is `Value` ever legitimately hidden?** D-42 assumes not. A hidden value on
one part of a pair usually looks accidental rather than intended.
