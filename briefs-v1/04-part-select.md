# Dispatch Brief — `part-select`

**Order 4. Kind: generative. NEW skill. Loops with 03 and 05.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`, `03-elicitation.md`
Coordinate with briefs 03 and 05.

## Intent

Take a `part_class` parametric requirement and return a short list of real,
buyable candidates with trade-offs and a recommendation, for a human to approve.

Split from `part-spec` because **selection needs human sign-off and extraction does
not**. Part choice has cost and supply consequences a model cannot weigh.

## Contract

```
Reads:   system.yaml and/or power_tree.yaml (for the part_class), project.yaml
         (for assembly target and maturity), ee-house-rules (approved/prohibited,
         generics)
Emits:   candidates/<class_id>.yaml
Gate:    scripts/gate.py
Refuses: to auto-select. Emits candidates and stops for human approval. Never
         writes an mpn into system.yaml or power_tree.yaml itself.
```

## Search ladder — in this order, because the first two are where consistency lives

1. **House approved-parts list.** If a blessed part fits, use it and stop searching.
2. **Existing parts DB** from prior projects — someone already qualified it.
3. **LCSC parametric search** (primary; the human's decision).
4. **Web search** for what parametrics cannot express: app notes, reference
   designs, errata, vendor selection guides, "known problems with X".
5. **DigiKey**, secondary, where it can be navigated.

**There are no DigiKey / Mouser / Octopart MCP connectors available.** This is
scripts, keys, and web search. Do not design around a connector that does not
exist. Octopart data now sits behind the Nexar GraphQL API (OAuth2, free tier
capped around 1000 results/month counted per part returned) — useful for
cross-distributor stock, price, and alternates checks, not as a primary search.

**Build a source adapter layer:** `sources/` with one module per source, each
returning a normalized candidate record. Add or drop a source without touching the
selection logic. This tooling moves fast and that is not over-engineering.

## Screening filters — a model will not apply these unless told

**JLC assembly first** (the human's decision), so JLC basic vs extended vs
not-stocked is a first-class screening criterion, not a footnote. Also: lifecycle
status (active / NRND / EOL / last-time-buy), stock and lead time, MOQ, second
source availability, package versus assembly capability, temperature grade,
AEC-Q where relevant, RoHS/REACH, and whether the part is on the house prohibited
list and why.

## Output and approval

2-4 candidates with a comparison table, explicit trade-offs, and a recommendation
with rationale. Elicitation pattern: options with trade-offs, not an open question
and not a silent auto-pick. `approved_by` stays null until the human sets it, and
`part-spec` refuses to run on an unapproved candidate.

## Gate

Hard: schema valid; at least one candidate; recommendation is one of the candidates.
Advisory: no house-approved option was found; recommended part is NRND/EOL, out of
stock, not JLC-stocked, or has no second source; fewer than two candidates.

## Deliverables

Skill directory, schema, source adapters, `screen_candidates.py` (deterministic
filtering and ranking), `emit_candidates.py`, `gate.py`, 2-3 evals — include one
where the ideal part is EOL, to prove the lifecycle screen actually fires.

## Definition of done

House-approved parts win when they fit. Every candidate is real and buyable.
Nothing is selected without a human.
