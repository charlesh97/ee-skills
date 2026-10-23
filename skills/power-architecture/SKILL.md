---
name: power-architecture
description: >
  Builds the power tree for a board: which rails exist, what feeds each one,
  LDO or buck or boost for each, how much current every rail carries in every
  operating mode (quiescent, sustained, peak), what that reflects back to the
  input or battery, how hot each regulator runs, battery life, and the
  power-up and power-down sequencing. Load it when the question sounds like
  "power budget", "power tree", "how much current does this need", "which
  regulator", "LDO or buck", "will it run off USB", "battery life", "rails",
  "sequencing", "what does the input see", or when system.yaml exists and
  power_tree.yaml does not. Also load it to re-run the numbers after parts
  have been chosen.
---

# Power Architecture

Turns the loads declared in `system.yaml` into `power_tree.yaml`: a rail graph
with a topology and part class per rail, a `computed:` block per rail filled by
Python, and inline sequencing. You supply the judgement (topology, sources,
gating); a short script supplies every number. That split is what makes two
runs of the same tree agree.

## Contract

Reads:  `system.yaml` (required — the loads), `requirements.yaml` (required —
        modes, duty, ambient, Vin), `project.yaml`, `parts/*.json` and
        `datasheets/<mpn>/` (optional; their presence upgrades assumed numbers —
        the digitized efficiency curves and the design-procedure equations live
        in the datasheets directory, see "Use the datasheets" below), existing `power_tree.yaml`
        (optional; re-entry).
Writes: `power_tree.yaml`; appends to `open_items.yaml`.
Stops if: `system.yaml` or `requirements.yaml` is missing (say which skill
        writes it — `system-architecture`, `requirements`); a load names a
        rail with no entry in the tree; a rail's parent does not exist; the
        parent graph has a cycle. Anything else is a warning and an open item.

## Before you start

Load `ee-schematic-rules` — rail naming, derating, the zero-ohm-on-regulator-
outputs rule and the four project asks all live there; do not restate them.
Read `requirements.yaml` for the mode list and duty cycles; every current in
this skill is per mode, using exactly those names. Read `system.yaml` and list
the distinct rail names its loads reference — that list is the tree's leaves.
A block with no `loads` gets an open item, not an invented number.

Ask first whether this is a derivative of an existing board. If so, read its
`power_tree.yaml` and interview only the deltas.

## Steps

1. **Detect the pass.** If `power_tree.yaml` exists, you are re-entering: keep
   every human-written field (topology, part_class, `why`, notes) and only
   refresh `source:`/`value:` pairs and `computed:`. For each rail with an
   `mpn` whose `parts/<mpn>.json` exists, copy efficiency at the operating
   point, Iq, shutdown current, current limit and theta_JA from the record and
   mark each `source: datasheet`. Clobbering a human's edits is how this skill
   gets switched off.

2. **Sources.** One question: what feeds the board? DC input, USB, battery, or
   several. If several, model arbitration as *which sources are active in
   which mode* (`active_in:` on the source), not as a static diagram — a board
   that charges from USB and runs from battery has a different tree in each
   mode. A fuel gauge in `system.yaml` means there is a battery; ask about
   chemistry, capacity and whether it charges on-board. Record `v: {min, nom,
   max}` and `i_limit_a` for every source; Vin_min sets dropout and input
   current, Vin_max sets dissipation and abs-max.

3. **Rail graph.** For each leaf rail, ask what feeds it — a source directly or
   another rail. Two rails at one voltage with different noise or gating needs
   are two rails (`3V3`, `3V3_ANA`), named per house rules. Draw the tree back
   to the human as an indented list before going on.

4. **Topology, one rail at a time.** Offer a recommendation with the reason,
   using the decision table in `references/topology-and-protection.md`: the
   Vin/Vout ratio and the current decide LDO versus buck through dissipation
   (`Vdrop × I`), the noise-sensitive loads (ADC reference, RF, PLL) decide
   whether an LDO post-regulates a buck, dropout headroom at Vin_min decides
   whether an LDO can hold regulation at all. Write a `part_class` string
   (parametric: "sync buck, Vin<=40V, Iout>=1A, Iq<50uA"), leave `mpn: null`,
   put candidates in `candidate_mpns`.

5. **Gated rails.** Any rail whose loads are all zero in some mode is a
   candidate for a load switch or a regulator enable driven by the MCU. Ask.
   Record `active_in: [modes]` on the rail; the calculation then charges only
   the part's shutdown current to that mode. This is where sleep budgets are
   won — a peripheral that draws 5µA "off" on a rail that stays up is still
   5µA, and ten of them is the MCU's whole sleep budget.

6. **Assumed numbers.** For every rail without a part record write `iq_ua`,
   `efficiency` (switchers only), `i_limit_a`, `theta_ja_c_w` with
   `source: assumed`, and log each as an open item. Iq is always its own term:
   the textbook `P_in = P_out / η` hides it inside efficiency, and in sleep the
   regulator's own Iq is typically 10–100× the load. Efficiency curves in
   datasheets are at heavy load; at 100µA a buck is nowhere near 88%. The
   split makes that visible instead of averaging it away.

7. **Compute.** Run this from the project directory, never estimate in prose.
   It fills `computed:` on every rail and source and rewrites the file in place
   (key order preserved; YAML style may reflow).

   ```python
   import yaml
   req, sysd, pt = (yaml.safe_load(open(f)) for f in ("requirements.yaml", "system.yaml", "power_tree.yaml"))
   modes = [m["id"] for m in req["modes"]]; duty = {m["id"]: m["duty_pct"] / 100 for m in req["modes"]}
   ta_max = req["environment"]["t_ambient_c"]["max"]
   srcs = {s["id"]: s for s in pt["sources"]}; rails = {r["id"]: r for r in pt["rails"]}
   loads, kids = {}, {r: [] for r in rails}
   for b in sysd["blocks"]:
       for l in b.get("loads", []):
           assert l["rail"] in rails, f"{b['id']} loads rail {l['rail']} which is not in power_tree.yaml"
           loads.setdefault(l["rail"], []).append(l)
   for r in rails.values():
       assert r["parent"] in srcs or r["parent"] in rails, f"{r['id']} parent {r['parent']} does not exist"
       if r["parent"] in rails: kids[r["parent"]].append(r["id"])
   def v_in(r, key):  # parent voltage: a source's min/max, or a rail's nominal
       p = r["parent"]; return srcs[p]["v"][key] if p in srcs else rails[p]["v_nom"]
   def compute(rid, memo={}):
       if rid in memo: return memo[rid]
       r = rails[rid]; v = r["v_nom"]; iq = r["iq_ua"]["value"] / 1000; eff = r["efficiency"]["value"]
       on = r.get("active_in", modes); vmin, vmax = v_in(r, "min"), v_in(r, "max"); linear = r["topology"] in ("ldo", "load_switch")
       c = {"i_out_ma": {}, "i_in_ma": {}, "p_diss_mw": {}}
       peak = sum(l.get("peak_ma", max(l["ma"].values())) for l in loads.get(rid, [])) + sum(compute(k)["i_peak_in_ma"] for k in kids[rid])
       for m in modes:
           if m not in on:  # gated off: no load, only the part's shutdown current
               c["i_out_ma"][m] = 0; c["i_in_ma"][m] = r.get("iq_off_ua", 1) / 1000; c["p_diss_mw"][m] = 0; continue
           io = sum(l["ma"][m] for l in loads.get(rid, [])) + sum(compute(k)["i_in_ma"][m] for k in kids[rid])
           if linear: iin = io + iq; pd = (vmax - v) * io + vmax * iq          # dissipation is Vdrop x I, worst at Vin_max
           else:      iin = (v * io / eff) / vmin + iq; pd = v * io * (1 / eff - 1) + vmax * iq  # Iq is not inside efficiency
           c["i_out_ma"][m], c["i_in_ma"][m], c["p_diss_mw"][m] = round(io, 3), round(iin, 3), round(pd, 1)
       c["i_peak_ma"] = round(peak, 1)
       c["i_peak_in_ma"] = round(peak + iq if linear else (v * peak / eff) / vmin + iq, 1)
       c["margin_pct"] = round(100 * (1 - peak / (1000 * r["i_limit_a"]["value"])), 1)
       c["tj_c"] = round(ta_max + max(c["p_diss_mw"].values()) / 1000 * r["theta_ja_c_w"]["value"], 1)  # sustained, not peak
       memo[rid] = c; return c
   for rid, r in rails.items():
       r["computed"] = compute(rid)
       if r["computed"]["margin_pct"] < 20: print(f"WARN {rid}: {r['computed']['margin_pct']}% margin to part limit")
       if r["computed"]["tj_c"] > 110: print(f"WARN {rid}: Tj {r['computed']['tj_c']}C at Ta {ta_max}C")
   for sid, s in srcs.items():  # what each source sees per mode; runtime for batteries
       roots = [r for r in rails.values() if r["parent"] == sid]
       i_in = {m: round(sum(r["computed"]["i_in_ma"][m] for r in roots), 3) for m in modes}
       s["computed"] = {"i_in_ma": i_in, "i_peak_ma": round(sum(r["computed"]["i_peak_in_ma"] for r in roots), 1)}
       if s["computed"]["i_peak_ma"] > 1000 * s["i_limit_a"]: print(f"WARN {sid}: peak {s['computed']['i_peak_ma']}mA over limit")
       if s["type"] == "battery":
           i_avg = sum(i_in[m] * duty[m] for m in modes if m in s.get("active_in", modes))
           s["computed"] |= {"i_avg_ma": round(i_avg, 3), "runtime_h": round(s["capacity_mah"] / i_avg, 1) if i_avg else None}
   yaml.safe_dump(pt, open("power_tree.yaml", "w"), sort_keys=False); print(yaml.safe_dump({r: rails[r]["computed"] for r in rails}, sort_keys=False))
   ```

   What it computes, per rail and per mode: `i_out_ma` (sum of loads plus
   children's input current), `i_peak_ma` (sum of load peaks — the current
   limit and the zero-ohm see this), `i_in_ma` reflected to the parent at
   Vin_min, `p_diss_mw` at Vin_max, `margin_pct` of peak against `i_limit_a`,
   and `tj_c` from sustained dissipation. Sustained and peak are kept apart on
   purpose: a 2ms radio burst is not DC for junction temperature, but it is
   what trips a current limit and what the input capacitor must supply. For
   batteries: duty-weighted average current and runtime in hours.

8. **Read the numbers against the limits.** Every `WARN` becomes an open item
   or a design change — say which. Check per the ee-schematic-rules derating: Tj at
   Ta_max, source peak against its limit at Vin_min, margin to the part class's
   current. If a rail's Tj is high, the fix is usually topology (LDO → buck)
   or a pre-regulator, not a bigger heatsink. If sleep current is dominated by
   regulator Iq, say so — that is a part-class requirement (`Iq<10uA`), and it
   goes into `part_class` now so `part-spec` searches for it.

9. **Sequencing, inline.** Write `sequencing:` at the bottom of the file, one
   edge per constraint, both directions:

   ```yaml
   sequencing:
     - {from: 3V3, to: 1V8, relation: before, phase: up,   delay_ms: {min: 1, max: 50}, why: "MCU DS §5.2: VDD before VCORE"}
     - {from: 1V8, to: 3V3, relation: before, phase: down, delay_ms: {min: 0, max: null}, why: "MCU DS §5.2: no back-drive into VCORE"}
   ```

   Every `why` cites a datasheet section. Without a part record write
   `why: "unresolved — needs parts/<mpn>.json"` and log it; do not guess an
   order. Power-down matters as much as power-up: a core rail that outlives
   its I/O rail back-drives through the pad ring. Where nothing constrains
   two rails, say so — an empty `sequencing:` with a note is a finding, an
   omitted one is a gap.

10. **Zero-ohm on every regulator output**, per house rules, sized from
    `computed.i_peak_ma`: 0402 to about 1A, then step the package up and check
    the resistor's rated current. Note the package on the rail
    (`zero_ohm: 0402`) so `schematic-capture` does not have to redo the sum.

11. **Play it back** in sections — sources, tree with topologies, the numbers
    table per mode, sequencing, open items — and get each approved before
    moving on. Do not run ahead into part search; propose `candidate_mpns`
    only, and only with a stated reason.

## Use the datasheets, not typical values

Once a regulator has a `datasheets/<mpn>/` capture, the numbers stop being
assumptions:

- `curves/` holds efficiency versus load, one CSV per Vin, digitized from the
  vector plot. Interpolate at each mode's actual load and Vin instead of a
  single scalar — at 1mA in sleep a "92% efficient" buck is often below 60%,
  and the curve shows it. Set `efficiency: {source: datasheet, ...}`.
- Iq, shutdown current, switching frequency and current limit are in the
  electrical-characteristics table under `tables/`, with min/typ/max. Use the
  max where it hurts you (Iq for battery life, current limit min for margin).
- `capture_semantic.md` carries the vendor's own design procedure as
  equations — inductor value from ripple, peak current, output capacitance
  from transient, feedback divider. Use those equations for the part rather
  than the generic ones in `references/`; the vendor's account for that
  controller's behaviour. Cite the equation number and page.
- Power-up, enable, soft-start and sequencing notes come from the capture's
  sections; that's the `why` on each `sequencing:` edge.

If a rail's part has no capture yet, say so, keep `source: assumed`, log it,
and run `part-spec` before `architecture-review` — an assumed efficiency on the
battery rail is the single biggest source of a wrong runtime number.

## Check yourself

- Every load in `system.yaml` lands on a rail in the tree; every rail has a
  parent that exists; the script ran without an assertion.
- `computed:` is present on every rail and source and came from the script,
  not from your head. If you changed a load or a topology, re-run it.
- Iq is a separate field on every rail with a `source`. Sleep `i_in_ma` on
  each source is plausible against the battery-life or standby requirement in
  `requirements.yaml`; if not, name the rail responsible.
- `tj_c` ≤ 110°C at Ta_max and margin ≥ house derating on every rail; every
  exception is an open item.
- Multi-source boards: each mode names which sources are active, and no rail
  is fed by a source that is inactive in a mode where the rail is on.
- Sequencing has both `up` and `down` edges and every `why` either cites a
  datasheet or says `unresolved`.
- Every `mpn` is null unless `parts/<mpn>.json` exists.
- Every `source: assumed` value has an `open_items.yaml` entry with
  `resolve_by: part-spec`.

## Handoff

`part-spec` reads `part_class`, `candidate_mpns`, `computed.i_peak_ma`,
`computed.p_diss_mw` and `tj_c` to search for and confirm a part, then writes
`parts/<mpn>.json`. When it does, re-run this skill (step 1 picks up pass 2).
`architecture-review` checks margins and sequencing against the records.
`schematic-capture` reads rails, zero-ohm packages and sequencing;
`layout-constraints` reads `i_peak_ma` for copper width and the topology for
switcher placement rules. Sizing arithmetic for inductors, capacitors and
input protection is in `references/topology-and-protection.md`.
