# JLCPCB capabilities: the one list

What JLCPCB publishes it can build and assemble. Fab limits, not house values: the house
chooses inside these in `ee-layout-rules`. All lengths in mm unless stated. A value in
"quotes" is JLC's own wording. **$** marks a published extra cost.

**Sources, all read 2026-10-23.** Re-read the page before relying on a limit a design
sits close to, update the row and the date here, and note what changed.
- Rigid: https://jlcpcb.com/capabilities/pcb-capabilities
- HDI: https://jlcpcb.com/capabilities/hdi-pcb-capabilities
- Flex: https://jlcpcb.com/capabilities/flex-pcb-capabilities
- Assembly: https://jlcpcb.com/capabilities/pcb-assembly-capabilities
- Assembly fees: https://jlcpcb.com/help/article/pcb-assembly-price (page dated 2026-10-22)
- Stackups: https://jlcpcb.com/impedance

---

## 1. Rigid boards

### Material, size and thickness

| Item | Limit |
|---|---|
| Layers | 1–32. Impedance control on 4, 6, 8 … 32 layers. FAQ: 1–6 layers optimal, over 10 layers gets a stackup review |
| Material | FR-4, grade A laminates (Nan Ya, KB, Shengyi and others); also aluminium core (1L), copper core (1L), Rogers/PTFE (2L, 1 oz) |
| Dielectric constant | 2L FR-4 4.5; prepreg 7628 4.4, 3313 4.1, 2116 4.16, 1080 3.91; core 4.6; soldermask 3.8 |
| Max size (≥0.8 thick) | 1L 606×510; 2L 670×600 (extended 1020×600); 4L 663×593 (extended 1016×596); 6L+ 656×586; thinner FR-4 599×497; Rogers/PTFE 590×438; aluminium 602×506; copper core 480×286 |
| Min size (≥0.6 thick; thinner is manual review) | FR-4/Rogers/PTFE 3×3; castellated or plated edges 10×10; aluminium/copper core 5×5 |
| Outline tolerance | ±0.1 precision / ±0.2 regular CNC routing; V-score ±0.4 |
| Thickness | 0.4–4.5. FR-4: 0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0; 2.5 and above only on 12+ layers (FAQ says 0.4–3.2 standard) |
| Thickness tolerance | ≥1.0: ±10%; <1.0: ±0.1 |
| Outer copper (finished) | 2L: 1, 2, 2.5, 3.5, 4.5 oz. **Multilayer: 1 or 2 oz only** (FAQ says heavy copper up to 3 oz) |
| Inner copper (finished) | 0.5, 1, 2 oz; **0.5 oz by default** |
| Soldermask colours | green, purple, red, yellow, blue, white, black (LPI) |
| Surface finish | HASL leaded / lead-free, ENIG, OSP. No OSP on single-sided FR-4, FPC or aluminium. Aluminium is HASL only. **No HASL** on FR-4/HDI with 6+ layers, boards ≤0.4 thick, high-frequency, copper-core or flex |

### Drills and holes

| Item | Limit |
|---|---|
| Drill range | 1L 0.3–6.3; 2L and multilayer 0.15–6.3. Holes ≥6.3 are routed. Aluminium core min 0.65, copper core min 1.0 |
| 0.1 drill | only on boards ≤1.0 thick with ENIG or OSP; **$** "more costly" |
| PTH tolerance | +0.13 / −0.08; press-fit ±0.05 (finished 0.55–2.0, multilayer ENIG round holes, call them out in the remarks) |
| Hole position tolerance | ±0.075 |
| Average hole plating | 18 µm |
| Recommended PTH | ≥0.5 (keeps mask and tin out of the hole) |
| Min NPTH | 0.50 (draw on a mechanical or keep-out layer) |
| Plated slot | min width 2L 0.5, multilayer 0.35; drawn as a pad, length ≥2× width; tolerance +0.13/−0.08 |
| Non-plated slot | min width 1.0 (outline on GM1/GKO); tolerance ±0.2 |
| Rectangular holes or slots with sharp corners | not supported |
| Pad (PTH) hole-to-hole | 0.45 |
| Countersink, blind slot, backdrill | available (below) |
| Blind slot | width ≥1.0, depth ≥0.2, annular ≥0.3, NPTH safety ≥0.2, remaining thickness ≥0.2; 2–32 layer FR-4 ≥0.8 thick |
| Backdrill | 4–32 layer FR-4 ≥0.8 thick; through hole 0.2–0.5, epoxy filled after; backdrill about 0.2 over the hole; depth per layer; dielectric ≥0.15; safety ≥0.2 |
| Castellated holes | hole ≥0.5, hole to edge ≥1.0, hole to hole ≥0.5; board ≥10×10 and ≥0.6 thick |
| Plated edges | board ≥10×10, ≥0.6 thick, ENIG only, at least 3 breaks in the plating for support tabs |

### Vias

| Item | Limit |
|---|---|
| Min via drill / pad | 0.15 / 0.25 (0.1 / 0.2 only ≤1.0 thick with ENIG/OSP). 1L (NPTH only) 0.3 / 0.5 |
| Pad vs drill | "Via diameter should be 0.1mm (0.15mm preferred) larger than Via hole size" |
| Preferred min via drill | 0.2 |
| **$ Via price** | "0.1mm or 0.15mm hole size with any size via diameter, and 0.2mm or 0.25mm hole size with via diameter less than 0.45mm, will cost more." Pick the matching via option when ordering. So 0.3 drill costs nothing extra at any pad, and 0.2/0.25 drills cost nothing extra with a pad ≥0.45 |
| Via hole-to-hole | 0.2 |
| Via hole to track | 0.2; inner layers: via hole to copper 0.2 |
| Aspect ratio | not published (a 0.15 drill is offered on 1.6 multilayer, about 10.7:1) |
| Plugged (soldermask-filled) vias | ≤0.5 diameter, no mask opening on either side, ≥0.35 from other openings |
| Via-in-pad, filled and capped | epoxy or copper paste, via 0.15–0.55, plated over; copper paste is the default on 6+ layers (choose it for heat) |
| Vias in BGA pads | filled and plated over |

### Traces, pads and spacing

| Item | Limit |
|---|---|
| Min trace / space, 1 oz | 1–2L 0.10/0.10 (4/4 mil); multilayer 0.09/0.09 (3.5/3.5 mil), "3 mil is acceptable in BGA fan-outs" |
| Min trace / space, 2 oz | 2L 0.16/0.16 (6.5 mil); **multilayer 0.15/0.15 (6 mil)** |
| Min trace / space, heavier (2L) | 2.5 oz 0.20/0.20; 3.5 oz 0.25/0.25; 4.5 oz 0.30/0.30 |
| Trace width tolerance | ±20% |
| PTH annular ring | 2L 1 oz: 0.25 recommended, 0.18 absolute; multilayer 1 oz: 0.20 recommended, 0.15 absolute; **2 oz (2L or multilayer): ≥0.254** |
| NPTH pad annular ring | ≥0.45 |
| Pad to track (1 oz) | 0.1 (0.09 locally at BGA pads) |
| SMD pad to pad, different nets | 0.15 |
| Min SMD pad | 0.25×0.25 |
| PTH to track | 0.28 min, 0.35 recommended; inner layers: PTH hole to copper 0.3 |
| NPTH to track | 0.2 |
| Same-net track spacing | 0.25 |
| Hatched grid | width and spacing 0.25 |
| BGA | pitch down to 0.2 (as published); 0.2–0.25 pads need ENIG; pad to trace ≥0.1 (0.09 multilayer) |
| Trace coils (1 oz) | 0.15/0.15 under mask; 0.25/0.25 bare (ENIG only) |

### Soldermask and silkscreen

| Item | Limit |
|---|---|
| Mask expansion | 1:1 (LDI since June 2025; reorders follow the earlier production file) |
| Mask opening to a neighbouring trace | ≥0.09 |
| Mask bridge (min pad spacing) | 1 oz: 0.10 green/red/yellow/blue/purple, 0.13 black/white; **2 oz: 0.20 any colour** |
| Mask thickness | ≥10 µm |
| Silkscreen | line ≥0.15, text height ≥1.0, width:height 1:6 preferred (hollow text too), pad to silk 0.15 |

### Outline and panels

| Item | Limit |
|---|---|
| Copper to routed edge or routed slot | ≥0.2 |
| Copper to V-cut edge | ≥0.4 |
| High-precision routing | panel ≥50×50 with ≥3 tooling holes (≥1.5) in different corners |
| Routed slot, metal core | ≥1.6 |
| V-cut | board ≥0.6 thick; spacing 0 (or V-cut one way, route the other with 1.6/2 mm gaps); panel 70×70 to 475×475; 25° groove; ≥2 between cuts (3 recommended) |
| Mouse bites | gaps 1.6 or 2; tooling edge ≥3; bite holes 0.5–0.8 at 0.2–0.3 spacing; breakaway tab ≥4 (5 with bites); edges stay serrated |
| Panel spacing | ≥2 (FAQ: 5–8 mm handling rails recommended) |
| Panel for JLC assembly | 5 mm rails, 2 mm tooling holes, 1 mm fiducials centred 3.85 from the panel edge |

### Impedance

| Item | Limit |
|---|---|
| Controlled impedance | 4+ layers, ±10% standard; **$** ±5% only "upon special request" |

## 2. Standard stackups (impedance page)

Copper on every listed stackup: outer 0.035, inner 0.0152. Use the
stackup name in the order and in the impedance calculator; read the per-layer prepreg
and core thicknesses from the page itself (a text extraction of the table was not
reliable enough to copy here).

- 4 layer, 1.6 (`JLC04161H-`): 7628, 3313, 1080, 2116, 7628A, 3313A, 1080A, 7628B,
  2116A, 2116B, 2116C, 1080B, 7628G, 7628E, 2116D, 7628F, 2116E, 7628C.
- 6 layer, 1.6 (`JLC06161H-`): 3313, 7628, 7628D, 1080, 2116A, 1080A, 3313C, 1080B,
  3313B, 3313E, 1080C, 2116B, 2116, 7628B, 3313D, 2116C, 7628A.

## 3. HDI

| Item | Limit |
|---|---|
| Build-up | 1-step, 2-step, 3-step (any-layer not offered) |
| Laser blind via | 0.075–0.15, copper-filled |
| Buried via (mechanical) | 0.15–0.55, epoxy filled and capped; 0.10 extreme when the dielectric it passes is ≤1.0 |
| HDI trace / space | 3/3 mil; 2.7/2.7 mil extreme (**$** special capability) |
| HDI board size | 5×5 to 576×469 |
| HDI material | Nan Ya NP-175F or Shengyi S1000-2M, Tg 170 |
| **$** | blind/buried, HDI, heavy copper and tight impedance "may increase both cost and production time" |

## 4. Flex (FPC)

| Item | Limit |
|---|---|
| Layers | 1, 2, 4. Rigid-flex not offered |
| Stackups | PI 25 µm (1L, 2L); PI 50 µm tear-resistant (1L, 2L; 2L suits impedance-sized traces); transparent PET 36 µm (1L, 2L); 4L with 1/3, 0.5 or 1 oz copper, inner 1 oz layers get coverlay by default |
| Size | regular max 234×490; up to 250×600 with edge rails (ask first); no minimum, panelise under 20×20 |
| Finished thickness (no stiffener) | 25 µm 1L 0.07/0.11, 2L 0.11/0.12/0.2; 50 µm 1L 0.12, 2L 0.19; transparent 1L 0.14, 2L 0.24; 4L 0.20–0.45 in 0.05 steps |
| Thickness tolerance | ≤0.3: ±0.05; 0.3–1.0: ±0.1; >1.0: ±10%; gold fingers ±0.03 |
| Copper | 1L 0.5 or 1 oz; 2L and 4L 1/3, 0.5 or 1 oz |
| Finish | ENIG 1 or 2 µ" gold; LDI dry film |
| Holes | 0.1–6.5 (PTH ≤5 recommended), ±0.08; plated slot ≥0.5; non-plated slot any width, 0.2 copper clearance |
| Castellated holes | hole ≥0.3, to edge ≥0.5, hole to hole ≥0.4 |
| Vias | regular 0.3/0.55; **$** extreme 2L 0.10/0.30, 4L 0.15/0.35; pad ≥ drill + 0.2 (+0.25 better) |
| PTH annular ring | 0.25 recommended, 0.18 absolute |
| Trace / space | 1/3 oz (12 µm) 3/3 mil (2/2 absolute, avoid); 0.5 oz 3.5/3.5 mil; 1 oz 4/4 mil; width ±20% |
| Clearances | via ring to trace ≥0.1; exposed pad to trace ≥0.15; NPTH to copper ≥0.2; BGA pad ≥0.25, BGA pad to trace ≥0.2 |
| Coverlay | yellow (recommended), black, white, transparent; expansion 0.1 per side; opening to trace ≥0.15; keep vias covered; min bridge 0.5 |
| Silkscreen | text ≥1.0, line ≥0.15, to pad ≥0.15 |
| Outline (laser) | copper to edge or slot ≥0.3; ±0.1 (±0.05 on request); gold finger to edge 0.2 |
| Panels | spacing 2 (3 with metal stiffeners); 5 mm copper-poured rails all round; four 1 mm fiducials (one offset ≥5), centred 3.85 from the edge, 1 mm clear; 2 mm tooling holes, 0.5 clear; tabs 0.7–1.0; max 234×490 |
| Stiffeners | PI 0.1/0.15/0.2/0.225/0.25; FR-4 0.1–1.6 (chips, avoid); stainless 0.1/0.2/0.3 (slightly magnetic, keep off Hall sensors); tapes 3M9077 0.05, 3M468 0.13 (not heat-resistant), tesa8854 0.1 (recommended) |
| EMI shield film | 18 µm black, grounded through mask openings |
| Bend radius | static ≥6× thickness 1L, ≥10× multilayer; dynamic 10–15×, 1–2L adhesiveless PI, no vias or pads in the bend |
| Impedance | **not controlled**, width only (PI εr 3.3, coverlay εr 2.9) |
| Everything else | holes, traces, mask and silk follow the rigid rules |

## 5. Assembly (PCBA)

| Item | Economic | Standard |
|---|---|---|
| Sides | one side (SMT and THT) | one or both |
| Layers | 2, 4, 6 | 1–32 |
| Board thickness | 0.8–1.6 | any |
| Single board | 10×10 to 470×500 | 70×70 to 460×500 |
| Panel | 10×10 to 250×250 | 70×70 to 250×250 (larger allowed, at handling and yield risk) |
| Quantity | 2–50 | 2–80,000 |
| Finish and colour | listed combinations only (below) | any |
| Delivery | single or mouse-bite panel | adds V-cut panels |
| Stackup | standard only | any |
| Gold fingers, castellation, plated edges | no | yes |
| Rails and fiducials | not required | required |
| Smallest package | 0402 | 01005 (step stencil advised for mixed sizes) |
| Min IC pitch | 0.4 | 0.35 |
| Min BGA pitch | 0.5 | 0.3 |
| Reflow peak | 255 ±5 °C, fixed | 240 ±5 °C |
| SPI / AOI / X-ray | no / yes / yes | yes / yes / yes (X-ray on BGA, QFN, LGA, priced per part) |
| Build time | 1–3 days | 4+ days |

Economic boards (thickness, colour, finish, quantity): 0.8 green HASL 2–30; 1.0 and 1.2
green or black HASL 2–30 (1.2 green to 50); 1.6 green HASL or ENIG 2–50; 1.6 black HASL
2–50; 1.6 blue/purple HASL 5–30; 1.6 red/white leaded HASL 5–30.

Other assembly notes: SMD is reflowed, THT is wave-soldered; unused THT holes are kept
open; flex assembly needs fixtures; wire soldering and MCU programming (Standard,
engineering review, HEX/BIN supplied) are offered; stacked parts need both in the BOM
and CPL with the top part's coordinate >0.2 away.

### Assembly fees (page dated 2026-10-22, USD)

| Fee | Economic | Standard |
|---|---|---|
| Setup | 8.18 | 25.56 one side / 51.12 two sides |
| Each extra design in a panel | 8.18 | 25.56 / 51.12 |
| Stencil | 1.53 | 8.21 / 16.42 |
| SMT | 0.0016 per joint | 0.0016 per joint to 50k, then 0.0013, then 0.0012 |
| Manual (THT) | 0.0164 per joint to 10k, 0.015 to 30k, 0.012 to 100k | same |
| Hand-soldering labour | 3.58 per order | same |
| **Feeder loading, per extended part number** | 3.07 | 1.53 (basic or extended) |
| Large board (>650 cm²) | 57.46 | 57.46 |
| X-ray | 1.64 per part (1–10) down to 0.082 (3k+) | same |
| Fixtures | — | rigid 8.21 each (2 for 1–29 boards … 20 for 500+); flex 24.63 each |
| Other | confirm placement 0.45 | handling ≥14.93 when the Economic gap is smaller, single-board surcharge 0.48, stencil or fixture storage 4.93, packing 0.50 + area |

Basic parts are already on the machines and carry no loading fee in Economic;
"preferred extended" parts are also exempt there (JLC assembly FAQ). The fee is per part number per order,
not per placement.
