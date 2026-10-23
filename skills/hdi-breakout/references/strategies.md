# Breakout strategies

One row per way to get a ball out of an array. "Router" is whether the house router (`rr`)
handles it today; KRT handles only the through-via rows. Numbers use 0.1/0.1 mm track/space
unless stated; run `scripts/escape_budget.py` with the board's own.

## Vias

| Strategy | When it applies | Cost and risk | Needs | Router |
|---|---|---|---|---|
| **Surface escape, outer ring** | Always, first | None | Room outside the field on the part's layer | yes |
| **Dogbone, outward** | Outer ring when its exit is blocked by other parts; ring 2 when a track passes between ring-1 balls | A via per ball beside the field; the L-47 band (via pad + 2 clearances) must exist at placement | Through or laser via | yes |
| **Quadrant dogbone, interstitial** | Pitch ≥ ~0.65 mm with through vias, ≥ ~0.5 mm with laser vias: when `interstitial_via.fits` | Classic and cheap; vias in each quadrant point away from the centre to leave channels | Via whose pad fits the half diagonal | yes (place the vias as fixed) |
| **Via-in-pad, inner balls only** | Inner balls with no channel and no interstitial site (0.4 mm WLCSP) | Filled and capped (IPC-4761 VII), on the fab drawing; a microvia per ball | Laser via, VIPPO | yes |
| **Via-in-pad, every ball** | Only when the via layer is not landlocked (check `via_in_pad_layer`) | Landlocks the inner rings at fine pitch; the sensor array's first 6L route failed on every AFE this way | Same | yes |
| **Staggered microvias** | More than one build-up layer, no stacking allowed | One offset per layer change (a short trace); lanes spent on the offsets | Laser vias per build-up layer | yes (`RR_NOSTACK`) |
| **Stacked microvias** | Densest fields, when the intake allows | Reliability concern under thermal cycling; copper-filled stacks cost more | Filled, stacked laser vias | yes (default) |
| **Skip via** | Need one more escape layer without stacking | L1 to L3 in one laser shot: deeper aspect ratio, not every fab, check the dielectric | Fab offers skip vias | add a via type |
| **Small or no capture pads on inner layers** | Via layer landlocked by capture pads | Fab minimum annular ring; padless vias need the fab's OK | Fab capability | rule change |
| **Any-layer HDI (ELIC)** | Phones-class density | Highest cost; every layer pair a laser via | Fab and budget | yes (stacked) |
| **Via farm outside the part** | Field too tight for any via inside | Longer stubs; space beside the part | Space | yes |

## Rules in the field

| Strategy | When | Cost | Router |
|---|---|---|---|
| **Neck-down rule area** | One track short between balls | Fab tier (JLC 3/3 mil is a higher tier); only inside the field's rule area | `.kicad_dru` area rule; `rr` uses one width per class today |
| **NSMD pad shrink** | A few hundredths of a millimetre open a channel | Assembler must accept the land; joint reliability | footprint change |

## Geometry (goes back to placement)

| Strategy | When | Cost | Router |
|---|---|---|---|
| **Rotate the part 45°** | Diagonal escapes have room the orthogonal ones don't (diagonal pitch is 1.41x) | Courtyard grows; assembly fine | n/a |
| **Rotate or mirror cells** | Escapes should face the lanes between cells | Conflicts with "identical, non-mirrored cells" (pcb-placement); record why | n/a |
| **Commensurate cell grid** | Any array next to another repeating grid | Board may grow (the sensor array's base grew 4.6 mm) | periodic tile mode |
| **One ring per layer** | Planning: rings / rows escaped per layer = escape layers | none: it's the estimate in `escape_budget.py` | n/a |

## Connections

| Strategy | When | Cost | Router |
|---|---|---|---|
| **Shared via for same-net neighbours** | Two GND or VDD balls side by side, via sites scarce | Breaks L-48 (a pad is a leaf): record as an exception; current through one land | needs an exception flag |
| **Shared plane tap per cell** | HDI stack with many GND pins per cell (L-43) | One buried via per cell instead of per pin; found 90 holes on the sensor array | yes (fixed own-net via as goal) |
| **NC balls as channels** | Datasheet says the ball must be left unconnected | none | treat as free |
| **Pin swapping** | FPGAs, MCUs with remappable pins | Schematic change; firmware | n/a |
