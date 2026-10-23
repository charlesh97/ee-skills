# Which loop is hot

The hot loop is the path whose current switches on and off every cycle. Its
inductance rings with the switch capacitance, and its area radiates. Every other
path carries a current that the inductor or a cap keeps smooth. Find the hot
loop first, because that is what the cell is built around.

| Topology | Hot loop (pads in order, for `hot_loop`) | Smooth side | Notes |
|---|---|---|---|
| Buck | input cap +, VIN, (high-side FET, low-side FET), GND, input cap − | output: inductor to output cap | The input cap is the critical part. The output cap matters for ripple, not ringing. |
| Boost | output cap +, VOUT (or the diode/high-side FET), GND/PGND, output cap − | input: input cap to inductor | Mirror of the buck: the output cap goes across the pins. |
| Buck-boost (4-switch) | both: input cap across VIN/PGND and output cap across VOUT/PGND | the inductor between the two SW nodes | Two hot loops and two SW nodes; check both. |
| Inverting buck-boost | input cap +, VIN, SW, inductor, … the loop through the input and output caps | — | Follow the vendor figure; the "ground" pin is often the negative rail. |
| Flyback / forward | primary: bulk cap, transformer primary, switch, sense resistor, bulk cap − ; secondary: winding, rectifier, output cap | — | Two loops; snubber and clamp loops are hot too. |
| Controller + external FETs | the input cap and the two FETs' drain-source path; plus each gate loop (driver, gate, source, driver return) | — | Gate loops are critical nets (L-49). |

## What to read in the datasheet

- **Pin table.** VIN and GND pins (often more than one each), SW, the exposed pad
  and what it is tied to, the sense pin (FB, VOS, SENSE), straps, EN, and BST.
- **Layout guidelines section.** It is usually half a page. Copy its numbered
  points into the cell notes and tick each one off against the demo.
- **Layout figure.** This is the most useful item in the datasheet. It shows the
  pin rotation, which side each cap goes on, where the ground vias go, and how
  the sense line leaves.
- **EVM user's guide.** It gives the full layout with layer stack and via sizes.
  Use it when captured, and say when it isn't.
- **Thermal table.** θJA and the board it was measured on (JEDEC 1s/2s2p, or the
  EVM). The EVM figure is usually half the JEDEC one; state which you used.
- **Application circuit.** Which pins are tied to VIN (EN, MODE) and where the
  figure ties them.

## Part traps seen in practice

- **A sense pin next to SW.** Small bucks (SOT-563, SOT-583, QFN-8) often put VOS
  or FB on the pin beside SW, facing the inductor. A top-layer route to the output
  cap then runs alongside the SW copper for millimetres. Take it to the layer
  under the first ground plane through a via within 1 mm of the pin.
- **EN tied to VIN.** It carries no current. A via-count script that treats it as
  a power pin asks for vias it doesn't need, and the spec's current table then
  says the pin is "short".
- **Separate analog and power ground** (SGND/PGND, AGND/PGND). If the datasheet
  joins them at one point (often the VCC or VDD bypass cap's return), the
  schematic needs two nets and a net tie at that point. One net in the
  schematic can't express the split in copper.
- **Exposed pad pasted whole.** A footprint whose EP carries paste on the full pad
  plus paste-window graphics has its vias under paste. Declare them filled and
  capped (L-30), or take the paste off the pad so the windows set it.
- **Internal bootstrap.** Many small parts have no BST pin. Check the pin table
  before looking for a bootstrap cap.
- **A plane split from the high-current side.** A split between two grounds
  drawn for a motor bridge or another power stage can run under a regulator's SW
  node, or under its output cap's ground via. The cell check catches both:
  plane cover under SW, and each cap's ground reaching the IC ground.
