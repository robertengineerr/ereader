# E-Reader v0.1 — Pin Connections Reference

KiCad project path: `/Users/robbiethomas/Documents/PlatformIO/Projects/e_reader_v0.1/hardware/`

MCU: **ESP32-S3-DevKitC-1 (N16R8)**

---

## E-Paper Display — Waveshare 7.5" V2 (800×480)
Interface: **FSPI (SPI2)**
Portrait orientation: 480px wide × 800px tall (setRotation(1))

| Display Pin | ESP32-S3 GPIO | Notes |
|-------------|---------------|-------|
| PWR         | GPIO3         | OUTPUT HIGH to power on |
| BUSY        | GPIO13        | Input, active HIGH while refreshing |
| RST         | GPIO12        | Active LOW reset |
| DC          | GPIO11        | Data/Command select |
| CS          | GPIO10        | SPI chip select, active LOW |
| CLK         | GPIO9         | FSPI clock |
| DIN (MOSI)  | GPIO46        | FSPI MOSI |
| VCC         | 3.3V          | |
| GND         | GND           | |

SPI settings: 4 MHz, MSBFIRST, SPI_MODE0

---

## SD Card Module — UMLIFE 3.3V (or equivalent)
Interface: **HSPI (SPI3)**

| SD Pin | ESP32-S3 GPIO | Notes |
|--------|---------------|-------|
| CS     | GPIO15        | SPI chip select, active LOW |
| MOSI   | GPIO16        | HSPI MOSI |
| SCK    | GPIO17        | HSPI clock |
| MISO   | GPIO18        | HSPI MISO |
| VCC    | 3.3V          | Must be 3.3V-native module (no onboard LDO) |
| GND    | GND           | |

SPI speed: 4 MHz. FAT32 formatted, .txt files in root.

---

## 5-Way Joystick
COM pin is driven LOW by GPIO (virtual GND). All direction pins are INPUT_PULLUP — pressed = LOW (FALLING edge interrupt).

| Joystick Pin | ESP32-S3 GPIO | Mode           | Function |
|--------------|---------------|----------------|----------|
| COM          | GPIO35        | OUTPUT LOW     | Virtual GND for joystick |
| UP           | GPIO36        | INPUT_PULLUP + INT | Navigate up / previous page |
| DOWN         | GPIO37        | INPUT_PULLUP + INT | Navigate down / next page |
| LEFT         | GPIO38        | INPUT_PULLUP + INT | Back to library |
| RIGHT        | GPIO39        | INPUT_PULLUP + INT | Next page (reading mode) |
| MID (press)  | GPIO40        | INPUT_PULLUP + INT | Select / back to library / exit WiFi |
| SET          | GPIO41        | INPUT_PULLUP   | Hold at boot → enter WiFi upload mode |
| RST          | GPIO42        | INPUT_PULLUP   | Reserved (reset / future use) |

All interrupts: FALLING edge, ISR-side debounce at 200 ms.

---

## Power Rails
| Rail  | Source                  | Consumers |
|-------|-------------------------|-----------|
| 3.3V  | DevKitC onboard reg / LiPo + regulator (future) | Display VCC, SD VCC, joystick pull-ups |
| GND   | Common ground           | All components |

---

## Unused / Reserved GPIOs (available for future use)
GPIO0, GPIO1, GPIO2, GPIO4, GPIO5, GPIO6, GPIO7, GPIO8, GPIO14, GPIO19–GPIO21, GPIO43–GPIO45, GPIO47, GPIO48

---

## WiFi
No external antenna wiring — onboard PCB antenna on DevKitC-1.
SSID / password stored in `src/secrets.h` (not committed to git).
mDNS hostname: `ereader.local`

---

## Notes for Schematic
- Add 100 nF decoupling caps on all VCC pins close to each IC
- Pull-up resistors on BUSY, RST are handled internally by GxEPD2 / MCU
- SD MISO should have a 10k pull-up to 3.3V (some modules include this)
- GPIO35 (JOY_COM) must be rated OUTPUT; on ESP32-S3-DevKitC-1 this is fine
- Future: LiPo charger (TP4056), 3.3V LDO (AP2112K or similar), power switch
