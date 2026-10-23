# Architecture review rubric

Every line gets a finding. *script* means compute it and show numbers; *judgement* means reason it out and show the reasoning. *stop* lines are structural: if they fail, write the finding and stop. A line whose input is missing is `unanswerable`, never `pass`; a line that doesn't apply is `n/a` with a reason. House-rule figures (derating, debug, naming) come from `ee-schematic-rules`.

| id | check | evidence looks like | how |
|---|---|---|---|
| AR-01 | Every `must` requirement maps to at least one block, rail, or interface | REQ id → ids that satisfy it; uncovered musts named | script |
| AR-02 | Every block traces to at least one requirement — no orphan blocks that exist because they seemed useful | block id → REQ ids; orphans named | script |
| AR-03 | Every category in `requirements.yaml coverage:` is answered, n/a, or deferred with an open item that has an owner | category, state, open item id | script |
| AR-04 | Every block declares a current for every mode in `requirements.yaml modes:`; a zero in sleep needs a comment saying the block is actually off | block, mode, mA | script |
| AR-05 | Recomputed per-rail, per-mode output current matches `power_tree.yaml computed:` within 5% | rail, mode, mine vs claimed, key path | script |
| AR-06 | Sleep budget per rail includes converter Iq; Iq as a share of sleep current is reported, and flagged where it dominates and nobody accepted that | rail, Iq µA, load µA, ratio | script + judgement |
| AR-07 | Coincident peak (sum of `peak_ma`, children rolled up) per rail is under the rail's part-class current limit after house derating | rail, peak mA, class limit, ratio | script |
| AR-08 | Input current at Vin_min, every rail rolled up with Iq, per mode, is under the source `i_limit_a` with margin | source, mode, mA vs limit | script |
| AR-09 | Duty-weighted average current (modes × `duty_pct`) meets any battery-life or energy requirement | mAh/day vs REQ figure | script; n/a if no such requirement |
| AR-10 | No rail has `efficiency` or `iq_ua` with `source: assumed` while a `parts/<mpn>.json` exists for it — power-architecture's second pass hasn't run | rail, field, record path | script |
| AR-11 | Every rail's part class holds house derating against the real stresses: Vin_max vs the class's voltage limit, peak current vs its current limit, inductor saturation vs peak not RMS | rail, stress, limit, ratio | script + judgement |
| AR-12 | Tj = Ta_max + θJA × P_diss ≤ 110 °C for every dissipating rail; LDO dissipation taken at Vin_max, buck at Vin_min | rail, P_diss mW, θJA and its source, Tj | script; unanswerable without θJA |
| AR-13 | Peripheral demand (SPI, I2C, UART, USB, ADC, GPIO incl. chip selects, timers) from buses and interfaces fits the candidate MCU `part_class` with spare | table of demanded vs available | script |
| AR-14 | Pinmux caveat: the datasheet's peripheral count assumes every alternate function is free; on the candidate package, can all demanded peripherals be pinned out at once | pin assignment from the part record, or the conflicts you can see | judgement; unanswerable without a part record |
| AR-15 | I2C addresses unique per bus, including any address a device gets only after a strap | bus, colliding members and address | script |
| AR-16 | No I2C address in 0x00–0x07 or 0x78–0x7F (reserved); nothing above 0x7F and no suspiciously even-only set — both mean someone copied 8-bit write addresses from a datasheet | bus, address, member | script + judgement |
| AR-17 | Every bus member's I/O rail matches the bus voltage, or a translator block is a member; where records exist, driver VOH/VOL clears every receiver's VIH/VIL | bus, member rails, thresholds | script; threshold part unanswerable without records |
| AR-18 | Open-drain pull-ups sized for the bus: Rp ≥ (VDD − VOL)/IOL and Rp ≤ t_r / (0.8473 × Cb), Cb estimated from member count (~10 pF each) plus trace, t_r from the declared speed | bus, Cb, Rp window, chosen Rp or "none declared" | script |
| AR-19 | Every bus endpoint has a matching endpoint — one master, and every slave's interface type is on the bus it's listed on | bus, members | script |
| AR-20 | Power-up order satisfies every sequencing constraint in the part records, and every edge in `sequencing:` cites where its constraint came from | edge, `why`, record path | judgement; unanswerable without records |
| AR-21 | Power-down order is also legal — rails collapse without violating a constraint, and no rail is held up by bulk capacitance while its parent is gone | edge, rail, what holds it up | judgement |
| AR-22 | No bus drives from a powered domain into an unpowered one — current through the receiver's ESD diodes — unless the driver is tri-stated or the domains share a sequencing edge | bus, domains, edge | judgement |
| AR-23 | Brownout, reset and supervision: a supervisor or MCU BOR with its threshold above the lowest operating voltage of anything on the rail; power-fail warning where a requirement needs a clean shutdown | block, threshold V, minimum operating V | judgement |
| AR-24 | Every external interface declares ESD protection | interface, `protection` | script |
| AR-25 | Power input declares reverse-polarity and over-current protection; over-voltage where Vin_max is near a part's limit | source/interface, element | script + judgement |
| AR-26 | Every interface names a connector | interface, `connector` | script |
| AR-27 | Clock accuracy matches the interfaces that need it — USB FS ±2500 ppm, CAN ~±0.5%, RTC timekeeping ±20 ppm, radio per its spec, UART is forgiving | block, interface, ppm required vs declared | judgement |
| AR-28 | A debug header is declared as an interface and matches `project.yaml test_access.debug_header`; every programmable part has a programming path | interface, project.yaml field | script + judgement |
| AR-29 | Test access per house rules is planned: every rail and every bus has a test-point intention and regulator outputs have zero-ohm links where `project.yaml` says so | rail/bus, plan | judgement |
| AR-30 | MPN rule: every non-null `mpn` in system.yaml or power_tree.yaml has a `parts/<mpn>.json` | id, mpn, missing path | script — stop |
| AR-31 | No dangling references: every load's rail exists, every rail's parent exists, every bus member and rail load is a block | offending id and file | script — stop |
| AR-32 | No cycles in the rail parent tree or the sequencing edges | the cycle | script — stop |
| AR-33 | Every open item has `raised_by` and `resolve_by`, and none is due at a phase already passed | item ids | script |
| AR-34 | Single points of failure the requirements don't accept — one fuse, one regulator, one connector carrying everything | block/rail, what it takes down | judgement; usually info |
