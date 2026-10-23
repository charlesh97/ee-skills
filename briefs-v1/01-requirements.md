# Dispatch Brief — `requirements`

**Order 1. Kind: elicitation. The first skill a project touches.**

## Read first
`shared/00-project-context.md`, `01-contracts.md`, `02-skill-template.md`,
**`03-elicitation.md` (essential — this skill is the reference implementation of it)**

## Intent

Turn a vague product idea into a structured, testable requirements set through a
Socratic interview. Every downstream skill traces back to this. The reason it is
its own skill, and comes before any architecture, is that the moment a model starts
designing it stops asking, and the unasked question is what causes the respin.

## Contract

```
Reads:   project.yaml (required)
         <prior project>/requirements.yaml (optional, for derivatives)
Emits:   requirements.yaml, requirements.md
Gate:    scripts/gate.py
Refuses: to propose blocks, part classes, rails, or topologies. The only skill
         that may follow this one is system-architecture.
```

## Build this

**Phase 0 — Scope check.** One board or a system of boards? Multi-board means
decompose first: each board gets its own `requirements.yaml`, plus an interconnect
spec. Do not interview a system as if it were a board.

**Phase 1 — Provenance.** New design, derivative of an existing project, or port of
a reference design? A derivative pre-fills from the prior `requirements.yaml` and
interviews only deltas. This is the single biggest time saver in the skill.

**Phase 2 — Interview.** One question per message, branch-conditional, drawn from
the question bank. See `references/question-bank.yaml` below.

**Phase 3 — Coverage sweep.** Every category reaches `answered`, `deferred`, or
`n/a`. Advisory: unresolved categories warn and append to `open_items.yaml`.

**Phase 4 — Playback.** Present in sections, approve section by section.

**Phase 5 — Emit and commit.** `requirements.yaml` + a human-readable
`requirements.md`, then git commit so the spec enters history rather than chat.

## references/question-bank.yaml — the core asset

A versioned decision tree, not a flat list. Structure each node with the question,
answer type, options with their trade-offs, and which branches each answer opens
or closes.

Categories to cover at minimum: power source and budget; operating modes (see
below); environment (temp, humidity, shock, ingress); connectivity; I/O and
sensing; processing and memory; mechanical envelope and connectors; compliance and
certification; lifecycle and volume; test, debug, and programming access;
manufacturing constraints; cost targets; schedule.

**Operating modes are the spine.** Define them once here (e.g. `off`, `sleep`,
`idle`, `active`, `peak`), because every load in `system.yaml` declares current in
every mode, and budgets, battery life, input current, and thermal all fall out of
that one table. Without it you get a single "typical" current per block and nothing
downstream is checkable. Make this an early, prominent question.

## Scripts

- `emit_requirements.py` — model fills fields, script writes the file
- `diff_requirements.py` — for derivatives, show what changed versus the parent
- `gate.py` — schema validation (hard); coverage completeness, requirements
  missing a `verify` method, and untestable statements (advisory)

## The hard gate, worded for the body

> Do NOT invoke `system-architecture`, propose blocks, name part classes, sketch a
> power tree, or suggest topologies. Designing stops you asking, and this skill
> exists to ask. The only successor is `system-architecture`, and only after the
> coverage sweep and the human's approval of the spec.

## Deliverables

Skill directory, question bank, both schemas, three scripts, 2-3 evals (suggest:
a greenfield battery product, a derivative revision, and a deliberately vague
one-line brief that should trigger the scope check).

## Definition of done

A vague brief produces a testable requirements set. A derivative takes roughly ten
questions. The skill never emits architecture.
