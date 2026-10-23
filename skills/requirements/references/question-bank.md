# Requirements question bank

Select and order from here; don't invent questions. Ask one per message. Each
question is tagged with the `requirements.yaml` category it closes (`power`,
`io`, `wireless`, `sensing`, `compute`, `mechanical`, `compliance`, `debug`,
`cost`) or with the block it fills (`modes`, `environment`, `project`). Where
an answer opens or closes a branch it says so. Options carry their trade-off;
where the question is a choice rather than a constraint, recommend one.

Skip anything a loaded artifact already answers. For a derivative, ask only the
questions whose answer might have changed.

---

## S — Scope and provenance (ask first, in this order)

**S1.** Is this a revision or derivative of an existing board? `project`
- Yes → load the prior project dir, play back a summary, set `derived_from`,
  interview deltas only.
- No → full interview.

**S2.** One board, or several boards in a system? `project`
- One → continue.
- Several → interview each separately; capture the interconnect (signals,
  power, connector, cable length) as an `io` requirement on both.

**S3.** In one sentence: what is it, who uses it, what does it do — and what is
already fixed (a connector position, a partner's interface, an existing
enclosure)? `project` — names the project, tells you which branches are live,
and surfaces hard constraints before detail questions.

---

## M — Mechanical envelope (ask before the asks.yaml questions)

**M1.** Board outline — dimensions in mm, or the enclosure it must fit? `mechanical`
→ `board_size_mm`. Under ~25×25 makes 0201 and compact debug headers likely;
over ~60×60 relaxes both. Say that when asking.

**M2.** Existing enclosure, or designed around the board? `mechanical`
- Existing → ask for the STEP/drawing; keep-outs and connector positions are
  fixed. Log a deferral if the drawing isn't available yet.
- New → connector positions are free; note that layout gets to choose.
Either way: which connectors must sit on an edge, and which edge?

**M3.** Height limit above and below the board? `mechanical` — kills tall
electrolytics, inductors and through-hole connectors early.

**M4.** Mounting — screws (how many, where), snap-fit, adhesive, DIN rail? `mechanical`

**M5.** Ingress rating needed (none / IP54 / IP67)? `mechanical` — sealed
enclosures change thermal assumptions and rule out openings for buttons/LEDs.

**M6.** Shock or vibration exposure (bench / handheld / vehicle / machinery)? `mechanical`
Vehicle or machinery → heavy parts need mechanical retention; note for layout.

Then ask the four `ee-schematic-rules/references/asks.yaml` questions — 0201s,
signal test-point form, zero-ohm scope, debug header — one per message.
`project` — write each to its `project_field`.

---

## P — Power source (the main branch)

**P1.** What powers the board? Pick all that apply. `power`
- Battery → opens P-B.
- Wall adapter or DC input → opens P-W.
- USB bus power → opens P-U.
- Rails supplied by a host or carrier board → capture which rails, their
  tolerances and current limits; opens P-W for hold-up only.
- Energy harvesting → treat as battery plus a source; usually `deferred`.
Battery + USB charging is the common combination and opens P-B and P-U.

**P2.** Rough power budget expectation — is this a milliwatt, single-watt, or
tens-of-watts board? `power` — a sanity number, not a design; it sizes the
rest of the interview.

**P3.** Must the board keep running through a supply interruption? For how
long (ms), and what must survive — everything, or just a controlled
shutdown/data save? `power` — closes brownout/hold-up.

### P-B — Battery (opened by P1: battery)

**PB1.** Rechargeable or primary (single-use)? `power`
- Primary (alkaline, lithium coin/AA) → simplest, no charger, no shipping
  paperwork beyond cell class; user replaces it. Closes PB3.
- Rechargeable Li-ion/LiPo → highest energy density, needs charger, protection
  and UN38.3 for shipping; opens PB3, PB5, PB6.
- LiFePO4 → safer, longer cycle life, lower voltage and density; same
  paperwork.
- NiMH → tolerant, low density; rare in new designs.
Recommend Li-ion/LiPo for anything rechargeable unless safety or temperature
argues otherwise.

**PB2.** Runtime target between charges or replacements, in hours/days/years,
and under which mode mix? Is a cell size or capacity already fixed? `power` —
pairs with O1. If both runtime and capacity are given, compute the implied
average current in Python and record it as a derived requirement.

**PB3.** Charge source — USB, dedicated adapter, dock contacts, wireless (Qi),
solar — and charge time target; may it run while charging? `power` — USB opens
P-U. Wireless charging adds a coil and coexistence issues; say so.

**PB4.** Does the user need a state-of-charge readout — none, coarse (LED bars),
or accurate (percent, remaining time)? `power`
- None/coarse → voltage-based estimate is enough.
- Accurate → fuel gauge; adds cost and a calibration step. Recommend coarse
  unless the product promises a percentage.

**PB5.** Battery replaceable by the user, by service, or never? `power` —
drives connector vs solder tab, and the compliance path (IEC 62368-1
treats user-replaceable cells differently).

**PB6.** Will the product ship with the battery installed, and by air? `compliance`
→ UN38.3, shipping mode with near-zero draw, and possibly a ship-mode
requirement. Closes shipping regs.

### P-W — Wall or DC input (opened by P1: wall / host rails)

**PW1.** Input voltage range — min, nominal, max, as numbers. `environment`
→ `vin_v`. "12V" is not an answer; 12V nominal from what to what? Vehicle
supplies need transients (ISO 7637) noted separately.

**PW2.** Who supplies the adapter — us, the customer, or is it a fixed
installation? `power` — customer-supplied means a wide range and reverse
polarity protection; note it as a requirement.

**PW3.** Input connector — barrel jack, USB-C PD, screw terminal, Phoenix,
harness? `io` — USB-C PD opens P-U as well.

**PW4.** Is there an inrush or turn-on current limit from the supply, a fuse,
or a hot-plug scenario? Must the board pass power through to anything
downstream? `power`

**PW5.** Galvanic isolation required from the input? `compliance`
- None → simplest.
- Functional (ground-loop / noise) → isolated DC-DC, low bar.
- Safety (mains-derived, touchable) → creepage/clearance, rated components,
  certification. Mains on this board at all is a scope question — say so.
Recommend none unless mains or a long external cable is involved.

### P-U — USB power (opened by P1 or PB3 or PW3)

**PU1.** USB-A cable, micro-B, or USB-C? If USB-C: 5V only, or PD negotiation
for higher voltage/current? `power` — PD adds a controller; recommend 5V-only
unless the budget needs more than ~7.5W.

**PU2.** Must the board be USB-compliant on enumeration and current draw (100mA
before enumeration, 500mA after), or is it a charger-only port? `compliance`

---

## O — Operating modes (the spine; ask right after power)

**O1.** What modes does the product have, and what fraction of operating time
does it spend in each? `modes` — offer a starter set: `sleep`/`active`;
`sleep`/`idle`/`active`/`peak`; or `always_on`. Duty percentages sum to ~100.
Every downstream load is declared per mode, so get this even if the answer is
"always on, 100%".

**O2.** What wakes it, and how fast must it be ready (ms)? `compute` —
wake-on-interrupt vs timer changes standby current expectations.

**O3.** Any mode with a short high-current burst (radio TX, motor start,
flash write)? Duration and repetition rate. `power` — this is what sizes peak
current and hold-up, and it doesn't show up in averages.

**O4.** Is there an `off` state the user reaches (switch, ship mode), and what
is the acceptable leakage there? `power`

---

## E — Environment (numbers, not adjectives)

**E1.** Operating ambient temperature, min and max in °C. `environment`
→ `t_ambient_c`. If the answer is "room temp" write 0–40 and mark
`source: default`. Inside a sealed enclosure add self-heating; ask whether the
number given is outside or inside the box. Storage/transport range too, if it
differs.

**E2.** Humidity or condensation exposure (indoor dry / outdoor / condensing /
wash-down)? `mechanical` — condensing means conformal coat or potting, which
changes test access. Also: altitude, salt spray, chemicals, UV, anything
unusual?

---

## C — Compute and firmware

**C1.** What does the compute have to do — read sensors and report, run a
control loop, drive a display, run Linux/an OS, process audio/video/ML? `compute`
Describes workload, not a chip. If they name a chip, record it as a constraint
with a reason, not as a design decision.

**C2.** Any existing firmware or ecosystem the team is committed to (an MCU
family, an RTOS, Zephyr, Arduino, a vendor SDK)? `compute` — a real
constraint; record it with its reason.

**C3.** Non-volatile storage needed — configuration only, logging (how much,
how long), or media? Real-time clock, and must it keep time unpowered? `compute`

**C4.** How does firmware get updated in the field — never, over the debug
port, via USB/serial by the user, over the air? `compute` — OTA needs a
bootloader and roughly 2× code storage; say so.

**C5.** Secure boot or firmware encryption required? Debug port locked out in
production? `compute` — lockout changes the test strategy (D3); flag the
interaction.

---

## W — Wireless

**W1.** Does the product need a radio? `wireless` — No → mark `n/a` with reason,
skip W. Yes → continue.

**W2.** Which capability fits the use? `wireless`
- BLE → cheapest, lowest power, needs a phone or gateway within ~10 m.
- WiFi → direct to internet, realistically wants mains or frequent charging.
- BLE + WiFi combo → roughly $4 more and an antenna coexistence problem.
- LoRa / sub-GHz → long range, low data rate, needs a gateway.
- Cellular (LTE-M / NB-IoT) → anywhere with coverage; SIM, carrier
  certification, and $10+ per unit.
- Thread/Zigbee/Matter → home ecosystems; needs a border router.
Recommend the cheapest one that reaches the data.

**W3.** Pre-certified module or discrete radio? `wireless`
- Module → carries modular certification, faster, ~$2–5 more per unit; the
  right answer below ~10k units/year.
- Discrete → cheaper at volume, but you pay for radio certification (~$10–30k
  per market) and RF layout.
Recommend module unless volume clearly justifies discrete.

**W4.** Antenna — on-board (PCB trace/chip, small, enclosure-sensitive) or
external (connector, better range, costs a cable and a hole)? `wireless`
Enclosure material matters: metal kills on-board antennas.

**W5.** Range and throughput actually needed (m, kbps)? `wireless` — numbers.

**W6.** Which target markets will the radio be sold in (US/FCC, EU/CE-RED,
UK/UKCA, Canada/ISED, Japan, others)? `compliance` — each is a certification
line item; module choice must cover all of them.

---

## I — I/O, sensing and interfaces

**I1.** What does the board sense — list each quantity with range and accuracy
needed? `sensing` — "temperature" is not enough; -40–125 °C to ±0.5 °C is.
Mark `n/a` if nothing.

**I2.** What does it drive — LEDs, display, motors, relays, speakers, heaters?
With voltage/current/power per load. `io`

**I3.** Wired interfaces leaving the board — USB, Ethernet, RS-485, CAN, UART,
I2C/SPI to another board, analog out? `io` — one requirement per interface.

**I4.** For each external interface: cable length and where the other end
lives (same enclosure, same room, outdoors, on a vehicle)? `io` — beyond a
metre, ESD/surge protection and driver choice change; beyond ~10 m a
single-ended bus is the wrong answer and this is where it gets caught.

**I5.** Are any external connectors user-accessible while powered (hot-plug,
mis-plug, ESD from fingers)? `io` — drives protection requirements.

**I6.** Human interface — buttons, switches, LEDs, display, buzzer? Count and
purpose. `io`

**I7.** Expansion or future headers needed? What signals and how many spare
GPIO to reserve? `io` — record a number or `n/a`; "some spares" is a guess.

**I8.** Precision analog anywhere (ADC bits and sample rate, reference
accuracy, microvolt signals)? `sensing` — flags analog-domain requirements
for later.

---

## K — Compliance and safety

**K1.** Which markets is the product sold in, and is there a customer or
integrator specification the board must meet? `compliance` — drives everything
below; if W is live, cross-check with W6. Get the document if there is one.

**K2.** EMC — which regime applies? `compliance`
- Consumer/residential (Class B emissions) → tighter emissions limits.
- Industrial (Class A emissions, higher immunity levels — IEC 61000-6-2).
- Automotive, medical, aerospace → own standards; say so and scope it.
Ask emissions class and immunity level separately; they pull in different
directions.

**K3.** Safety standard in play — IEC 62368-1 (ITE/AV), 61010 (lab/measurement),
60601 (medical), 60335 (appliances), none (low-voltage accessory)? `compliance`
Anything touching mains or >60 VDC makes this a must.

**K4.** Hazardous energy on the board — mains, >60 VDC, large battery,
motors, heaters, lasers? `compliance` — each needs a protection requirement.

**K5.** Material and environmental — RoHS, REACH, halogen-free, conflict
minerals, WEEE labelling? `compliance` — RoHS is assumed; ask about the rest.

**K6.** Who runs certification and when — in-house pre-scan, test lab,
self-declare? `compliance` — usually `deferred` with an owner; fine, just
record it.

---

## D — Debug, test and programming

The four `asks.yaml` questions are already asked under M. These are the rest.

**D1.** How is the board tested in production — none (bring-up only), manual
bench, functional test fixture (bed-of-nails, pogo pins), or in-system
self-test? `debug`
- None/manual → fine under ~100 units.
- Fixture → needs test pads on a grid and an unpopulated-side keep-out;
  decide now because it shapes layout.
- Self-test → firmware requirement; record it under `compute` too.
Recommend fixture above a few hundred units per year.

**D2.** How is firmware first loaded — debug header on the line, pre-programmed
parts, USB bootloader, fixture? `debug`

**D3.** Does the debug port stay accessible in the shipped product? `debug` —
if C5 said lockout, the test strategy must finish before lockout; flag it.

**D4.** Status LEDs wanted — power, heartbeat, per-interface activity? `debug`
Not mandatory under house rules, good practice where area and power allow.

---

## L — Cost, volume and lifecycle

**L1.** Target unit cost for the assembled board (USD, at what volume)? `cost`
→ `target_unit_cost_usd`. If unknown, get a ceiling; record it as a ceiling.

**L2.** Annual volume, and first-build quantity? `cost` → `annual_volume`.
First build under ~50 boards changes what's worth optimising.

**L3.** Expected service life in years, and expected production life? `cost` —
over ~5 years means part longevity and no end-of-life parts; record it.

**L4.** Schedule — when do you need working boards on the bench, and what's
fixed (a demo, a trade show, a customer date)? `cost` — this decides how many
`deferred`s are acceptable.

**L5.** Any parts, vendors or distributors that are required or forbidden
(customer-approved vendor list, no single-source, must be on LCSC)? `cost`

---

## F — Manufacturing

**F1.** Assembler — JLCPCB (house default), another CM, in-house? `project`
→ `assembly`. Non-JLC changes the part-sourcing order in part-spec.

**F2.** Single-sided assembly only, or is double-sided placement acceptable? `mechanical`
Single-sided is cheaper and tests easier; double-sided buys area on a small
board. Recommend single-sided unless M1 forces it.

**F3.** Constraints imposed from outside on stack-up (cost cap, existing panel,
impedance control), finish (conformal coat, potting), or marking (serial, QR,
regulatory marks on the PCB)? `mechanical` — don't choose the stack-up here;
just record any constraint on it.

---

## Coverage sweep

Before playback, walk the nine categories and confirm each has a terminal
state. Typical closers:

| category   | answered when                                | commonly n/a when      |
|------------|----------------------------------------------|------------------------|
| power      | P1–P3 plus the opened branch, O3, O4         | never                  |
| io         | I2–I7, PW3                                   | nothing leaves the board |
| wireless   | W1–W6                                        | W1 = no                |
| sensing    | I1, I8                                       | no sensors             |
| compute    | C1–C5, O2                                    | no processor (rare)    |
| mechanical | M1–M6, E2, F2, F3                              | never                  |
| compliance | K1–K6, PB6, PW5, PU2, W6                     | internal-only prototype (say so) |
| debug      | asks.yaml ×4, D1–D4                          | never                  |
| cost       | L1–L5                                        | never; a ceiling counts |

`modes` and `environment` are blocks, not categories — they must be filled, not
marked n/a. A `deferred` needs an `open_items.yaml` entry with an owner and the
skill that has to resolve it.
