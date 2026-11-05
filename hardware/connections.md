# E-Reader — Pin Connections Reference

KiCad project: [`hardware/e_reader_v0.1/`](e_reader_v0.1/) (schematic rev 0.2.0)

There are two hardware targets. The firmware picks the pin map from `src/pins.h`:

| Target | MCU | Build |
|--------|-----|-------|
| Breadboard | ESP32-S3-DevKitC-1 (N16R8), joystick module with COM on a GPIO | `pio run -e esp32-s3-devkitc-1` (default) |
| PCB (rev 0.2.0) | ESP32-S3-WROOM-1-N16R8 on the custom board | `pio run -e pcb` (`-DBOARD_PCB`, 16 MB flash, octal PSRAM, Serial over native USB-CDC) |

Pins that differ between the two are **bold**.

---

## Flashing the PCB (first time)
The PCB has no USB-UART bridge and no auto-reset circuit, so the first flash is manual:
1. Slide **SW10 to ON**. The ESP32 is only powered with the regulator enabled, even on USB.
2. Plug in USB-C, then **hold BOOT (SW1), tap RESET (SW2) and release BOOT**. The ESP32 enters download mode.
3. `pio run -e pcb --target upload`
4. Tap RESET. Once the firmware is running, later uploads normally work over the native USB port without buttons.
   If a sketch crashes or disables USB, repeat step 2.

## E-Paper Display — Waveshare 7.5" V2 (800×480) driver HAT
Interface: **FSPI (SPI2)**, 4 MHz, MSBFIRST, SPI_MODE0. Portrait orientation (setRotation(1)).
On the PCB the HAT plugs into the 9-pin 2.54 mm SMD header J2 with individual Dupont leads.

| Display pin | J2 pin | Breadboard GPIO | PCB GPIO | Notes |
|-------------|--------|-----------------|----------|-------|
| PWR         | 1 | GPIO3  | GPIO3  | OUTPUT HIGH to power the panel |
| BUSY        | 2 | GPIO13 | GPIO13 | Input, active HIGH while refreshing |
| RST         | 3 | GPIO12 | GPIO12 | Active LOW reset |
| DC          | 4 | GPIO11 | GPIO11 | Data/Command select |
| CS          | 5 | GPIO10 | GPIO10 | Chip select, active LOW |
| CLK         | 6 | GPIO9  | GPIO9  | FSPI clock |
| DIN (MOSI)  | 7 | **GPIO46** | **GPIO14** | GPIO46 is a strapping pin, so the PCB avoids it |
| VCC         | 8 | 3.3V   | 3.3V   | |
| GND         | 9 | GND    | GND    | |

---

## microSD — Molex 104031-0811 (PCB) / 3.3 V SD module (breadboard)
Interface: **HSPI (SPI3)**, 4 MHz. FAT32, `.txt` files in root.

| SD signal | GPIO | Notes |
|-----------|------|-------|
| CS (DAT3) | GPIO15 | 10K pull-up (R20) on the PCB |
| MOSI (CMD) | GPIO16 | 10K pull-up (R21) on the PCB |
| SCK (CLK) | GPIO17 | |
| MISO (DAT0) | GPIO18 | 10K pull-up (R19) on the PCB |
| DAT1 / DAT2 | — | 10K pull-ups (R2 / R1), unused in SPI mode |
| Card detect | **GPIO6 (PCB only; not read by firmware yet)** | DET_B → GPIO6 with 10K pull-up (R22), DET_A → GND. Check the switch polarity (open or closed with a card in) on the first board |

---

## Inputs
All inputs are active LOW (pressed = LOW, FALLING-edge interrupts, 200 ms ISR debounce).
On the PCB each line also has a 5.1K pull-up and a 1 µF RC to GND.

| Function | Breadboard GPIO | PCB GPIO | PCB part |
|----------|-----------------|----------|----------|
| Joystick COM | **GPIO35 (OUTPUT LOW)** | **GND** | SW3 pin 5 |
| UP / previous page | **GPIO36** | **GPIO4** | SW3 A (pin 1) |
| DOWN / next page | **GPIO37** | **GPIO5** | SW3 C (pin 3) |
| LEFT / back to library | GPIO38 | GPIO38 | SW3 D (pin 4) |
| RIGHT / next page | GPIO39 | GPIO39 | SW3 B (pin 6) |
| MID (press) / select | GPIO40 | GPIO40 | SW3 center (pin 2) |
| SET (hold at boot → WiFi upload) | GPIO41 | GPIO41 | SW8 (KMR2) |
| RST (reserved) | GPIO42 | GPIO42 | SW9 (KMR2) |
| BOOT (download mode) | — | GPIO0 | SW1 (KMR2) |
| RESET | — | EN | SW2 (KMR2), 10K + 1 µF RC |

On the PCB the joystick is an **Alps SKRHABE010** (LCSC C139794). Which of A/B/C/D faces "up" depends
on how it is rotated on the board, so check it after layout and remap in `pins.h` if needed.

Why the PCB moves UP/DOWN: on the WROOM-1 **N16R8** module, GPIO35–37 are wired to the octal PSRAM.
They only work on the breadboard because the default PlatformIO board config leaves PSRAM disabled.

---

## Power
| Rail | Source | Consumers |
|------|--------|-----------|
| VBUS | USB-C (5 V), ESD-protected by USBLC6-2SC6 + SMAJ5.0A TVS (D3) | MCP73831 charger, SS54 → VHI |
| VBAT_RAW | 1-cell LiPo on JST PH (X1), 2-pin SMD | → F1 (1 A PTC) → Q4 (reverse-polarity P-FET) → VBAT |
| VBAT | protected battery rail | MCP73831 output, DMG3415U load switch → VHI, battery divider |
| VHI | VBUS via SS54, or VBAT via DMG3415U (Q3, gate pulled down by R12 10K) when USB is absent | RT9080-3.3 LDO input |
| +3V3 | RT9080-33GJ5 (600 mA, ~2 µA Iq) | ESP32-S3, display, SD, pull-ups |

- **Power switch SW10** (C&K PCM12SMTR, SMD) drives the LDO **EN**: ON = VHI, OFF = GND. R7 (1M) pulls EN down
  while the slider is moving. Pin 2 is the switch common.
  When OFF the 3V3 rail is down, but the battery still charges from USB.
- **Charging:** MCP73831, 200 mA (R4 = 5.1K; 2K gives 500 mA, so pick it for your cell). The orange LED (CHG0) is on while charging.
- **Battery protection:** F1 sits between the cell and everything else, and Q4 blocks a reversed cell.
  Over-discharge cutoff is left to the cell's own protection PCB, so use a protected LiPo.
- **Battery sense (hardware only; firmware does not read it yet):** VBAT → 470K/470K → **GPIO1 (ADC1_CH0)**, with 100 nF filter.
  V_bat = 2 × V_adc. The divider draws about 4.5 µA permanently. Sample slowly: the 100 nF cap feeds the ADC.

---

## Test pads (PCB, not assembled)
TP1 VBAT, TP2 VHI, TP3 3V3, TP4 GND, TP5 TXD0 (GPIO43), TP6 RXD0 (GPIO44). UART0 is a fallback console;
the primary console is native USB-CDC.

## Free GPIOs (PCB)
GPIO2, GPIO7, GPIO8, GPIO21, GPIO45 (strapping), GPIO47, GPIO48.
Do not use GPIO35–37 (octal PSRAM).
Note: GPIO39–42 (joystick RIGHT/MID, SET, RST) are the external JTAG pins. Use the built-in USB-JTAG for debugging.

## WiFi
Onboard PCB antenna on the WROOM-1. SSID/password in `src/secrets.h` (not committed). mDNS: `ereader.local`.
