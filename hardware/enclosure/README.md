# Enclosure (v0.1 fit prototype)

A 3D-printable case for the whole reader: Waveshare 7.5" panel on the left, the PCB in a strip on the right.
Outer size is **176.4 x 174.8 x 17.4 mm**, which fits a Bambu A1 mini bed (180 x 180).

**None of this has been test-fitted.** The dimensions come from the KiCad board file and from datasheet values
for the display, joystick and connectors. Expect to adjust a few numbers after the first print.

## View it in Onshape
Create a document, choose **Import**, and upload `ereader_assembly.step`. It contains every printed part plus
mock-ups of the PCB, display, battery and display plugs so you can see how it goes together.

## Parts to print
| File | Qty | How to print |
|---|---|---|
| `back_shell.stl` | 1 | Open side up, no supports |
| `front_cover.stl` | 1 | Front face down on the bed, no supports |
| `j2_hood.stl` | 1 | Open side up (flip it over), no supports |
| `joystick_cap.stl` | 1 | Wide flange down; supports under the top section, or flip and glue |
| `button_plunger.stl` | 2 | Top down, no supports |

Hardware: 3 x M2.5 x 5 screws for the PCB, 6 x M2.5 x 8 for the cover (self-tapping into the plastic), and thin foam tape.

## How it goes together
1. Screw the PCB onto the three standoffs. Its microSD slot faces the bottom wall and the USB-C faces the recess on the right.
2. The battery sits in the ribbed pocket above the PCB. Its plug goes into X1; route the lead under or over the PCB.
3. The display driver HAT sits behind the panel area. Its 9 leads plug onto J2.
4. Lay the panel face down into the front cover's pocket, drop the joystick cap and two button plungers into their holes,
   then hook the cover's three tabs over the ridges on the left wall and screw down the right side.
5. Push the hood over the J2 opening. It covers the plugged-in display leads, which stand about 17 mm above the PCB.

## Openings
Joystick and SET/RST come through the front. BOOT and RESET are pinholes (use a paperclip). The charge LED has a 2 mm hole.
USB-C and the power slider are in the recess on the right side. The microSD card is reached through a window in the bottom wall.

## Things to check before printing
- `JOY_STEM_D`, `JOY_STEM_H`: the joystick stem size is an estimate. Measure the real part and edit `enclosure.py`.
- `AA_LEFT`, `AA_BOTTOM`: where the active area sits on the panel. Measure your panel's borders.
- `H_INNER` (13 mm): depth behind the panel for the driver HAT. Measure your HAT with its header.
- The ESP32 antenna ends up about 1.5 mm from the panel edge, which may shorten Wi-Fi range.

To regenerate after editing: `python enclosure.py` (needs `cadquery`). It re-runs a clash check against the mock-ups.
