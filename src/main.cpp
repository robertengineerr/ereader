#include <Arduino.h>
#include "display.h"
#include "sd_manager.h"
#include "network.h"

// --- 5-way joystick ---
// COM is wired to a GPIO configured OUTPUT LOW (virtual GND)
#define JOY_COM  35
#define JOY_UP   36
#define JOY_DWN  37
#define JOY_LFT  38
#define JOY_RHT  39
#define JOY_MID  40
#define JOY_SET  41  // hold at boot to enter WiFi upload mode
#define JOY_RST  42

#define DEBOUNCE_MS 200

// Flags set by ISRs; read and cleared in loop()
static volatile bool ev_up    = false;
static volatile bool ev_down  = false;
static volatile bool ev_left  = false;
static volatile bool ev_right = false;
static volatile bool ev_mid   = false;

// Per-button last-fire timestamp for ISR-side debounce
static volatile uint32_t t_up    = 0;
static volatile uint32_t t_down  = 0;
static volatile uint32_t t_left  = 0;
static volatile uint32_t t_right = 0;
static volatile uint32_t t_mid   = 0;

static void IRAM_ATTR isr_up()    { uint32_t n=millis(); if(n-t_up   >DEBOUNCE_MS){ev_up   =true;t_up   =n;} }
static void IRAM_ATTR isr_down()  { uint32_t n=millis(); if(n-t_down >DEBOUNCE_MS){ev_down =true;t_down =n;} }
static void IRAM_ATTR isr_left()  { uint32_t n=millis(); if(n-t_left >DEBOUNCE_MS){ev_left =true;t_left =n;} }
static void IRAM_ATTR isr_right() { uint32_t n=millis(); if(n-t_right>DEBOUNCE_MS){ev_right=true;t_right=n;} }
static void IRAM_ATTR isr_mid()   { uint32_t n=millis(); if(n-t_mid  >DEBOUNCE_MS){ev_mid  =true;t_mid  =n;} }

// --- App state ---
enum AppState { LIBRARY, READING, SETTINGS };

static AppState appState     = LIBRARY;
static int      selectedItem = 0;   // cursor position in LIBRARY or SETTINGS
static int      listScroll   = 0;   // scroll offset for LIBRARY list
static int      currentPage  = 0;

static char bookNames[MAX_BOOKS][MAX_NAME_LEN];
static int  bookCount = 0;

static const char* settingsItems[] = { "WiFi Upload", "Back" };
static const int   SETTINGS_COUNT  = 2;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static void clampScroll(int selected, int& scroll, int visible, int total) {
  if (selected < scroll)            scroll = selected;
  if (selected >= scroll + visible) scroll = selected - visible + 1;
}

static void enterLibrary() {
  bookCount    = listBooks(bookNames, MAX_BOOKS);
  selectedItem = 0;
  listScroll   = 0;
  appState     = LIBRARY;
  showLibraryScreen(bookNames, bookCount, selectedItem, listScroll);
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);

  // Joystick: COM acts as virtual GND so direction pins read LOW when pressed
  pinMode(JOY_COM, OUTPUT);
  digitalWrite(JOY_COM, LOW);
  pinMode(JOY_UP,  INPUT_PULLUP);
  pinMode(JOY_DWN, INPUT_PULLUP);
  pinMode(JOY_LFT, INPUT_PULLUP);
  pinMode(JOY_RHT, INPUT_PULLUP);
  pinMode(JOY_MID, INPUT_PULLUP);
  pinMode(JOY_SET, INPUT_PULLUP);
  pinMode(JOY_RST, INPUT_PULLUP);

  attachInterrupt(JOY_UP,  isr_up,    FALLING);
  attachInterrupt(JOY_DWN, isr_down,  FALLING);
  attachInterrupt(JOY_LFT, isr_left,  FALLING);
  attachInterrupt(JOY_RHT, isr_right, FALLING);
  attachInterrupt(JOY_MID, isr_mid,   FALLING);

  initSD();
  initDisplay();

  // Hold SET at boot → WiFi upload mode (never returns on success)
  if (digitalRead(JOY_SET) == LOW) {
    runWifiMode();
  }

  showBootScreen();
  delay(1000);
  enterLibrary();
}

// ---------------------------------------------------------------------------
// Loop — state machine
// ---------------------------------------------------------------------------

void loop() {
  if (!ev_up && !ev_down && !ev_left && !ev_right && !ev_mid) return;

  // Snapshot and clear flags atomically
  bool up    = ev_up;    ev_up    = false;
  bool down  = ev_down;  ev_down  = false;
  bool left  = ev_left;  ev_left  = false;
  bool right = ev_right; ev_right = false;
  bool mid   = ev_mid;   ev_mid   = false;

  int totalItems;

  switch (appState) {

    // ---- Library ----
    case LIBRARY:
      totalItems = bookCount + 1;  // books + "Settings"
      if (up && selectedItem > 0) {
        selectedItem--;
        clampScroll(selectedItem, listScroll, LIBRARY_VISIBLE, totalItems);
        showLibraryScreen(bookNames, bookCount, selectedItem, listScroll);
      } else if (down && selectedItem < totalItems - 1) {
        selectedItem++;
        clampScroll(selectedItem, listScroll, LIBRARY_VISIBLE, totalItems);
        showLibraryScreen(bookNames, bookCount, selectedItem, listScroll);
      } else if (mid) {
        if (selectedItem < bookCount) {
          if (openBook(bookNames[selectedItem])) {
            scanPages();
            currentPage = 0;
            appState    = READING;
            showPage(currentPage);
          }
        } else {
          selectedItem = 0;
          listScroll   = 0;
          appState     = SETTINGS;
          showSettingsScreen(settingsItems, SETTINGS_COUNT, selectedItem);
        }
      }
      break;

    // ---- Reading ----
    case READING:
      if ((down || right) && currentPage < totalPages - 1) {
        currentPage++;
        showPage(currentPage);
      } else if (up && currentPage > 0) {
        currentPage--;
        showPage(currentPage);
      } else if (left || mid) {
        enterLibrary();
      }
      break;

    // ---- Settings ----
    case SETTINGS:
      if (up && selectedItem > 0) {
        selectedItem--;
        showSettingsScreen(settingsItems, SETTINGS_COUNT, selectedItem);
      } else if (down && selectedItem < SETTINGS_COUNT - 1) {
        selectedItem++;
        showSettingsScreen(settingsItems, SETTINGS_COUNT, selectedItem);
      } else if (mid) {
        if (selectedItem == 0) {
          runWifiMode();  // blocks forever (or returns on connect failure)
        } else {
          enterLibrary();
        }
      } else if (left) {
        enterLibrary();
      }
      break;
  }
}
