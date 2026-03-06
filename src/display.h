#pragma once

#include "sd_manager.h"  // for MAX_NAME_LEN

// --- Reading grid layout (296x128 display, landscape rotation) ---
#define DISPLAY_W       296
#define DISPLAY_H       128
#define MARGIN            8
#define LINE_HEIGHT      18
#define CHARS_PER_LINE   38
#define LINES_PER_PAGE    5
#define LIBRARY_VISIBLE   4  // list rows visible at once (1 line reserved for header)

void initDisplay();

// Reading screen
void showPage(int pageNum);

// Navigation screens
void showBootScreen();
void showLibraryScreen(char names[][MAX_NAME_LEN], int count, int selected, int scroll);
void showSettingsScreen(const char** items, int count, int selected);

// WiFi upload screen (ip = IP address string, or "Connecting..." / "Connect failed")
void showWifiScreen(const char* ip);
