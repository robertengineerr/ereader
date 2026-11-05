#pragma once
// Pin map for both hardware targets.
//   default        : breadboard (ESP32-S3-DevKitC-1, joystick module COM driven by a GPIO)
//   -DBOARD_PCB    : e_reader_v0.1 PCB (hardware/e_reader_v0.1/e_reader_v0.1.kicad_sch, rev 0.2.0)
//
// PCB notes:
//  * GPIO35-37 are wired to the octal PSRAM inside ESP32-S3-WROOM-1-N16R8, so the
//    PCB moves JOY_UP/JOY_DWN to GPIO4/GPIO5.
//  * GPIO46 is a boot strapping pin, so the PCB moves EPD_DIN to GPIO14.
//  * The joystick COM pin is tied straight to GND (no JOY_COM GPIO).
//  * Every input has a 5.1K pull-up + 1uF RC on the board; INPUT_PULLUP is harmless.

// --- e-paper (FSPI) ---
#define EPD_PWR    3
#define EPD_BUSY  13
#define EPD_RST   12
#define EPD_DC    11
#define EPD_CS    10
#define EPD_CLK    9

// --- SD card (HSPI) ---
#define SD_CS    15
#define SD_MOSI  16
#define SD_SCK   17
#define SD_MISO  18

#ifdef BOARD_PCB
  #define EPD_DIN   14
  #define JOY_COM   -1   // tied to GND on the PCB
  #define JOY_UP     4
  #define JOY_DWN    5
  #define SD_DET     6   // card-detect switch to GND (use INPUT_PULLUP)
  #define BATT_ADC   1   // VBAT via 470K/470K divider + 100nF -> multiply reading by 2
#else
  #define EPD_DIN   46
  #define JOY_COM   35   // driven OUTPUT LOW as a virtual GND on the breadboard
  #define JOY_UP    36
  #define JOY_DWN   37
  #define SD_DET    -1
  #define BATT_ADC  -1
#endif

#define JOY_LFT  38
#define JOY_RHT  39
#define JOY_MID  40
#define JOY_SET  41  // hold at boot to enter WiFi upload mode
#define JOY_RST  42
