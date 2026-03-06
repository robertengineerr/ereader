#include <Arduino.h>
#include <SPI.h>
#include <GxEPD2_BW.h>
#include <Fonts/FreeMonoBold9pt7b.h>
#include "display.h"
#include "sd_manager.h"

// --- e-Paper pins (FSPI / SPI2) ---
#define EPD_BUSY  13
#define EPD_RST   12
#define EPD_DC    11
#define EPD_CS    10
#define EPD_CLK    9
#define EPD_DIN   46  // MOSI

static SPIClass epdSPI(FSPI);

// Waveshare 2.9" V2, 296x128. Swap to GxEPD2_750_T7 when 7.5" arrives.
static GxEPD2_BW<GxEPD2_290_T94_V2, GxEPD2_290_T94_V2::HEIGHT> display(
  GxEPD2_290_T94_V2(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY)
);

void initDisplay() {
  epdSPI.begin(EPD_CLK, -1, EPD_DIN, EPD_CS);
  display.init(115200, true, 2, false, epdSPI, SPISettings(4000000, MSBFIRST, SPI_MODE0));
  display.setRotation(1);
}

// ---------------------------------------------------------------------------
// Reading screen
// ---------------------------------------------------------------------------

void showPage(int pageNum) {
  if (pageNum < 0 || pageNum >= totalPages) return;

  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setFont(&FreeMonoBold9pt7b);
    display.setTextColor(GxEPD_BLACK);

    for (int line = 0; line < LINES_PER_PAGE; line++) {
      char lineBuf[CHARS_PER_LINE + 1];
      int len = getLine(pageNum, line, lineBuf, CHARS_PER_LINE);
      if (len == 0) break;
      display.setCursor(MARGIN, MARGIN + LINE_HEIGHT + (line * LINE_HEIGHT));
      display.print(lineBuf);
    }

    display.setCursor(DISPLAY_W - 40, DISPLAY_H - 8);
    display.printf("%d/%d", pageNum + 1, totalPages);
  } while (display.nextPage());
}

// ---------------------------------------------------------------------------
// Boot screen
// ---------------------------------------------------------------------------

void showBootScreen() {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setFont(&FreeMonoBold9pt7b);
    display.setTextColor(GxEPD_BLACK);
    display.setCursor(MARGIN, MARGIN + LINE_HEIGHT);
    display.print("e-Reader");
    display.setCursor(MARGIN, MARGIN + LINE_HEIGHT * 2 + 4);
    display.print("Loading...");
  } while (display.nextPage());
}

// ---------------------------------------------------------------------------
// Library screen
// Items:  names[0..count-1]  (SD books)
//         index count        → "Settings" (always last)
// ---------------------------------------------------------------------------

void showLibraryScreen(char names[][MAX_NAME_LEN], int count, int selected, int scroll) {
  int totalItems = count + 1;

  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setFont(&FreeMonoBold9pt7b);

    display.setTextColor(GxEPD_BLACK);
    display.setCursor(MARGIN, MARGIN + LINE_HEIGHT);
    display.print("Library");
    display.drawFastHLine(0, MARGIN + LINE_HEIGHT + 2, DISPLAY_W, GxEPD_BLACK);

    for (int i = 0; i < LIBRARY_VISIBLE; i++) {
      int idx = scroll + i;
      if (idx >= totalItems) break;

      const char* label = (idx < count) ? names[idx] : "Settings";
      int cursorY = MARGIN + LINE_HEIGHT * (i + 2);

      if (idx == selected) {
        display.fillRect(0, cursorY - 13, DISPLAY_W, LINE_HEIGHT, GxEPD_BLACK);
        display.setTextColor(GxEPD_WHITE);
      } else {
        display.setTextColor(GxEPD_BLACK);
      }
      display.setCursor(MARGIN, cursorY);
      display.print(label);
    }

    display.setTextColor(GxEPD_BLACK);
  } while (display.nextPage());
}

// ---------------------------------------------------------------------------
// Settings screen
// ---------------------------------------------------------------------------

void showSettingsScreen(const char** items, int count, int selected) {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setFont(&FreeMonoBold9pt7b);

    display.setTextColor(GxEPD_BLACK);
    display.setCursor(MARGIN, MARGIN + LINE_HEIGHT);
    display.print("Settings");
    display.drawFastHLine(0, MARGIN + LINE_HEIGHT + 2, DISPLAY_W, GxEPD_BLACK);

    for (int i = 0; i < count && i < LIBRARY_VISIBLE; i++) {
      int cursorY = MARGIN + LINE_HEIGHT * (i + 2);
      if (i == selected) {
        display.fillRect(0, cursorY - 13, DISPLAY_W, LINE_HEIGHT, GxEPD_BLACK);
        display.setTextColor(GxEPD_WHITE);
      } else {
        display.setTextColor(GxEPD_BLACK);
      }
      display.setCursor(MARGIN, cursorY);
      display.print(items[i]);
    }

    display.setTextColor(GxEPD_BLACK);
  } while (display.nextPage());
}

// ---------------------------------------------------------------------------
// WiFi upload screen
// ---------------------------------------------------------------------------

void showWifiScreen(const char* ip) {
  display.setFullWindow();
  display.firstPage();
  do {
    display.fillScreen(GxEPD_WHITE);
    display.setFont(&FreeMonoBold9pt7b);
    display.setTextColor(GxEPD_BLACK);

    display.setCursor(MARGIN, MARGIN + LINE_HEIGHT);
    display.print("WiFi Upload Mode");
    display.setCursor(MARGIN, MARGIN + LINE_HEIGHT * 2 + 4);
    display.print("IP: ");
    display.print(ip);
    display.setCursor(MARGIN, MARGIN + LINE_HEIGHT * 3 + 4);
    display.print("http://");
    display.print(ip);
  } while (display.nextPage());
}
