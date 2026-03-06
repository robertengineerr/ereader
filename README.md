# e-reader

An open-source e-reader built on the ESP32-S3. Bare-metal firmware, web-based book management, physical controls. Designed to be hacked on.

## Hardware

| Component | Part |
|---|---|
| MCU | ESP32-S3 DevKitC-1 (N16R8) |
| Display | Waveshare 2.9" V2 e-ink (296×128) |
| Storage | MicroSD module (3.3V, SPI) |
| Input | 5-way joystick |

### Wiring

**Display (FSPI / SPI2)**
| Signal | GPIO |
|---|---|
| CS | 10 |
| SCK | 12 |
| MOSI | 11 |
| DC | 8 |
| RST | 9 |
| BUSY | 7 |

**SD Card (HSPI / SPI3)**
| Signal | GPIO |
|---|---|
| CS | 18 |
| SCK | 17 |
| MOSI | 15 |
| MISO | 16 |

> Use a 3.3V SD module (no onboard LDO). Connect VCC to the ESP32 3.3V pin.

**Joystick**
| Direction | GPIO |
|---|---|
| COM | 35 (driven LOW) |
| UP | 36 |
| DOWN | 37 |
| LEFT | 38 |
| RIGHT | 39 |
| MID | 40 |
| SET | 41 |

## Building

1. Install [PlatformIO](https://platformio.org/)
2. Copy `src/secrets.txt` instructions and create `src/secrets.h` with your WiFi credentials
3. Build and flash: `pio run --target upload`

## Usage

- **UP / DOWN** — navigate menus, prev/next page while reading
- **MID** — select
- **LEFT** — go back
- **Hold SET at boot** — enter WiFi upload mode

### WiFi Upload

Hold SET while pressing reset, or navigate to Settings → WiFi Upload. The device IP shows on screen. Open it in a browser to upload/delete `.txt` books.

## Project Structure

```
src/
  main.cpp        # setup, loop, state machine
  display.cpp/h   # e-ink display abstraction
  sd_manager.cpp/h # SD card, book file, pagination
  network.cpp/h   # WiFi + HTTP file manager
  web_ui.h        # embedded HTML for the file manager
  secrets.h       # WiFi credentials (not in repo — create your own)
```

## License

MIT
