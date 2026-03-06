#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include "sd_manager.h"
#include "display.h"   // for CHARS_PER_LINE, LINES_PER_PAGE

// --- SD card pins (HSPI / SPI3) ---
#define SD_CS    18
#define SD_SCK   17
#define SD_MOSI  15
#define SD_MISO  16

static SPIClass sdSPI(HSPI);
static bool usingSD = false;
static File bookFile;

// Built-in sample text shown when no book is open.
static const char* fallbackText =
  "It was the best of times, it was the worst of times, "
  "it was the age of wisdom, it was the age of foolishness, "
  "it was the epoch of belief, it was the epoch of incredulity, "
  "it was the season of Light, it was the season of Darkness, "
  "it was the spring of hope, it was the winter of despair, "
  "we had everything before us, we had nothing before us.";

int totalPages = 0;
static uint32_t pageOffsets[MAX_PAGES];

bool initSD() {
  sdSPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  if (!SD.begin(SD_CS, sdSPI)) {
    Serial.println("SD init failed");
    return false;
  }
  Serial.println("SD card OK");
  return true;
}

int listBooks(char names[][MAX_NAME_LEN], int maxBooks) {
  int count = 0;
  File root = SD.open("/");
  if (!root) return 0;
  File f = root.openNextFile();
  while (f && count < maxBooks) {
    String name  = f.name();
    bool   isDir = f.isDirectory();
    f.close();
    if (!isDir) {
      String lower = name;
      lower.toLowerCase();
      if (lower.endsWith(".txt")) {
        strncpy(names[count], name.c_str(), MAX_NAME_LEN - 1);
        names[count][MAX_NAME_LEN - 1] = '\0';
        count++;
      }
    }
    f = root.openNextFile();
  }
  root.close();
  return count;
}

bool openBook(const char* filename) {
  if (bookFile) bookFile.close();
  String path = (filename[0] == '/') ? String(filename) : "/" + String(filename);
  bookFile = SD.open(path);
  if (!bookFile) {
    Serial.printf("Failed to open %s\n", path.c_str());
    usingSD = false;
    return false;
  }
  usingSD = true;
  Serial.printf("Opened %s\n", path.c_str());
  return true;
}

void scanPages() {
  int charsPerPage = CHARS_PER_LINE * LINES_PER_PAGE;
  totalPages = 0;

  if (usingSD) {
    bookFile.seek(0);
    pageOffsets[totalPages++] = 0;
    uint32_t charCount = 0;
    while (bookFile.available() && totalPages < MAX_PAGES) {
      bookFile.read();
      charCount++;
      if (charCount % charsPerPage == 0)
        pageOffsets[totalPages++] = bookFile.position();
    }
  } else {
    int textLen = strlen(fallbackText);
    pageOffsets[totalPages++] = 0;
    for (int i = charsPerPage; i < textLen && totalPages < MAX_PAGES; i += charsPerPage)
      pageOffsets[totalPages++] = i;
  }

  Serial.printf("Scanned %d pages\n", totalPages);
}

int getLine(int pageNum, int lineNum, char* buf, int maxLen) {
  int len = 0;
  uint32_t offset = pageOffsets[pageNum] + ((uint32_t)lineNum * maxLen);

  if (usingSD) {
    bookFile.seek(offset);
    while (len < maxLen && bookFile.available())
      buf[len++] = (char)bookFile.read();
  } else {
    int textLen = strlen(fallbackText);
    while (len < maxLen && (offset + len) < (uint32_t)textLen) {
      buf[len] = fallbackText[offset + len];
      len++;
    }
  }

  buf[len] = '\0';
  return len;
}
