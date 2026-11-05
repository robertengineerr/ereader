# e-reader

An open-source e-reader built on the ESP32-S3. Bare-metal C++ firmware, web-based book management, physical controls. Designed for FOSS developers to build on top of solid hardware.

## Schematic

[![View Schematic](https://img.shields.io/badge/KiCanvas-View%20Schematic-blue)](https://kicanvas.org/?github=https://github.com/robertengineerr/ereader/blob/main/hardware/e_reader_v0.1/e_reader_v0.1.kicad_sch)

[![View Layout](https://img.shields.io/badge/KiCanvas-View%20Layout-blue)](https://kicanvas.org/?github=https://github.com/robertengineerr/ereader/blob/main/hardware/e_reader_v0.1/e_reader_v0.1.kicad_pcb)

The full KiCad project is in [`hardware/e_reader_v0.1/`](hardware/e_reader_v0.1/). Pin reference is in [`hardware/connections.md`](hardware/connections.md).

## Hardware

| Component | Part (PCB rev 0.2.0) |
|---|---|
| MCU | ESP32-S3-WROOM-1-N16R8 (16 MB flash, 8 MB octal PSRAM) |
| Display | Waveshare 7.5" V2 e-ink (800×480) via driver HAT on a 9-pin header |
| Storage | microSD (Molex 104031-0811), SPI, FAT32, card detect |
| Input | Alps SKRHABE010 5-way joystick, plus SET / RST / BOOT / RESET buttons |
| Battery | 1-cell protected LiPo via JST-PH, MCP73831 charger, PTC + reverse-polarity FET |
| Power | USB-C (charging + native USB programming), RT9080 3.3 V LDO (~2 µA Iq), slide switch on LDO enable |

The BOM, with an LCSC number for every assembled part, is in
[`hardware/e_reader_v0.1/e_reader_v0.1_bom.csv`](hardware/e_reader_v0.1/e_reader_v0.1_bom.csv).
The design-review log is in [`hardware/REVIEW.md`](hardware/REVIEW.md).

### Wiring

Full pin tables for the breadboard and the PCB are in [`hardware/connections.md`](hardware/connections.md).
The firmware takes its pins from [`src/pins.h`](src/pins.h): the default build uses the breadboard map,
and `pio run -e pcb` uses the PCB map.

The PCB pins that differ from the breadboard are:
| Signal | Breadboard | PCB | Why |
|---|---|---|---|
| Joystick UP / DOWN | GPIO36 / 37 | GPIO4 / 5 | GPIO35–37 are used by the N16R8's octal PSRAM |
| Joystick COM | GPIO35 driven LOW | GND | |
| Display DIN | GPIO46 | GPIO14 | GPIO46 is a boot strapping pin |
| SD card detect | — | GPIO6 | |
| Battery voltage | — | GPIO1 (×2 divider) | |

## Building

1. Install [PlatformIO](https://platformio.org/)
2. Create `src/secrets.h` with your WiFi credentials:
```cpp
#define WIFI_SSID "your-ssid"
#define WIFI_PASS "your-password"
```
3. Build and flash:
```bash
pio run --target upload            # breadboard (DevKitC-1)
pio run -e pcb --target upload     # custom PCB (first time: SW10 ON, hold BOOT, tap RESET; see hardware/connections.md)
```

## Usage

| Button | Library | Reading | Settings |
|---|---|---|---|
| UP | Cursor up | Previous page | Cursor up |
| DOWN | Cursor down | Next page | Cursor down |
| RIGHT | — | Next page | — |
| MID | Select | Back to library | Select |
| LEFT | — | Back to library | Back to library |
| Hold SET at boot | — | — | Enter WiFi mode |

### WiFi Upload

Hold SET while pressing reset, or navigate **Settings → WiFi Upload**. The device connects to your WiFi and shows `ereader.local` on screen. Open `http://ereader.local` in a browser to upload and delete books.

Supported formats (converted to plain text in the browser):
- `.txt` — uploaded directly
- `.epub` — extracted in browser via JSZip
- `.pdf` — extracted via PDF.js
- `.docx` — extracted via JSZip
- `.html` / `.htm` — stripped in browser
- `.fb2` — parsed in browser

Press MID on the device or click **Exit WiFi Mode** in the browser to return to the library.

### Fallback

If no SD card is present the device falls back to a built-in sample text (Iliad Book I, Pope translation) so the UI is always usable.

## Project Structure

```
src/
  main.cpp          # setup, loop, ISR input handling, state machine
  display.cpp/h     # e-ink display abstraction (GxEPD2)
  sd_manager.cpp/h  # SD card init, book listing, pagination engine
  network.cpp/h     # WiFi, HTTP file manager, mDNS
  web_ui.h          # embedded HTML/JS for the browser file manager
  secrets.h         # WiFi credentials (not in repo — create your own)

hardware/
  connections.md              # full pin reference for KiCad
  e_reader_v0.1/              # KiCad project (schematic + PCB)
```

## Roadmap

- [x] Text rendering on e-ink display
- [x] SD card file management
- [x] State machine UI (Library / Reading / Settings)
- [x] WiFi upload with multi-format support
- [x] mDNS (`ereader.local`)
- [x] Hardware schematic v0.1
- [x] Schematic rev 0.2.0: power fixes, 5-way joystick, BOM with LCSC numbers (3 review rounds)
- [x] PCB layout (4-layer, routed, DRC clean) and JLCPCB fab files in `hardware/e_reader_v0.1/fab/`
- [ ] Fabrication and bring-up
- [x] LiPo battery + charging circuit (MCP73831 + RT9080) in schematic
- [ ] Persist reading position (LittleFS)
- [ ] EPUB native rendering
- [ ] 3D printed enclosure

## License

MIT
