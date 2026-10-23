# Findings and open items

One shape for every review, so any skill can read what another wrote.
`schematic-review` and `layout-review` write `findings/<kind>-<date>.yaml`.
They, and any skill that takes a house default, append to `open_items.yaml`.
`board-doc` reads both. This file is the only copy: cite it, don't restate it.

## Not decided yet: maturity and severity

**Maturity** (what v0 / v1 / production mean here) and **severity** (critical /
major / minor / info) are deferred. Until they exist, report everything you find
and don't suppress a finding on maturity grounds — and don't invent thresholds.
Grade severity by consequence and say what you assumed.

## The shape

```yaml
# findings/schematic-2026-09-28.yaml
reviewed: {file: board.kicad_sch, sha256: "…", stage: null, reviewer: fresh}
findings:
  - id: C-1            # rubric line
    result: fail       # pass | warn | fail | unanswerable
    severity: major    # critical | major | minor | info (by consequence)
    where: U3 pin 7, 3V3_ANA
    evidence: "no cap to GND on 3V3_ANA; capture p12 asks for 100nF"
    assumed: null

# open_items.yaml — append only, never rewrite
- {id: OI-12, from: findings/schematic-2026-09-28.yaml#C-1, text: "…", status: open}
```
