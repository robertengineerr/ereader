# e-reader

An open-source e-reader built on the ESP32-S3. Bare-metal C++ firmware, web-based book management, physical controls. Designed for FOSS developers to build on top of solid hardware.

## Schematic

[![View Schematic](https://img.shields.io/badge/KiCanvas-View%20Schematic-blue)](https://kicanvas.org/?github=https://github.com/robertengineerr/ereader/blob/main/hardware/e_reader_v0.1/e_reader_v0.1.kicad_sch)

The full KiCad project is in [`hardware/e_reader_v0.1/`](hardware/e_reader_v0.1/). Pin reference is in [`hardware/connections.md`](hardware/connections.md).

## Hardware

| Component | Part |
|---|---|
| MCU | ESP32-S3-DevKitC-1 (N16R8, 16MB flash, 8MB PSRAM) |
| Display | Waveshare 7.5" V2 e-ink (800×480) |
| Storage | MicroSD socket, SPI, FAT32 |
| Input | 7× tactile buttons |
| Battery | 3.7V LiPo via JST-PH, MCP73831 charger |
| Power | USB-C (charging + programming), AP2112 3.3V LDO |

### Wiring

**Display (FSPI / SPI2)**
| Signal | GPIO | Notes |
|---|---|---|
| PWR | 3 | Drive HIGH to power display |
| CS | 10 | |
| CLK | 9 | |
| DIN (MOSI) | 46 | |
| DC | 11 | |
| RST | 12 | |
| BUSY | 13 | |

**SD Card (HSPI / SPI3)**
| Signal | GPIO |
|---|---|
| CS | 15 |
| MOSI | 16 |
| SCK | 17 |
| MISO | 18 |

> Use a 3.3V-native SD socket (no onboard LDO). DAT1 and DAT2 must be pulled to 3.3V via 10k resistors.

**Buttons**
| Button | GPIO | Notes |
|---|---|---|
| UP | 36 | INPUT_PULLUP, FALLING interrupt |
| DOWN | 37 | INPUT_PULLUP, FALLING interrupt |
| LEFT | 38 | INPUT_PULLUP, FALLING interrupt |
| RIGHT | 39 | INPUT_PULLUP, FALLING interrupt |
| MID | 40 | INPUT_PULLUP, FALLING interrupt |
| SET | 41 | Hold at boot → WiFi mode |
| RST | 42 | Reserved |

## Building

1. Install [PlatformIO](https://platformio.org/)
2. Create `src/secrets.h` with your WiFi credentials:
```cpp
#define WIFI_SSID "your-ssid"
#define WIFI_PASS "your-password"
```
3. Build and flash:
```bash
pio run --target upload
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
- [ ] PCB layout and fabrication (JLCPCB)
- [ ] LiPo battery + charging circuit (MCP73831 + AP2112)
- [ ] Persist reading position (LittleFS)
- [ ] EPUB native rendering
- [ ] 3D printed enclosure

## License

MIT
