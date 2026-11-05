# Schematic review log — e_reader_v0.1, rev 0.1.0 → 0.2.0

The schematic went through an initial audit, then three rounds of independent review.
Each round had three reviewer agents on smaller models: Sonnet for power, Sonnet for the MCU and
peripherals, and Haiku for general correctness and manufacturability. Every finding was checked
against the KiCad netlist (`kicad-cli`), the KiCad libraries or the LCSC catalogue before it was
accepted or rejected.

## Scores

| Round | Power | MCU / peripherals | General / DFM | Average |
|---|---|---|---|---|
| 1 | 7 | 8 | 6 | 7.0 |
| 2 | 4 ¹ | 8 | 8 | 6.7 |
| 3 | 8 | 8 | 6 ² | 7.3 |

¹ The score was driven by a claimed short through SW10. That claim was wrong: the KiCad symbol
`SW_SPDT_321` has pin 2 as the common, and the footprint matches.
² The main items were a repeat of the SW10 misread, a 1 A PTC concern (actual peak is about 0.5 A)
and the lack of an on-board protection IC (the design uses a protected cell).

ERC finishes with 0 errors after every round. The remaining warnings only mean the Adafruit Eagle
library isn't installed on the machine running ERC; the symbols are embedded in the schematic.

## Initial audit (before round 1)

| Problem in rev 0.1.0 | Fix |
|---|---|
| The power switch only gated the charger; the board was always on with a battery fitted | SW10 drives the LDO EN; the charger is fed straight from VBUS |
| A full-size SD symbol on a microSD footprint scrambled CS, MOSI, GND and DAT2 | `Micro_SD_Card_Det2` with the Molex 104031-0811 footprint, card detect on GPIO6 |
| KMR2 buttons, charge LED, USB-C and battery JST: symbol pin numbers didn't match the footprint pads | Pins renumbered or stacked to match the footprints |
| Joystick UP/DOWN on GPIO36/37, which the N16R8 module uses for octal PSRAM | Moved to GPIO4/5 |
| Display DIN on GPIO46, a strapping pin | Moved to GPIO14 |
| The 5.1K/5.1K battery divider drew about 410 µA all the time | 100K/100K, later 470K/470K, with 100 nF |
| No charger input cap, no PWR_FLAGs, stray wires | C22 4.7 µF, PWR_FLAGs, wires cleaned up |
| Five tact switches for the directions | One Alps SKRHABE010 5-way joystick, footprint built from LCSC land-pattern data |

## Round 1 → fixes
Accepted: F1 moved to the battery input, with a Q4 reverse-polarity P-FET added; AP2112K replaced by
the RT9080 (about 2 µA Iq instead of about 55 µA); divider raised to 470K; R3 lowered to 2.2K so the
LED is visible; SMAJ5.0A TVS added on VBUS; joystick mounting pads tied to GND; BOM assembly notes added.
Rejected: U3's LCSC number (C424093 was confirmed as MCP73831T-2ACI/OT); D1 split nets
(intentional flow-through routing); STAT to a GPIO (STAT swings to 5 V).

## Round 2 → fixes
Accepted: R22 10K pull-up on SD_DET; R21 10K pull-up on SD CMD; PlatformIO `pcb` env changed to
USB-CDC on boot, 16 MB flash, qio_opi and PSRAM.
Rejected: the SW10 short (wrong; see ¹ above); F1 "not a PTC" (LCSC lists it under resettable fuses);
C22 "10 V" (Samsung voltage code A means 25 V).

## Round 3 → fixes
Accepted: R12 100K → 10K (VBUS bleeds off quickly after unplug, so Q3 takes over and SS54 leakage
can't hold it off); R7 1M pull-down on EN; test pads TP1–TP6 (VBAT, VHI, 3V3, GND, UART0 TX/RX);
battery polarity note; firmware reads "SET held at boot" before SD/display init.
Accepted as known v0.1 limitations: RT9080 thermals at sustained high load on USB (the average
e-reader load is low); no on-board cell protection (use a protected LiPo); SMAJ5.0A clamp voltage vs
the MCP73831 abs-max under surge; about 10–15 µA off-state drain from the divider and leakage.

## Before ordering PCBs
- [ ] During layout, confirm which SKRHABE010 direction (A/B/C/D) faces "up", and remap `pins.h` if needed.
- [ ] Check the Molex 104031-0811 card-detect polarity (switch open or closed with a card in) on the first board.
- [ ] Silkscreen every J2 pin name (it is wired for individual Dupont leads, not a ribbon) and mark "+" on X1.
- [ ] Choose R4 for your cell (5.1K ≈ 200 mA, 2K ≈ 500 mA, max 1C).
- [ ] Every part is SMD with a verified LCSC number (`e_reader_v0.1/e_reader_v0.1_bom.csv`), so JLCPCB can assemble the whole board.
      The USB-C connector (HRO TYPE-C-31-M-12) has through-hole shield tabs. JLCPCB normally places it in SMT assembly, but check the quote.

## All-SMD follow-up
SW10 changed from the Nidec CAS-120A1 (not stocked at LCSC) to a **C&K PCM12SMTR** (LCSC C221841), using KiCad's standard
`SW_SPDT_PCM12` footprint. Its pads match LCSC's land pattern, and the pinout is the same (pin 2 is the common).
J2 changed from a through-hole header to an **SMD 1×9 2.54 mm male header** (INCP IPCP254M09PB08S, LCSC C22438433),
with a footprint built from LCSC's land pattern. The pin order is unchanged, so individual Dupont leads still plug on.

## PCB layout (rev 0.2.0)
`hardware/e_reader_v0.1/e_reader_v0.1.kicad_pcb`: 4 layers, 68 × 50 mm. F.Cu and B.Cu carry signals plus a GND pour,
In1 is a solid GND plane and In2 is a solid +3V3 plane. The board was placed with `hardware/tools/gen_pcb.py` and routed
with `hardware/tools/route_pcb.py` (grid A* router with rip-up and reroute; GND/+3V3 pads drop to their plane through vias).

**KiCad DRC with schematic parity:** 0 unconnected pads, 0 clearance, hole or edge errors, 0 footprint mismatches.
There are 17 silkscreen-only warnings (footprint outline art at the board edge and overlapping labels).

**Layout review round** (Sonnet electrical 7/10, Haiku DFM 7/10). These were fixed:
- The ESP32 3V3 decoupling was about 20 mm from the pin. The module moved 3.5 mm so that C10 (100 nF) is 2.6 mm and C1 (10 µF) is 4.9 mm from pin 2.
- D1 (USB ESD) moved to 2.8 mm from the USB-C D+/D- pads (it was about 10 mm). The battery input caps are now 5 mm from X1.
- Three fiducials (FID1-3) added for SMT assembly, and the board revision is set to 0.2.0 in the Gerbers.
- The router now keeps tracks out of the fiducial clearance and mask opening.

**Accepted for v0.1:** USB D+/D- are routed as separate lines rather than a matched pair, which is fine for 12 Mbit/s Full Speed.
The ESP32 footprint's own 0.2 mm thermal vias are within JLCPCB's multilayer capability. USB-C, SW10 and X1 sit flush with the board edge on purpose.

### Ordering at JLCPCB
Upload `fab/jlcpcb_gerbers.zip`: 4 layers, 1.6 mm, choose HASL lead-free or ENIG. Then add "PCB Assembly" (top side)
with `fab/jlcpcb_bom.csv` and `fab/jlcpcb_cpl.csv`.
- [ ] **Check each part's rotation in JLCPCB's placement preview.** The CPL uses KiCad rotations, and SOT-23, SMA, USB-C,
      JST, microSD, the slide switch and the ESP32 often need an offset in JLCPCB's library. Adjust them in the preview before you confirm.
- [ ] Open the board in KiCad and look it over, especially the USB lines and the area around the antenna.
