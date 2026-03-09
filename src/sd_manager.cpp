#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include "sd_manager.h"
#include "display.h"   // for CHARS_PER_LINE, LINES_PER_PAGE

// --- SD card pins (HSPI / SPI3) ---
#define SD_CS    15
#define SD_MOSI  16
#define SD_SCK   17
#define SD_MISO  18

static SPIClass sdSPI(HSPI);
static bool sdMounted = false;
static bool usingSD   = false;
static File bookFile;

// Built-in sample — The Iliad, Book I (Alexander Pope translation, 1899, public domain)
static const char* fallbackText =
  "THE ILIAD OF HOMER - BOOK I\n"
  "Translated by Alexander Pope\n\n"
  "Achilles' wrath, to Greece the direful spring\n"
  "Of woes unnumber'd, heavenly goddess, sing!\n"
  "That wrath which hurl'd to Pluto's gloomy reign\n"
  "The souls of mighty chiefs untimely slain;\n"
  "Whose limbs unburied on the naked shore,\n"
  "Devouring dogs and hungry vultures tore.\n"
  "Since great Achilles and Atrides strove,\n"
  "Such was the sovereign doom, and such the will of Jove!\n"
  "Declare, O Muse! in what ill-fated hour\n"
  "Sprung the fierce strife, from what offended power\n"
  "Latona's son a dire contagion spread,\n"
  "And heap'd the camp with mountains of the dead;\n"
  "The king of men his reverent priest defied,\n"
  "And for the king's offence the people died.\n\n"
  "For Chryses sought with costly gifts to gain\n"
  "His captive daughter from the victor's chain.\n"
  "Suppliant the venerable father stands;\n"
  "Apollo's awful ensigns grace his hands:\n"
  "By these he begs; and lowly bending down,\n"
  "Extends the sceptre and the laurel crown.\n"
  "He sued to all, but chief implored for grace\n"
  "The brother-kings, of Atreus' royal race:\n"
  "\"Ye kings and warriors! may your vows be crown'd,\n"
  "And Troy's proud walls lie level with the ground.\n"
  "May Jove restore you when your toils are o'er\n"
  "Safe to the pleasures of your native shore.\n"
  "But, oh! relieve a wretched parent's pain,\n"
  "And give Chryseis to these arms again;\n"
  "If mercy fail, yet let my presents move,\n"
  "And dread avenging Phoebus, son of Jove.\"\n\n"
  "The Greeks in shouts their joint assent declare,\n"
  "The priest to reverence, and release the fair.\n"
  "Not so Atrides; he, with kingly pride,\n"
  "Repulsed the sacred sire, and thus replied:\n"
  "\"Hence on thy life, and fly these hostile plains,\n"
  "Nor ask, presumptuous, what the king detains:\n"
  "Hence, with thy laurel crown, and golden rod,\n"
  "Nor trust too far those ensigns of thy god.\n"
  "Mine is thy daughter, priest, and shall remain;\n"
  "And prayers, and tears, and bribes, shall plead in vain;\n"
  "Till time shall rifle every youthful grace,\n"
  "And age dismiss her from my cold embrace,\n"
  "In daily labours of the loom employ'd,\n"
  "Or doom'd to deck the bed she once enjoy'd.\n"
  "Hence then; to Argos shall the maid retire,\n"
  "Far from her native soil and weeping sire.\"\n\n"
  "The trembling priest along the shore return'd,\n"
  "And in the anguish of a father mourn'd.\n"
  "Disconsolate, not daring to complain,\n"
  "Silent he wander'd by the sounding main;\n"
  "Till, safe at distance, to his god he prays,\n"
  "The god who darts around the world his rays:\n"
  "\"O Smintheus! sprung from fair Latona's line,\n"
  "Thou guardian power of Cilla the divine,\n"
  "Thou source of light! whom Tenedos adores,\n"
  "And whose bright presence gilds thy Chrysa's shores.\n"
  "If e'er with wreaths I hung thy sacred fane,\n"
  "Or fed the flames with fat of oxen slain;\n"
  "God of the silver bow! thy shafts employ,\n"
  "Avenge thy servant, and the Greeks destroy.\"\n\n"
  "Thus Chryses pray'd: the favouring power attends,\n"
  "And from Olympus' lofty tops descends.\n"
  "Bent was his bow, the Grecian hearts to wound;\n"
  "Fierce as he moved, his silver shafts resound.\n"
  "Breathing revenge, a sudden night he spread,\n"
  "And gloomy darkness roll'd about his head.\n"
  "The fleet in view, he twang'd his deadly bow,\n"
  "And hissing fly the feather'd fates below.\n"
  "On mules and dogs the infection first began;\n"
  "And last, the vengeful arrows fix'd in man.\n"
  "For nine long nights, through all the dusky air,\n"
  "The pyres, thick-flaming, shot a dismal glare.";

int totalPages = 0;
static uint32_t pageOffsets[MAX_PAGES];

bool initSD() {
  delay(100);  // let card power stabilise
  sdSPI.begin(SD_SCK, SD_MISO, SD_MOSI, -1);
  if (!SD.begin(SD_CS, sdSPI, 4000000)) {
    Serial.println("=== SD FAILED — check wiring and FAT32 format ===");
    sdMounted = false;
    return false;
  }
  uint8_t t = SD.cardType();
  Serial.printf("=== SD OK: %s, %llu MB ===\n",
    t==CARD_MMC?"MMC": t==CARD_SD?"SD": t==CARD_SDHC?"SDHC":"?",
    SD.cardSize() / (1024ULL * 1024));
  sdMounted = true;
  return true;
}

int listBooks(char names[][MAX_NAME_LEN], int maxBooks) {
  if (!sdMounted) return 0;
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
