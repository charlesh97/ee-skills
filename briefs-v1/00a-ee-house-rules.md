# Dispatch Brief — `ee-house-rules`

**Wave 0. Kind: data. Everything else reads this. Build before anything else.**

## Read first
`shared/00-project-context.md`, `shared/01-contracts.md`, `shared/02-skill-template.md`

## Intent

The canonical house EE standard. This is the artifact that actually produces
consistency across boards; the skills are just machinery that applies it.
Ships as a **separate repo** from the skills so product lines can pin or fork the
rules without forking the logic.

Design guidelines are data, not a skill. If they live inside a skill body they get
forked every time a skill is forked.

## OPEN QUESTION 1 — resolve with the human first

Does this ship as a skill other skills read, or as a plain data repo loaded by
path? A data repo is more robust: no context budget consumed, no risk of the model
paraphrasing a standard instead of applying it. A skill is easier to deploy.
**Draft the content model either way; it is identical. Do not pick for them.**

## Build this

A versioned, schema-validated data repo. Machine-readable where a script consumes
it, prose where a human or a rubric consumes it.

```
ee-house-rules/
|-- VERSION                        semver; project.yaml pins it
|-- schemas/                       JSON Schema for every file below
|-- naming.yaml                    refdes prefixes, net naming, sheet naming,
|                                  library naming, file naming
|-- parts/
|   |-- approved.yaml              blessed MPNs by function, with rationale
|   |-- generics.yaml              passive classes: value/package/voltage/
|   |                              tolerance/dielectric rules
|   `-- prohibited.yaml            banned parts and why (EOL, bad experience)
|-- symbols.yaml                   pin ordering/grouping, field set, graphic style
|-- footprints.yaml                IPC density class, courtyard, silkscreen,
|                                  pin-1 marker, thermal relief, paste rules
|-- stackups/                      named stackups with impedance targets
|-- netclasses.yaml                default classes, widths, clearances
|-- dru/                           DRC profiles per fab and per layer count
|-- derating.yaml                  voltage/current/power/thermal derating by
|                                  maturity level
|-- maturity.yaml                  what v0 / v1 / production MEAN here
|-- severity.yaml                  critical / major / minor / info definitions
`-- rubrics/                       shared rubric lines the review skills import
```

## Two files that need the most care

**`maturity.yaml`** is load-bearing. Every gate check and rubric line is tagged
with the maturity at which it becomes expected, and gates are advisory below that.
Get the definitions from the human in their own words; do not invent them. Draft a
structure like:

```yaml
levels:
  v0:
    intent: "bring-up board; prove the concept works"
    expected: [erc_clean, power_budget_present, bypass_caps]
    not_expected: [thermal_analysis, emc_review, second_sourcing, dfm_full]
  v1: {...}
  production: {...}
```

**`severity.yaml`** must be unambiguous enough that three different review sessions
grade the same finding the same way. Include a worked example per level.

## What you cannot generate

The *content* is the adopter's actual standards and no agent can invent it. Your
job is the schema, the structure, the validator, and a well-commented starter set
clearly marked as placeholder. Ask the human for whatever exists today in any
form: a naming doc, a preferred-parts spreadsheet, standard stackups, an old
review checklist. If the honest answer is "it's in people's heads," say so and
propose an extraction interview as its own task.

## Deliverables

1. The repo structure above with JSON Schemas for every file.
2. `validate.py` — validates the whole repo, exits nonzero on schema violation.
3. A resolver module other skills import: given a `house_rules_version` from
   `project.yaml`, load and return the rules. Pinning must be real.
4. A starter set with every placeholder value clearly marked `PLACEHOLDER`.
5. An extraction interview plan for pulling real standards out of the team.

## Definition of done

A skill can pin version 2.3.1, load it, and get the same answer next month.
Placeholder values are impossible to mistake for real ones.
