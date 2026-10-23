# EE Skills Dispatch Pack

Fourteen skill-authoring briefs plus the shared context they all depend on. Each
brief is written to be handed to a fresh session that has none of the design
conversation behind it.

## How to use

For each skill you want built, start a new session and give it:

1. `shared/00-project-context.md` — the decision record (always)
2. `shared/01-contracts.md` — the eleven frozen interchange files (always)
3. `shared/02-skill-template.md` — SKILL.md shape and gate exit codes (always)
4. `shared/03-elicitation.md` — only for briefs 01, 02, 03, 04
5. The one brief from `briefs/`

Opening instruction that works:

> You are authoring one skill in a KiCad EE design plugin. Read the four attached
> shared documents first, then the brief. Follow the SKILL.md template exactly. Do
> not invent interchange files — if you need one that is not on the frozen list,
> stop and ask me. Log every assumption you make about house rules; that list is
> my review checklist. Ask me questions one at a time as you go.

## Build order, not project order

The briefs are numbered by when a skill runs on a project. Build them in a
different order — foundation first, then the two that prove the pattern on low
risk:

| Wave | Build | Why |
|---|---|---|
| 0 | `00a-ee-house-rules`, `00b-kicad-files` | everything reads these; cannot be parallel with consumers |
| 1 | `07-symbol-footprint`, `09-schematic-review` | self-contained and mechanically verifiable; highest value and read-only |
| 1 | `01-requirements`, `05-part-spec` | independent, no upstream artifacts needed |
| 2 | `02`, `03`, `04`, `06` | the architecture loop; 03/04/05 authors should talk to each other |
| 2 | `10`, `11`, `12` | |
| 3 | `08-schematic-capture` | blocked on the HDL fork; hardest; build last |

Wave 0 is not a parallel task. Everything downstream reads it.

## Four open questions

Every brief that depends on one flags it. Do not let a session guess silently.

1. **`ee-house-rules` deployment** — skill that others read, or data repo loaded by
   path? (blocks brief 00a's final form)
2. **KiCad version** — 7, 8, or 9? (blocks brief 00b entirely)
3. **Power topology profile** — single-input DC, or multi-source with battery /
   USB-PD / load switching? (blocks brief 03's schema)
4. **Schematic source of truth** — direct `.kicad_sch` vs text HDL. Being decided
   separately. (blocks brief 08 only)

Questions 1 and 2 should be answered before wave 0 starts. Question 3 before wave 2.

## Also needed, and no agent can produce it

- **Whatever house rules exist today**, in any form: naming conventions, a
  preferred-parts spreadsheet, standard stackups, an old review checklist. This is
  the long pole on real consistency.
- **Maturity definitions** — what v0, v1, and production actually mean for
  your boards, in your words. Every gate check and rubric line is tagged against these.
- **Two or three completed boards** as golden references for regression evals.

## What each session returns

- A complete skill directory per `shared/02-skill-template.md`
- 2-3 eval prompts in `evals/evals.json`
- An explicit list of every assumption it made about house rules
- A list of anything it wanted that was not on the frozen contract list
