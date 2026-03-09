#pragma once

#include "sd_manager.h"  // for MAX_NAME_LEN

// --- Reading grid layout (800x480 display, portrait rotation) ---
#define DISPLAY_W       480
#define DISPLAY_H       800
#define MARGIN           12
#define LINE_HEIGHT      24   // FreeMonoBold12pt7b: ~22px glyph + 2px leading
#define CHARS_PER_LINE   30   // (480 - 2*MARGIN) / ~14px per char
#define LINES_PER_PAGE   30
#define LIBRARY_VISIBLE  26   // list rows visible at once (1 line reserved for header)

void initDisplay();

// Reading screen
void showPage(int pageNum);

// Navigation screens
void showBootScreen();
void showLibraryScreen(char names[][MAX_NAME_LEN], int count, int selected, int scroll);
void showSettingsScreen(const char** items, int count, int selected);

// WiFi upload screen (ip = IP address string, or "Connecting..." / "Connect failed")
void showWifiScreen(const char* ip);

void showPressAnyButton();
