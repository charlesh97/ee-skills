---
name: system-architecture
description: >
  Turn an approved requirements set into a block diagram and a system.yaml — the
  blocks a board needs, what class of part fills each one, how they connect
  (SPI, I2C, UART, USB, CAN, GPIO, ADC), what leaves the board and through which
  connector, and how much current each block draws in each operating mode. Load
  this when someone asks for a block diagram, "what chips do we need", "which
  MCU should we use", "how should this be put together", system design,
  architecture, interconnect, peripheral or bus allocation, or "do we have
  enough SPI/I2C/GPIO". Load it right after requirements are approved and
  before any power tree, part record or schematic exists. Do not load it to
  size regulators (power-architecture) or to pick a specific MPN (part-spec).
---

# System Architecture

Requirements says what the board must do. This skill says what it is made of:
blocks, the buses between them, the connectors out, and the current each block
pulls in each mode. It is the same brainstorming conversation as requirements,
continued — the difference is only that the output is a block diagram and a
list of part classes and interconnects, at a level a power tree and a parts
search can start from. Don't over-build it. A dozen blocks, a handful of buses,
a resource count and a picture is a complete result.

## Contract

Reads:  `requirements.yaml` (required), `project.yaml` (required),
        `open_items.yaml` (append), `<derived_from>/system.yaml` if this is a revision,
        `datasheets/<mpn>/` for any candidate that already has a capture (see
        "Use the datasheets" below)
Writes: `system.yaml`, `architecture.md`, appends to `open_items.yaml`
Stops if: `requirements.yaml` or `project.yaml` is missing or unparseable — say
        so and name `requirements` as the skill that produces them. Do not
        reconstruct requirements from the conversation; the interview that
        produced them is the record, and a guess here poisons every file after.
Does not: write a power tree, choose regulators, bind an MPN, or draw a schematic.

## Before you start

1. Load `ee-schematic-rules`. Naming, refdes, derating and debug rules live there;
   you will need the bus naming pattern (`I2C0_SENSORS_SDA`) and the debug
   header answer from `project.yaml`.
2. Read `requirements.yaml` and `project.yaml` in full. Note the mode names —
   every load you declare must use exactly those names, or `power-architecture`
   cannot sum them.
3. If `project.yaml` has `derived_from`, load that project's `system.yaml` and
   `architecture.md`. Present the old block diagram, ask which blocks change,
   and interview only the deltas. A revision should be a short conversation.
4. Check the format in `shared-v2.md` (system.yaml section) before writing. The
   field names there are the contract; downstream skills read them literally.

## Steps

Follow the elicitation pattern from `shared-v2.md` principle 8: one
question per message, multiple choice with trade-offs and a recommendation
where the answer is a choice, never a question whose answer is already in a
loaded file. Design and ask alternate; do not draft the whole diagram and then
ask "does this look right".

### 1. Decompose into blocks

Walk `requirements.yaml` category by category and propose the functional blocks
that satisfy it: a compute block, sensing blocks, wireless, storage, human
interface, external I/O. Every `must` requirement should be covered by at least
one block and every block should point back at a requirement — a block with no
requirement is scope creep, a `must` with no block is a respin. Record the
trace in `architecture.md`, not in `system.yaml`.

Give each block a `function` (one plain sentence) and a `part_class` — a
parametric description of what would fill it: core, peripheral counts, package
family, temperature grade, key spec. Propose `candidate_mpns` freely; this is
where your knowledge of real parts belongs, and the human wants to see names.
But leave `mpn: null`. The null is a structural guard: a part number is only
real once `part-spec` has fetched a datasheet and written `parts/<mpn>.json`.
Until then any MPN in the tree is a guess, and a guessed MPN in a YAML file
looks exactly like a verified one. Explain this to the human the first time it
comes up so the null is not read as an omission.

Ask about the MCU early, because it constrains everything else. Offer two or
three candidate classes with the trade-off stated (peripheral count, price,
package, toolchain the team already has) and recommend one.

### 2. Define buses and point-to-point interconnect

For every connection between blocks decide the bus type, voltage, speed and
members. Multi-drop buses (I2C, SPI with several chip selects, CAN, RS-485)
get an entry in `buses:`; point-to-point signals (a UART, an interrupt, an
enable) still get an entry so they count against MCU resources. Name buses
per house rules — index then purpose, `I2C0_SENSORS`, `SPI0_FLASH`.

For I2C, write every member's 7-bit address into `addresses:` and check for
collisions in Python, not by eye. Reserved ranges are 0x00-0x07 and 0x78-0x7F.
Where two candidate parts share an address, note the fix (address pin, second
bus, or a mux) as an open item. Check that a bus's voltage matches every
member's I/O domain; where it doesn't, add a level-shifter block or move the
member to a bus at its own voltage. A 1.8V sensor on a 3.3V bus is a common
silent failure — the pull-ups make it look like it works on the bench.

### 3. Interfaces: everything that leaves the board

List every connector, antenna, and exposed pad in `interfaces:` with a `type`,
a `connector` and a `protection` element. Anything touching the outside world
gets ESD, TVS, a series element or an explicit "none, because …". The debug
header from `project.yaml` is an interface. Confirm connector choices with the
human; they are often already decided by the enclosure.

### 4. Declare per-mode current on every block

Every block carries `loads:` — one entry per rail it draws from, with a
current in milliamps for every mode in `requirements.yaml` and a `peak_ma`.
Rails at this stage are names and voltages only (`3V3`, `1V8`); which
regulator makes them is `power-architecture`'s problem, but the rail names
you write here are the ones it will use, so name them per house rules.

Where you know a number from a datasheet you have read, say so. Where you are
estimating, ask the human first — they often know — and if you still have to
estimate, write the estimate in and log it to `open_items.yaml` with
`kind: assumption`, `raised_by: system-architecture`, and
`resolve_by: part-spec`. Never leave a load blank and never quietly insert a
plausible figure. `power-architecture` treats a missing load as a stop and an
unlogged estimate as truth; both are worse than a logged guess.

### 5. Resource sanity against the candidate MCU

Count what the design needs — SPI, I2C, UART, USB, CAN, ADC channels, timers,
GPIO — and compare against what the leading candidate MCU offers. Do this in a
short Python snippet (see `references/architecture-md.md`) and show the table.
Anything at or over available is a problem now; anything under 20 percent
spare is worth flagging, because GPIO always grows during capture.

Say plainly that a passing count is necessary and not sufficient. Peripheral
instances share pins, and the real failure is a pinmux conflict — the second
SPI exists but its only SCK pin is the one the USB needs. The count here
catches the gross miss months early; `part-spec` must confirm from the
datasheet's alternate-function table that the pinout actually supports this
allocation, and `schematic-capture` must not re-plan it. Write the allocation
into `architecture.md` so there is something to confirm against.

### 6. Commonly forgotten blocks

Run down this list with the human before playback. Each has been missed on a
real board; none of them show up in requirements because nobody asks for them.

- **Clocking.** Which blocks need a crystal, and to what accuracy class. USB
  full speed needs ±0.25 percent (2500 ppm) and CAN typically ±0.5 percent,
  so an internal RC oscillator is not enough for either. An RTC wants 32.768
  kHz at ±20 ppm. Decide crystal versus oscillator and who provides the clock.
- **Reset and supervisor.** Power-on reset source, brown-out threshold, an
  external supervisor if the MCU's internal one is not trusted at the minimum
  supply, a reset button or test point per house debug rules.
- **Boot-mode straps.** Which pins the MCU samples at reset and what state
  they need. They are GPIO you cannot freely use at boot, and they need a
  test point.
- **Level shifting.** Anywhere two blocks on different I/O voltages meet, or
  where a 5V-tolerant input is assumed and not confirmed.
- **Debug access.** The debug header from `project.yaml`, a UART console if
  the team uses one, and whether the debug interface shares pins with
  anything above.
- **Storage and identity.** External flash or EEPROM, a MAC/serial EEPROM if
  the wireless block does not carry one.
- **Indicators.** Power LED and heartbeat LED, per house rules, if area and
  budget allow.

Add the blocks these produce, count their pins in step 5, and log anything
deferred.

### 7. Play back the block diagram before writing

Render the Mermaid block diagram and present it with the block list under it.
Then present the buses and interfaces, then the loads table, then the resource
count — a section at a time, approval per section. Incorporate changes, re-render,
re-present the changed section only. Do not write `system.yaml` until the
diagram is approved: the diagram is the thing the human can actually judge, and
the YAML is its transcription.

### 8. Write the outputs

Write `system.yaml` in the `shared-v2.md` shape. Write `architecture.md` with the
Mermaid diagram, the requirement trace, the resource table, the pin allocation,
and the checklist outcomes; the format is in `references/architecture-md.md`.
Mermaid rather than Graphviz because it renders in any Markdown viewer with no
install. Emit nodes in the order blocks appear in `system.yaml` and edges in
bus then interface order, and keep that order on re-runs, so a diff of
`architecture.md` shows a design change and not a reshuffle.

## Use the datasheets, not your memory of them

When a decision turns on what a part actually does — does this MCU have three
SPI *that can be muxed onto free pins*, does this sensor speak I2C at 400kHz,
what does this radio module need for supply — don't answer from recall. If the
candidate has a `datasheets/<mpn>/` capture, read `capture_full.json`: the
pin-functions and alternate-function tables are `table` blocks with page
numbers, and the features and electrical sections are searchable by heading.
If it doesn't have one yet and the decision matters, run `part-spec` on the
candidate now — extraction doesn't need the human to have committed to the
part, and an architecture built on a remembered pinout is the most common way a
board ends up with two peripherals fighting over one pad. Cite the page when
you use a number.

## Check yourself

- Every mode name in every `loads:` entry matches `requirements.yaml` exactly;
  every load has every mode and a `peak_ma`.
- Every `mpn` is null. Every `part_class` is a spec someone could search on.
- Every I2C bus's addresses are unique and outside reserved ranges — by script.
- Every bus member exists as a block; every rail named in a load appears on at
  least one other block or is flagged as single-load. No dangling references.
- Every `must` requirement has a block; every block has a requirement.
- Every interface has a `protection` entry, even if it is a justified "none".
- The resource table is present and the pinmux caveat is written next to it.
- Every estimate you made is in `open_items.yaml`. Count them; say how many.
- Open `architecture.md` and read the rendered diagram. Does it match what the
  human approved? Are the nodes in the declared order?
- You did not write a power tree, a regulator choice, or a schematic.

## Handoff

Next is `power-architecture`, which reads `system.yaml` and sums the loads per
rail per mode. Then `part-spec` turns each `candidate_mpns` entry the human
approves into a `parts/<mpn>.json` — and confirms the pin allocation against the
real alternate-function table. `architecture-review` reads all of it in a fresh
session. Say to the human: "system.yaml and architecture.md are written; the
next skill is power-architecture. Not starting it in this session."
