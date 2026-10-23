# Project Context — EE AI-Assisted Design Skills

Paste this file into every skill-authoring session before anything else. It is the
decision record. Do not re-litigate these decisions; if a brief seems to conflict
with them, stop and ask the human.

## Goal

A versioned plugin of skills, workflows, and documentation used across all
AI-assisted EE board designs that adopt it. The point is **consistent output**:
two engineers running the same phase on the same inputs should get materially the
same artifact. EDA tool is KiCad.

## Principle 1 — Three kinds of work, never mixed in one skill

- **Generative** — the AI writes an artifact (symbols, footprints, netlists, DRU
  files, BOMs, docs).
- **Judgement** — the AI evaluates against a rubric (schematic review, layout
  review, architecture review).
- **Constraint authoring** — the AI encodes intent for a human or tool to execute
  (stackup, net classes, placement rules, critical-net constraints).

Mixing these in one skill is the main cause of inconsistent output. Layout is
constraint authoring plus judgement only. **The AI does not place parts or route
traces.** An LLM writing `.kicad_dru`, net classes, and a placement spec, then
triaging DRC output, is strong. An LLM placing components is not.

## Principle 2 — Sequence is enforced by data, not by instructions

A model skips a step written as a bullet. It cannot skip a step whose output the
next step loads from disk. Every skill declares what it reads; if a required input
is missing, it stops and says so rather than synthesizing it.

## Principle 3 — Anything that should be byte-identical is a script

File emission, BOM formatting, gerber generation, netlist extraction, and **all
arithmetic** are Python. The model supplies judgement and fills structured fields.
This is where consistency across boards actually comes from.

## Principle 4 — Review runs in a fresh context

The session that produced an artifact is the worst reviewer of it. Review skills
receive the artifacts and the rubric, never the design conversation.

## Principle 5 — Rubrics require evidence per line, including passes

Every rubric line emits a finding record with a refdes or file reference, even
when it passes. An empty section is a failure, not a clean bill. This is what
kills the "looks good to me" failure mode.

## Principle 6 — Gates are ADVISORY, with one exception

The human's decision: walk every step, skip the ones a given maturity level does
not need. So:

- **Completeness is advisory.** Missing numbers, unresolved estimates, skipped
  analyses -> warn loudly, log to `open_items.yaml`, continue.
- **Structural validity is a hard error.** Malformed YAML, schema violations,
  dangling references (a load pointing at a rail that does not exist) -> stop.
  The next skill cannot read it, and continuing produces silent garbage instead
  of a stopped run.

Because nothing blocks, **the record is what preserves consistency**. Every skip
is logged with a reason and the maturity level that justified it. `release`
prints the full ledger. The goal is "we knowingly skipped thermal analysis
because this is a v0 bring-up board," never "nobody remembers."

## Principle 7 — Design guidelines are data, not a skill

House standards live in `ee-house-rules`. If guidelines live inside a skill body,
they get forked every time a skill is forked.

## Principle 8 — Elicitation follows the superpowers `brainstorming` pattern

One question per message, multiple choice preferred, options with trade-offs and
a recommendation where a decision is a choice rather than a constraint, design
played back in sections for approval, hard gate against running ahead into the
next phase. See `03-elicitation.md`.

## Sourcing decisions (confirmed by the human)

- **JLC assembly first.** Selection prefers parts assemblable at JLCPCB; basic vs
  extended part status is a real screening criterion.
- **LCSC + web search are the primary part search path.**
- **DigiKey** is used where it can be navigated; treat as a secondary source.
- There are **no DigiKey / Mouser / Octopart MCP connectors available**. Part
  search is scripts plus keys plus web search, not connectors. Do not design
  around a connector that does not exist.
- Octopart data is now behind the Nexar GraphQL API (OAuth2; free tier capped at
  roughly 1000 results/month, counted per part returned). Suitable for
  cross-distributor stock/price/alternates checks, not as a primary search.

## The skill roster (14)

| Order | Skill | Kind |
|---|---|---|
| 0 | `ee-house-rules` | data |
| 0 | `kicad-files` | mechanics |
| 1 | `requirements` | elicitation |
| 2 | `system-architecture` | generative |
| 3 | `power-architecture` | generative |
| 4 | `part-select` | generative |
| 5 | `part-spec` | generative |
| 6 | `architecture-review` | judgement |
| 7 | `symbol-footprint` | generative (acquire-then-verify) |
| 8 | `schematic-capture` | generative |
| 9 | `schematic-review` | judgement |
| 10 | `layout-constraints` | constraint authoring |
| 11 | `layout-review` | judgement |
| 12 | `release` | generative, human-checkpointed |

Steps 3, 4, and 5 form a convergence loop, not a linear sequence.

## Open questions — confirm with the human before writing code

These were not settled at dispatch time. Each brief flags where it depends on one.
Draft around them; do not guess silently.

1. **`ee-house-rules` deployment** — a skill that others read, or a plain data repo
   loaded by path? Data repo is more robust (no context budget, no paraphrasing of
   standards); skill is easier to deploy.
2. **KiCad version** — 7, 8, or 9. The s-expression format moved between them.
3. **Power topology profile** — single-input DC, or multi-source with battery / USB-PD
   / load switching? The second makes `power_tree.yaml` a state-dependent graph.
4. **Schematic source of truth** — direct `.kicad_sch` generation vs a text HDL
   (SKiDL / atopile) as canonical. Being decided in a separate session. Only
   `schematic-capture` is blocked on this.

## Rules for skill-authoring sessions

1. **Do not invent interchange files.** The frozen list is in `01-contracts.md`.
   If you need a file that is not on it, stop and report to the human.
2. **Do not change another skill's contract.** If your skill needs a field another
   skill emits, request it; do not assume it.
3. **Follow the SKILL.md template** in `02-skill-template.md` exactly. Uniformity
   is what lets these be authored in parallel.
4. **Log every assumption** you make about house rules. Your assumption list is the
   human's review checklist.
5. Follow the `skill-creator` skill's conventions for SKILL.md structure,
   progressive disclosure, and eval authoring.
