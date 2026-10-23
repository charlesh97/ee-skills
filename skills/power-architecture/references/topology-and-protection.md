# Topology, sizing arithmetic and input protection

Reference for `power-architecture` step 4 (topology), step 8 (reading the
numbers) and the handoff to `part-spec`. Every formula here is meant to be run
in a few lines of Python with the project's numbers, not evaluated in prose.

## 1. Choosing a topology per rail

Ask these in order; the first decisive answer wins.

| Question | Answer | Choose | Why |
|---|---|---|---|
| Is Vout > Vin_min? | yes | boost (or buck-boost if Vin range straddles Vout) | Nothing else can do it. A Li-ion cell at 3.0V cannot feed a 3.3V LDO. |
| Dissipation `(Vin_max − Vout) × I_sustained` | > ~300mW, or Tj > 110°C at Ta_max | buck | An LDO turns the whole drop into heat. 24V→3.3V at 100mA is 2.1W — not an LDO. |
| Vin/Vout ratio | > ~2 at any real current (>50mA) | buck | Efficiency of an LDO is Vout/Vin; below 50% you are paying twice for every mA. |
| Load is an ADC reference, RF PA/LNA, PLL, sensor analog supply | yes | LDO post-regulating a buck | Switching ripple at 0.5–2MHz sits inside most ADC and RF bandwidths; PSRR of an LDO at that frequency is what buys you clean bits. Give the LDO ≥0.5V headroom or its PSRR collapses. |
| Sleep-mode current dominates the budget | yes | whichever has Iq ≤ 10% of sleep load; often an LDO or a buck with pulse-skip mode | A 50µA-Iq buck feeding a 20µA sleep load has 30% efficiency in sleep no matter what the curve says. |
| Vin_min − Vout | < LDO dropout + 0.2V | not an LDO | An LDO out of headroom is a resistor; the rail follows Vin and nothing flags it. |
| Rail is only on in some modes and Vout = Vin | yes | load switch | Cheapest way to make a peripheral truly zero in sleep. Check Ron × I_peak for droop. |
| Otherwise, I ≤ 150mA and drop ≤ 2V | | LDO | Simpler, quieter, cheaper, no inductor, no EMI. |

Two rails at the same voltage are two rails when their noise class, gating or
sequencing differs. Do not share a 3V3 between a radio and an ADC reference to
save a part.

Battery systems: a single-cell Li-ion runs 4.2→3.0V. A 3.3V rail needs a
buck-boost or a 3.0V/2.8V design point; decide this at architecture, because
it sets the whole tree. A fuel gauge wants to see the cell directly, before
any switch — put it on the battery node, not a rail.

## 2. Arithmetic that sizes the parts

Run these before writing `part_class`; the results become the numbers in it
(`I_sat ≥ ...`, `C_out ≥ ...`). Symbols: f = switching frequency, D = duty.

**Buck inductor ripple and peak.**
`D = Vout / Vin`, `ΔI_L = Vout × (1 − D) / (L × f)`, `I_L_peak = I_out_peak + ΔI_L / 2`.
Size ripple at Vin_max (worst) to 20–40% of I_out. House rules: choose the
inductor on **saturation current ≥ I_L_peak**, not on RMS. Include the
converter's own current-limit — the inductor must survive the limit, not just
the load, or a short saturates it and the limit stops limiting.

**Boost.** `D = 1 − Vin/Vout`, `I_in_avg = I_out / (1 − D) / η` — the input and
inductor see the *output power divided by the input voltage*. A 3.0V→5V boost at
500mA draws about 0.95A from the cell. `I_L_peak = I_in_avg + ΔI_L/2` with
`ΔI_L = Vin × D / (L × f)`. Boosts have no short-circuit protection through
the inductor path unless the part says so; check.

**Input capacitor RMS ripple (buck).** `I_Cin_rms ≈ I_out × sqrt(D × (1 − D))`,
maximum I_out/2 at D = 0.5. Ceramics take this without heating; a polymer or
electrolytic must be rated for it (house rules: ≤80% of rated ripple).

**X7R DC-bias loss.** A ceramic at half its rated voltage has lost 20–50% of
its nominal capacitance; at rated voltage, more. Read the manufacturer's
DC-bias curve and use the biased value in every formula below. A 10µF 0805 6.3V
on a 5V rail is roughly 4µF. This is why house rules ask for ≥2× voltage
rating — it is a capacitance rule wearing a voltage costume.

**Output droop on a load step.** The converter cannot respond faster than its
loop; for the first `t_resp` (≈ 2–5 switching periods, or 1/(loop bandwidth)),
the capacitor supplies the step alone:
`ΔV ≈ ΔI × t_resp / C_out + ΔI × ESR`.
For an MCU stepping 5→80mA with a 3V3 rail that must stay above 3.0V, solve for
C_out with the biased capacitance, not the nameplate.

**LDO dissipation and junction.** `P = (Vin_max − Vout) × I_sustained + Vin × Iq`,
`Tj = Ta_max + P × θ_JA`. θ_JA from the datasheet is for a specified copper
area; on a small board with little copper it is worse. Use sustained current —
a 2ms burst does not heat a die that has a ~100ms thermal time constant, but
it must be inside the current limit.

**Hold-up capacitance.** To ride through a dropout of `t` at power `P` from
`V_start` down to the converter's `V_uvlo`:
`C = 2 × P × t / (V_start² − V_uvlo²)`. This is why hold-up goes on the high
voltage side: energy scales with V².

## 3. Input protection checklist

Work down the list for each source that leaves the board. Write the result
into the source's `protection:` field and its `part_class` strings.

- **Reverse polarity.** Series Schottky (simple; costs `V_f × I` — 0.4V at 1A is
  0.4W, fine at 100mA, not at 2A), or a P-FET ideal-diode (near-zero drop, needs
  Vgs rating ≥ Vin_max). For a 9–36V input a Schottky must be ≥60V.
- **Transient / TVS coordinated with the converter's abs-max.** The TVS clamp
  voltage at the surge current must sit *below* the converter's absolute
  maximum, and the TVS standoff must sit *above* Vin_max. A 9–36V industrial
  input sees load dump and inductive kicks to 60V+ for milliseconds; a 40V
  converter leaves no room for any real TVS to clamp under it. Pick a 60V
  converter, or add a pre-regulator/clamp stage. This is the most common miss
  on wide-input boards.
- **Inrush and soft-start.** Input capacitance charging from a hard source draws
  a current spike limited only by wiring; a 100µF at 24V from a bench supply
  trips its OCP. Use the converter's soft-start pin, an e-fuse with dv/dt
  control, or an NTC where power is low. Hot-plug on USB-C is limited by spec
  to 10µF at the sink — more needs a load switch with slew control.
- **Hold-up for brownout.** Decide what the board must do during a 10–50ms
  dropout (keep running, or shut down cleanly). Size with the hold-up formula
  above; put the capacitance at the highest voltage node that is still ahead
  of the regulators.
- **Overcurrent / e-fuse.** A resettable e-fuse gives current limit, reverse
  blocking, UVLO/OVLO and slew in one part and is usually worth it above ~1A or
  on anything a user can plug in. Set the limit ≥ `computed.i_peak_ma` of the
  source with margin; below that it trips on the peak the tree already
  predicts. A polyfuse is slow (seconds) and only protects wiring, not silicon.
- **LC input filter damping.** A series inductor or ferrite into ceramic input
  caps forms a high-Q tank; the converter's negative input impedance can make
  it oscillate. Add a damping leg (electrolytic or ceramic + series R, with
  `C_damp ≥ 4 × C_in` and `R ≈ sqrt(L/C_in)`), or accept a lower-Q ferrite.
  Conducted EMI filters for 9–36V inputs almost always need this.
- **UVLO.** Set the converter's under-voltage lockout above the point where its
  own input current at Vin_min would exceed the source limit; a buck at low Vin
  draws its highest input current exactly when the source is weakest.
- **ESD on connectors** is the interface's job (`system.yaml`), not the rail's,
  but a power pin on a user-accessible connector still needs the TVS above.
