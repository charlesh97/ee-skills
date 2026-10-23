---
name: architecture-review
description: >
  Independent review of a board's system and power architecture before any
  schematic is drawn. Load it when someone says "review the architecture",
  "does the power budget close", "check my power tree", "sanity check the block
  diagram", "is this ready to draw", "before we draw the schematic", "did we
  miss anything at the architecture level", or when system.yaml and
  power_tree.yaml exist and nobody has read them with a critical eye. It walks a
  fixed rubric, recomputes the power budget itself instead of trusting the
  producer's numbers, and writes a finding for every line with evidence.
---

# Architecture Review

The cheapest place in the flow to catch a mistake. A missing SPI port, a rail
that can't carry its sleep current, a fabricated part number — each costs
minutes here and a respin later. This is a judgement skill: it reads, it
recomputes, it writes findings. It does not edit the architecture.

## Contract

```
Reads:   requirements.yaml, system.yaml, power_tree.yaml, project.yaml (required)
         parts/*.json, open_items.yaml (if present)
Writes:  findings/architecture-<date>.yaml
         open_items.yaml (append only; one item per fail, warn, or unanswerable)
Stops if: a required input is missing or won't parse; a load names a rail that
         doesn't exist; a rail names a parent that doesn't exist; a bus member
         isn't a block; any non-null `mpn` has no parts/<mpn>.json. Write the
         structural findings first, then stop and name the skill that fixes it.
```

Structural stops are the only stops. Everything else — missing numbers, assumed
efficiencies, unresolved parts — is a finding and an open item, and the review
continues, because a partial review with named gaps is still worth more than no
review.

## Fresh context

If this session wrote any of the inputs, say so and recommend a fresh session.
The session that chose the architecture already believes in it, and will
rationalise the same way twice. If the human insists, proceed, but put
`reviewer_context: same_session` at the top of the findings file so the release
skill can see it.

## Before you start

1. Load `ee-schematic-rules`. Derating figures, naming, debug and test-access rules
   all come from there; this skill applies them, it doesn't restate them.
2. Load the four required inputs. If one is missing, stop and say which skill
   produces it (`requirements`, `system-architecture`, `power-architecture`).
3. List `parts/*.json`. A part record turns several rubric lines from
   `unanswerable` into real checks; note which rails and blocks have one.
4. Open `references/rubric.md`. Every line in it gets a finding. Not most —
   every. A line you didn't reach is a finding with status `unanswerable`.

## Steps

### 1. Structural pass

Parse all four files. Check every cross-reference (rubric AR-30 to AR-32): loads
to rails, rails to parents, bus members to blocks, cycles in the rail tree or
sequencing. Check the MPN rule: any `mpn` that is not null must have a
`parts/<mpn>.json`. A bound MPN with no record is the invented-part-number
failure the null guard exists to prevent, and every downstream skill will trust
it — so it is a stop, not a warning. Write these findings, and if any failed,
stop here.

### 2. Recompute the power budget — do not trust `computed:`

`power_tree.yaml` carries a `computed:` block written by the producer. A review
that reads it back and agrees is not a review. Recompute from the raw loads in
`system.yaml`, per mode, including converter quiescent current, at Vin_min, and
compare. Run this inline (extend as needed, but keep every sum in Python):

```python
import yaml
S=yaml.safe_load(open('system.yaml')); P=yaml.safe_load(open('power_tree.yaml'))
R=yaml.safe_load(open('requirements.yaml'))
modes=[m['id'] for m in R['modes']]; vin_min=R['environment']['vin_v']['min']
rails={r['id']:r for r in P['rails']}; srcs={s['id']:s for s in P['sources']}
v_of=lambda x: rails[x]['v_nom'] if x in rails else vin_min
out={r:{m:0.0 for m in modes} for r in rails}; peak={r:0.0 for r in rails}
for b in S['blocks']:
    for l in b.get('loads',[]):
        for m in modes: out[l['rail']][m]+=l['ma'][m]   # KeyError = missing mode/rail: a finding
        peak[l['rail']]+=l.get('peak_ma',max(l['ma'].values()))
def i_in(rid,m):   # current a rail pulls from its parent, children rolled up, Iq included
    r=rails[rid]; o=out[rid][m]+sum(i_in(c,m) for c in rails if rails[c]['parent']==rid)
    iq=r['iq_ua']['value']/1000
    if r['topology'] in ('ldo','load_switch'): return o+iq
    return r['v_nom']*o/r['efficiency']['value']/v_of(r['parent'])+iq
for rid,r in rails.items():
    c=r.get('computed',{})
    for m in modes:
        o=out[rid][m]+sum(i_in(k,m) for k in rails if rails[k]['parent']==rid)
        print(f"{rid:6}{m:8} out {o:9.3f}mA  in {i_in(rid,m):9.3f}mA  "
              f"claimed out {c.get('i_out_ma',{}).get(m)}  in {c.get('i_in_ma',{}).get(m)}")
    print(f"{rid:6}peak     out {peak[rid]:9.1f}mA  claimed {c.get('i_peak_ma')}")
for sid,s in srcs.items():
    for m in modes:
        t=sum(i_in(k,m) for k in rails if rails[k]['parent']==sid)
        print(f"{sid} {m}: {t:.2f}mA at Vin_min {vin_min}V vs limit {s.get('i_limit_a')}A")
```

Then judge the numbers, not just the deltas:

- A mismatch over about 5% against `computed:` is a `fail` on AR-05 — the
  producer's arithmetic is wrong or its inputs changed after it ran. Say which.
- Sleep is where budgets die. On a 90%-sleep board, 50 µA of regulator Iq can
  exceed the entire declared sleep load. Report Iq as a share of each rail's
  sleep current (AR-06) and flag it if it dominates and nobody said that's fine.
- Peak is the coincident sum of every load's `peak_ma`. That's conservative;
  say so. If the producer assumed peaks don't coincide, that assumption needs
  to be in `open_items.yaml` with a reason.
- Input current is worst at Vin_min; LDO dissipation is worst at Vin_max.
  Compute each at its own worst case (AR-08, AR-12).
- Efficiency is assumed flat across Vin and load. It isn't — light-load
  efficiency of a buck can be far lower than the datasheet headline. If a part
  record has a curve, use the point nearest the sleep load.

### 3. Walk the rubric

Take `references/rubric.md` top to bottom. For each line, write one finding
(or one per rail/bus when the line applies per rail/bus — suffix the id, e.g.
`AR-05/3V3`). Fields per `shared-v2.md`:

- `status`: `pass | fail | warn | n/a | unanswerable`. `unanswerable` means the
  input needed doesn't exist — no part record, so no absolute maximums to check.
  It is never a pass. `n/a` means the line doesn't apply to this board (no I2C
  bus → I2C lines are n/a) and you must say why.
- `severity`, by consequence. Definitions aren't ratified, so state what you
  assumed in the file header. Working assumption: **critical** — board won't
  work or a part will be damaged (over abs-max, budget exceeds source, sequencing
  that back-drives a die); **major** — needs a respin to fix (missing protection,
  no level translator, address collision, no debug access); **minor** — fix in
  the next revision (assumed Iq with a record on hand, missing test point plan);
  **info** — worth knowing, no action.
- `evidence`: the number, the id, the file and key. "3V3 sleep: recomputed
  0.62 mA vs claimed 0.40 mA; power_tree.yaml rails[0].computed.i_out_ma.sleep."
- `refs`: block, rail, bus, interface, requirement or file ids. Never empty. A
  pass with no refs is an assertion, not a finding.

Passes get the same treatment. "AR-15 pass — I2C0_SENSORS addresses 0x68, 0x48
unique" tells the next reader what was checked; an empty section tells them
nothing.

Where a line is marked *judgement* in the rubric, reason it out and show the
reasoning in the evidence. Where it's marked *script*, compute it and show the
numbers. Don't do arithmetic in prose.

### 4. Write the findings file

`findings/architecture-<date>.yaml`, shape per `shared-v2.md`. Header carries
`review: architecture`, the files reviewed with sha256, the date, the severity
assumptions, and `reviewer_context`. Then every finding.

### 5. Append open items

For every `fail`, `warn`, and `unanswerable`, append to `open_items.yaml`:
statement (quote the finding id and the one-line fix), `raised_by:
architecture-review`, an owner (the skill that fixes it or a named human), and
`resolve_by` (the phase it must be closed before — usually `schematic-capture`
for architecture faults, `part-spec` for missing records). The four `kind`
values don't include a review finding; use `deferral` and note the finding id.
Never overwrite an existing item.

### 6. Play back, worst first, in sections

Sort by severity. Present criticals, stop and wait. Then majors, stop. Then
minors, then info, then passes and unanswerables as a compact list. One section
per message. The human decides what to act on; you don't fix anything here.
Forty findings in one message get skimmed; six get read.

## Check yourself

- Every rubric line has at least one finding. Count them.
- No finding has empty `refs` or empty `evidence`.
- No `pass` on a line whose input was missing — reread every pass on a line
  that needs a part record and confirm the record exists.
- The power numbers in your findings are the ones the script printed, not
  ones you remembered.
- Every `fail`, `warn`, `unanswerable` has a matching open item with an owner.
- You said whether this session produced the inputs.

## Handoff

`schematic-capture` reads `system.yaml` and `power_tree.yaml` next and will
draw whatever is in them; fix criticals and majors before it runs.
`part-spec` closes the `unanswerable` lines by producing part records — after
it runs, `power-architecture` re-runs its second pass and this review runs
again. `release` reads the findings file and `open_items.yaml` and will refuse
to ship with open criticals.
