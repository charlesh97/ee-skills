# Dispatch Brief — `architecture-review`

**Order 6. Kind: judgement. Read-only, zero blast radius.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md` (reviewer template)

## Intent

The cheapest place in the entire flow to catch a mistake. Fresh context, rubric,
evidence per line.

## Contract

```
Reads:   requirements.yaml, system.yaml, power_tree.yaml, sequencing.yaml,
         project.yaml, open_items.yaml, parts/*.json (where they exist)
Emits:   findings.yaml (review: architecture)
Gate:    scripts/gate.py
Refuses: to review artifacts produced in the current session. Says so and
         recommends a fresh session.
```

## Rubric — `references/rubric.md`

Every line gets a finding, including passes, each with refs. Every line is tagged
with the maturity at which it becomes expected. Suggested coverage:

- Requirement traceability both ways: every `must` covered by a block; every block
  justified by a requirement
- Worst-case power budget margin per rail per mode, against house derating
- Input current at Vin_min versus source limit
- Sequencing versus every part constraint, with each constraint traced to a record
- Brownout, reset, and power-fail behaviour
- Protection on every external interface (ESD, reverse polarity, overvoltage, OCP)
- Resource allocation and spare margin
- Thermal at max ambient for every dissipating element
- Single points of failure
- Rails still `resolution: estimated` (advisory below v1)
- Bus loading, addressing, and voltage-domain consistency
- Test, debug, and programming access on every rail and bus
- Open items with no owner or no resolve-by phase

Import shared severity definitions from `ee-house-rules/severity.yaml` rather than
defining them here.

## The `unanswerable` status

When a check needs an input that does not exist — a thermal check with no part
record — the status is `unanswerable`, not `pass`. Silent passes on missing data are
the exact failure mode this whole design exists to prevent.

## Playback

Findings in sections, worst severity first, stopping between sections. Do not dump
forty findings in one message.

## Gate

Hard: every rubric line has a finding; every finding has non-empty `refs`; schema valid.
Advisory: counts of critical/major findings, reported not blocked.

## Deliverables

Skill directory, rubric, `emit_findings.py`, `gate.py`, 2-3 evals — at least one
using an architecture with a deliberately planted flaw, to prove the rubric catches
rather than rationalises it.

## Definition of done

Zero empty rubric sections. Every finding carries evidence. Missing inputs produce
`unanswerable`, never `pass`.
