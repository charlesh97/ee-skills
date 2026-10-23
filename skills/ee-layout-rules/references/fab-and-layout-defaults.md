# Fab capabilities

Research, not rules. It covers what JLCPCB and PCBWay publish they can build,
and when a board needs something tighter: fine-pitch vias, via-in-pad, or HDI.
The house values chosen from it are in `../rules/drc.json` (what KiCad enforces)
and `../rules/layout.md` (practice). Change a house value there, not here.

**Sources, fetched 2026-09-28.** Re-fetch before relying on a limit, because
fabs change these pages.
- JLCPCB rigid: https://jlcpcb.com/capabilities/pcb-capabilities
- JLCPCB flex: https://jlcpcb.com/capabilities/flex-pcb-capabilities
- PCBWay: https://www.pcbway.com/capabilities.html
- IPC-2226, *Design Standard for HDI Printed Boards* (Oct 2000 working draft,
  via iNEMI). IPC-2226A is the current revision, and the definitions quoted
  here carried over.

---

## 1. What the houses publish (1 oz outer copper unless stated)

| Feature | JLCPCB rigid | PCBWay | JLCPCB flex (FPC) |
|---|---|---|---|
| Layers | 1–32 | 1–14 standard | 1, 2, 4 |
| Min trace / space | 2L 0.10/0.10; multilayer 0.09/0.09 ("3 mil acceptable in BGA fan-outs") | 0.10 (4 mil) standard | 4/4 mil at 1 oz |
| Trace / space at 2 oz | 2L 0.16/0.16; ML 0.15/0.15 | 6/8 mil (70 µm, normal) | — |
| Min via drill / pad | 0.15 / 0.25 (0.1/0.2 only if board ≤1 mm and ENIG/OSP) | drill 0.15–6.0 | regular 0.3/0.55; extreme 2L 0.10/0.30, 4L 0.15/0.35 (extra cost) |
| Via pad vs drill | pad ≥ drill + 0.10, "+0.15 preferred"; "preferred min via hole 0.2" | min annular ring 0.15 (6 mil) | annular ≥0.25 recommended, 0.18 absolute (PTH) |
| **Via price note** | "0.1 or 0.15 mm hole with any via diameter, and 0.2 or 0.25 mm hole with via diameter < 0.45 mm, will cost more" | — | extreme vias cost extra |
| Via price, as the house reviewer gave it (2026-10-04) | 0.3 mm drill no added cost; 0.2 mm adds cost; 0.15 mm additional cost; 0.1 mm only on boards < 1 mm thick. Stricter than the published note on 0.2 mm with a ≥ 0.45 pad: check the quote before relying on either | — | — |
| PTH annular ring | 2L 0.25 rec / 0.18 min; ML 0.20 rec / 0.15 min; 2 oz 0.254 | 0.15 | as above |
| Via hole-to-hole | 0.2 | ≥11 mil (0.28) for vias ≤0.45 | — |
| Via hole to track | 0.2 | — | — |
| Pad to track | 0.1 (0.09 locally at BGA pads) | — | — |
| SMD pad to pad, different nets | 0.15 | — | — |
| Copper to routed edge | ≥0.2 (V-cut ≥0.4) | 0.25 normal, 0.20 medium | ≥0.3 (laser outline) |
| Soldermask bridge | 0.10 green/colours, 0.13 black/white, 0.20 at 2 oz | 4 mil (0.10) green <2 oz | 0.5 (coverlay) |
| Silkscreen line / text height | ≥0.15 / ≥1.0 mm | 0.15 / 0.8 mm | ≥0.15 / ≥1.0 mm |
| Via-in-pad (filled + capped) | epoxy or copper paste, via Ø 0.15–0.55; **default on 6L+** | listed, no dims | — |
| Blind / buried / HDI | 1-, 2-, 3-step; laser blind 0.075–0.15; HDI trace 3/3 mil | 1+N+1 normal; any-layer medium; 2+N+2 high difficulty | — |
| Impedance control | 4L+, ±10% (±5% on request) | ±10% (±5 Ω at ≤50 Ω) | **not supported** (width only) |
| Finished-thickness tolerance | ±10% ≥1 mm; ±0.1 mm <1 mm | same | — |
| Flex bend radius | — | — | ≥6× thickness 1L, ≥10× multilayer (dynamic 10–15×) |

---

## 2. HDI: what it is, what it isn't, and when a board needs it

**HDI means microvias.** IPC-2226 defines a microvia as a formed *blind or
buried* via **< 0.15 mm in diameter with a pad < 0.35 mm**. The revision says a
microvia has an aspect ratio of ≤ 1:1 and spans at most 0.25 mm, so it
connects one layer to the next. These vias are laser-drilled into a thin
dielectric that is laminated onto a core, one "step" (build-up layer) at a
time: **sequential lamination**. IPC-2226 sorts HDI boards by how many
build-up layers they have:

- **Type I, 1[C]0 or 1[C]1:** one microvia layer on one or both sides of a
  conventional core, plus through vias. JLC "1-step", PCBWay "1+N+1".
- **Type II:** Type I, plus buried vias in the core.
- **Type III, ≥2[C]≥0:** two or more microvia layers on a side, stacked or
  staggered. JLC "2/3-step", PCBWay "2+N+2" (high difficulty).
- Types IV–VI: passive-substrate, coreless and alternative constructions.
  Rare for us.

**What is *not* HDI, even though it's fine-featured:**
- **A 0.15/0.3 mm through via.** It is mechanically drilled, through all
  layers, on a standard stackup. IPC calls anything drilled over 0.15 mm a
  plain via. At JLC it costs a little extra, but it isn't HDI.
- **Via-in-pad, filled and capped** (IPC-4761 Type VII). It is still a through
  via, filled with epoxy or copper and plated over so the pad is flat. It lets
  a via sit *in* a BGA land instead of beside it, and JLC does it by default
  on 6+ layers. It costs a process step, but it isn't HDI.
- 3–3.5 mil traces in a BGA fanout. That is tight etching, not a build-up.

**When a board needs which.** For a BGA or WLCSP, the question is whether a via
fits in the diagonal between four lands (a "dog-bone" fanout), and whether a
trace fits between two lands. Computed for typical NSMD lands, about half the
pitch, with copper gap on each side of the via. JLC needs ≥0.09–0.10; 0.15 is
comfortable.

| Pitch (land) | Dog-bone via 0.3/0.6 | 0.2/0.45 | 0.15/0.3 | One 0.10 trace between lands, spacing | What it takes |
|---|---|---|---|---|---|
| 1.0 (0.45) | 0.18 | 0.26 | 0.33 | 0.225 | standard tech |
| 0.8 (0.40) | 0.07 ✗ | 0.14 | 0.22 | 0.150 | standard, with 0.2/0.45 or 0.15/0.3 vias |
| 0.65 (0.30) | 0.01 ✗ | 0.09 marginal | 0.16 | 0.125 | 0.15/0.3 vias (the fine-via tier) |
| 0.5 (0.25) | ✗ | ✗ | 0.08 ✗ | 0.075 ✗ | **via-in-pad** for every inner ball; outer two rows escape on the surface |
| 0.4 (0.20) | ✗ | ✗ | ✗ | ✗ | **via-in-pad on a thin board (≤1 mm, ENIG) for a small array; laser microvias (HDI Type I) otherwise** |

Rules of thumb that follow from the table:
- **≥0.65 mm pitch never needs HDI.**
- **0.5 mm pitch needs via-in-pad, not HDI.** The exception is an array deep
  enough (4+ rows) that a through via in every inner land blocks every
  inner-layer routing channel. Then microvias, which don't pass through the
  inner layers, give those channels back.
- **0.4 mm WLCSP:** a small array (e.g. a 4×4) escapes with
  through via-in-pad. A large one is HDI.
- **HDI also becomes necessary** when the number of routing channels the
  stackup offers can't carry the nets, and more through-via layers won't help
  because the vias themselves block the channels. It also applies when the
  board is too thin for a through via's aspect ratio. Otherwise it is cost with
  no benefit. Every build-up step is a lamination cycle, and it roughly
  doubles lead time and price per step.

---
