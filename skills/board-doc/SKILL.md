---
name: board-doc
description: >
  Writes the documentation page for a KiCad 10 board — the page a person reads
  when they are handed the board and need to use it. Load it for "document this
  board", "board doc", "write the page for this board", "board README", "Notion
  page for the board", "pinout for this board", "connector pinout", "render the
  board for the docs", "block diagram of this board", "which revision is this
  board pinned to", "update the board doc for rev N". Generates most of the page
  from the .kicad_pcb: top and bottom renders, a pinout drawing and net table
  per connector, the spec table, a Mermaid block diagram seeded from the
  netlist, and the git revision the board files are pinned to. Reads git but
  never writes to it, and never modifies a KiCad file.
---

# Board doc

Seven short sections. A board page earns its keep by answering *"I have been
handed this board, how do I use it"* — what it is, what it looks like, what
plugs into it, how it is wired, what is broken, and where the files are.
Everything else belongs in the design spec or the review findings. A page long
enough to skim past is a page nobody reads.

Almost all of it is generated. Four scripts read the `.kicad_pcb` and produce
the renders, the pinouts, the spec table, the block diagram and the revision
pin. What is left for a person is four lines of prose and the errata table —
short enough that people actually finish it, and the generated half cannot
drift from the board.

## Contract

```
Reads:   <name>.kicad_pcb, sibling *.kicad_sch (for the revision pin only)
         git, read-only
         existing docs/notion/<board>.md, if there is one
Writes:  docs/notion/<board>.md
         docs/notion/assets/<board>/rev<N>/{board_top.png, board_bottom.png, <refdes>.svg}
Stops if: the .kicad_pcb is missing or does not parse
          no revision number and status were given
```

Never commits, stages, branches, pushes, or writes any KiCad file. `git log`,
`git status` and `git config` are the only git commands it runs.

## Before you start

1. Get the revision number and its status. Status comes from a fixed
   vocabulary: `concept → in design → routed → fabbed → bring-up → working →
   retired`. The vocabulary is only useful if it is used exactly.
2. Read `references/template.md`. It is the canonical section list and order.
3. If `docs/notion/<board>.md` already exists, this is an **update**. Read it
   first. Prior revision sections are read-only — append a new `## Rev N`
   section, never edit an old one. A shipped revision is a record of what was
   built.

## Steps

### 1. Generate

```bash
S=<this skill>/scripts
A=docs/notion/assets/<board>/rev<N>

python3 $S/render.py <board>.kicad_pcb --out $A
python3 $S/pinout.py <board>.kicad_pcb --out $A --asset-path assets/<board>/rev<N>
python3 $S/facts.py  <board>.kicad_pcb      # Spec table + the revision pin
python3 $S/blocks.py <board>.kicad_pcb      # Mermaid seed for Architecture
```

- **`render.py`** — top and bottom via `kicad-cli pcb render`. Resolves
  `kicad-cli` from PATH and then the macOS KiCad.app path, because a default
  macOS install does not put it on PATH. Sizes the frame to the board outline
  and derives the zoom from its aspect ratio, so a long thin flex and a squat
  rigid board both fill their image.
- **`pinout.py`** — one SVG per connector plus the whole **Connectors** section
  on stdout, tables included.
- **`facts.py`** — board size, stackup and mounting holes from the board file;
  the revision pin from git.
- **`blocks.py`** — a Mermaid seed. See the rule below: it is a starting point,
  not the diagram.

`render.py` and `pinout.py` refuse to overwrite an existing asset. That is the
freeze rule, not a bug; pass `--force` when you mean it.

### 2. Check the pin before you write anything

`facts.py` prints the last commit that touched this board's files, and prints a
loud **DIRTY** block if any of them have uncommitted changes. If it is dirty,
**stop and say so.** The page would describe files that exist only on this
machine, and would name a commit that does not contain them. Ask whether to
commit first or carry on knowingly.

### 3. Write the short human part

Only these. Everything else is generated or copied.

- **At a glance** — status, date, purpose in one line, what hosts it, the
  firmware path.
- **Board** — the one line the renders cannot show: flex regions, stiffeners,
  what mounts where.
- **Architecture** — one or two sentences, then the edited diagram.
- **Known issues & errata** — every entry keeps its ID (E1, E2 …) for the life
  of the board, so a later revision can cite the row that caused a change.
  Severity is `blocker`, `annoyance`, or `cosmetic`. If `findings/` or
  `open_items.yaml` exist from the review skills (shape in
  `references/findings.md`), propose entries from them
  rather than asking cold.

**Files** you fill in yourself by looking. Do not ask for paths you can find.

### 4. Assemble and report

Write the page from `references/template.md`, then print every placeholder still
unfilled. Do not quietly leave a `<...>` in the page and say nothing.

## Rules

**Never invent a value.** Every number on the page is extracted from the board
file, read out of a real file, or told to you by a person. If you cannot get a
value, leave the placeholder and list it at the end. A board page that is
confidently wrong is worse than one with a visible gap, because the gap gets
filled and the wrong number gets designed against.

**The seed is not the diagram.** `blocks.py` draws what is connected; it cannot
know what matters. Five identical AFEs come out as five identical blocks, and
the human version says "AFE ×5". Always collapse the repetition, name the buses,
and order it so it reads left to right. Shipping the raw seed is the one way
this skill produces something worse than hand-writing it.

**Pin the board, not the repo.** The revision is the last commit touching this
board's own files. Two boards in one repo sit at different commits, and `HEAD`
describes neither. `facts.py` already does this — do not substitute `HEAD`.

**The freeze rule.** Once a revision's status is past `routed` — fabbed,
bring-up, working, retired — its assets are not regenerated. A render of the
current board file presented as rev 0, after rev 0 was fabbed, is a quiet lie
about what was built. The scripts enforce this by refusing to overwrite; hold
the line when someone asks you to `--force` without a reason.

**The drawings carry pin numbers; the tables carry nets.** Deliberate, and it
should stay that way. Net names on these boards run to `INT4_SENSOR_OUT`, which
on a 2.54 mm header means either overlapping labels or leader-line machinery
that looks different on every board. Splitting them keeps every drawing legible
and identical in style across boards, which is the whole reason there is a
house template.

**Direction and voltage domain are not extractable.** `pintype` reads `passive`
on headers, so the board file cannot tell you which way a signal goes. That is
what the Note column is for, filled by a person, and it is the column most worth
filling — it is what someone plugging a cable in actually needs.

## Files

```
SKILL.md
references/template.md     the canonical page — section list and order
scripts/render.py          top + bottom renders via kicad-cli
scripts/pinout.py          per-connector SVG + net table
scripts/facts.py           spec table + the git revision pin (read-only)
scripts/blocks.py          Mermaid block diagram seeded from the netlist
scripts/kx.py              KiCad 10 s-expression parser (vendored, no dependencies)
```
