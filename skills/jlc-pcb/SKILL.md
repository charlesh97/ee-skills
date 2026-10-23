---
name: jlc-pcb
description: >
  Everything JLCPCB publishes it can build and assemble, in one list: rigid board limits
  (layers, thickness, copper, drills, vias, annular rings, trace and space by copper
  weight, hole spacing, soldermask, silkscreen, finish, outline, V-cut, panels,
  castellation, plated edges, backdrill), HDI (blind and buried vias, steps), flex (FPC
  vias, coverlay, stiffeners, bend radius), standard stackups, assembly (Economic and
  Standard PCBA, minimum package and pitch, BGA), and what costs extra, with the fee
  table. Load it for "can JLC build this", "JLC capabilities", "what's JLC's minimum
  via / drill / trace / spacing", "does this cost extra at JLC", "is 0.15 drill
  standard", "what annular ring does JLC need", "2 oz rules at JLC", "JLC stackup",
  "JLC flex", "JLC assembly limits", "Economic or Standard PCBA", "extended part fee",
  or any time a board, rule or review number has to sit inside what JLC builds.
  The house's chosen values stay in ee-layout-rules; this is what the fab offers.
---

# JLCPCB capabilities

`references/capabilities.md` is the one list: every published JLCPCB limit for rigid,
HDI and flex boards, the standard stackups, assembly, and the fees, each with the page
it came from and the date it was read. Read it whenever a number has to fit JLC.

## How to use it

- **Look it up, don't recall it.** Quote the row from the list, with its date. If the
  list doesn't have it, fetch the source page in the list's header and add the row.
- **Re-fetch before relying on a limit that is close.** JLC changes these pages. When a
  design sits within 10% of a limit, or a review hangs on one, re-read the page, update
  the row and its date, and say so.
- **Fab limit, not house value.** The list says what JLC can build. What the house
  chooses inside it (Board Setup floors, net classes, the via menu, the via current
  table) is in `ee-layout-rules`: `rules/drc.json`, `rules/layout.md` L-32 for vias,
  and `references/fab-and-layout-defaults.md` for the JLC/PCBWay comparison and HDI
  reasoning. Change a house value there, not here.
- **Cost is part of the answer.** Many limits are buildable but priced: a 0.15 mm via
  drill, a 0.2/0.25 drill with a pad under 0.45 mm, a 0.1 mm drill, HDI steps, tighter
  impedance, 2 oz on multilayer. Say which side of the price line a choice falls.
- **Copper weight changes the limits.** Trace and space, annular ring and mask bridge
  all grow at 2 oz. Read the stackup's outer copper before applying a 1 oz number.
- **Assembly has its own limits.** Economic PCBA is narrower than Standard (packages,
  pitch, layers, thickness, finishes). Check which one the board is quoted under.

## Related

- Part lookup (LCSC code, basic or extended, JLC stock):
  `../schematic-capture/scripts/jlc.py`, rule D-46 in
  `../ee-schematic-rules/rules/schematic.md`, review checks E-7/E-8 in schematic-review.
  `jlc.py` uses JLC's unpublished parts endpoint; if it stops answering, fix it, and
  never fall back to a part code from memory.
- Gerber, drill, BOM and CPL files in JLC's formats: the release skill's
  `references/jlcpcb-package.md`, when that skill is installed.
