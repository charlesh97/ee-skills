# SKILL.md Template and Directory Layout

Every skill in this plugin uses the same shape. Uniformity is what allows these to
be authored in parallel sessions and still compose.

## Directory layout

```
skill-name/
|-- SKILL.md              required
|-- schemas/              JSON Schema for each artifact this skill emits
|-- scripts/
|   |-- gate.py           validator; see exit-code contract below
|   `-- *.py              all deterministic emission and arithmetic
|-- references/           rubrics, house-rule excerpts, format notes, question banks
`-- evals/
    `-- evals.json        2-3 realistic test prompts
```

## Frontmatter

```yaml
---
name: skill-name
description: >
  What it does AND when to trigger. This is the only triggering mechanism, so put
  all "when to use" information here, not in the body. Claude under-triggers
  skills, so be somewhat pushy: name the phrases and contexts that should invoke
  it, including ones where the user would not say the skill's name.
---
```

For `release` and any other skill that must NOT fire automatically, include an
explicit anti-trigger sentence in the description.

## The Contract block

**The first thing in every SKILL.md body, before any prose.** This is what makes
the chain deterministic and what a linter can check.

```markdown
## Contract

Reads:   power_tree.yaml (required), parts/*.json (optional), project.yaml (required)
Emits:   netlist.yaml, conforming to schemas/netlist.schema.json
Gate:    scripts/gate.py
Refuses: if any required input is missing. Do not proceed and do not synthesize it.
         Report which file is missing and which skill produces it.
```

## Gate exit-code contract

`scripts/gate.py` is called at the end of every invocation and prints a report.

| Exit | Meaning | Behaviour |
|---|---|---|
| 0 | clean | continue |
| 1 | **structural failure** | stop. Malformed file, schema violation, dangling reference. |
| 2 | **advisory warnings** | continue, print warnings, append each to `open_items.yaml` |

Gates are advisory on completeness and hard on structure. See Principle 6 in
`00-project-context.md`. Every advisory warning must carry the maturity level at
which it would become expected, so a v0 board does not drown in production-grade
nags.

## Producer template (generative and constraint-authoring skills)

```markdown
---
name: ...
description: ...
---

# Skill Name

## Contract
[the block above]

## Preconditions
Load each required input. If one is missing, stop and name the skill that
produces it. Read project.yaml first; `maturity` sets how deep to go.

## Phase 1 - <name>
...

## Phase 2 - <name>
...

## Emission
Fill the structured fields, then call scripts/emit_*.py. Never hand-write the
artifact; the script owns formatting so output is byte-identical across runs.

## Gate
Run scripts/gate.py. On exit 1, fix and re-run. On exit 2, report warnings to the
user and confirm they are acceptable at this maturity before continuing.

## Handoff
Name the next skill and what it will read.
```

## Reviewer template (judgement skills)

```markdown
---
name: ...
description: ...
---

# Skill Name

## Contract
[the block above]

## Fresh context requirement
This skill evaluates artifacts, not conversations. If the current session produced
the artifact under review, say so and recommend re-running in a new session. The
session that drew the schematic is the worst reviewer of it.

## Preconditions
[what must exist; what to do about gaps -- usually run the producing skill first]

## Rubric
references/rubric.md. Walk EVERY line. Emit a finding for every line including
passes. An empty section is a failure, not a clean bill.

## Evidence requirement
Every finding carries a refdes, net name, or file reference. A finding with no
`refs` is invalid and the gate rejects it.

## Status values
pass | fail | warn | n/a | unanswerable
Use `unanswerable` when a required input is missing. Never silently pass.

## Playback
Present findings in sections, worst severity first, and stop for the user between
sections. Do not dump forty findings in one message.

## Emission
scripts/emit_findings.py -> findings.yaml

## Gate
scripts/gate.py: every rubric line has a finding; every finding has refs.
```

## Writing style for skill bodies

- Imperative form.
- Explain *why* a step matters rather than stacking MUSTs. A model that
  understands the reason generalises; one following a rule does not.
- Keep SKILL.md under ~500 lines. Push detail into `references/` with clear
  pointers about when to read each file.
- For reference files over ~300 lines, add a table of contents.
- Do not hard-code house rules into the body. Read them from `ee-house-rules`.

## Evals

`evals/evals.json`, 2-3 realistic prompts of the kind an engineer would actually
type. Prompts must be substantive enough that a model would benefit from the
skill; trivial one-step prompts do not trigger skills regardless of description
quality.

```json
{
  "skill_name": "power-architecture",
  "evals": [
    {"id": 1,
     "prompt": "Here's the block diagram for the sensor node. Work up the power tree.",
     "expected_output": "power_tree.yaml with per-mode rollups and resolution flags",
     "files": ["system.yaml", "requirements.yaml", "project.yaml"]}
  ]
}
```

Golden reference designs from two or three completed boards will be added later
and run as regression evals on every skill change.
