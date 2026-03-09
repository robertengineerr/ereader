#pragma once

#include <stdint.h>

#define MAX_PAGES    512
#define MAX_BOOKS     32
#define MAX_NAME_LEN  128

// Total pages computed by scanPages(); read by display and main.
extern int totalPages;

// Initialize SD card (mount only — book selection happens via openBook).
// Returns true on success. Falls back to built-in sample text on failure.
bool initSD();

// List all .txt files in the SD root. Fills names[][MAX_NAME_LEN] and
// returns the count. Closes all directory handles when done.
int listBooks(char names[][MAX_NAME_LEN], int maxBooks);

// Open a specific book file for reading. Closes any previously open book.
// Returns true on success; on failure usingSD stays false (fallback text used).
bool openBook(const char* filename);

// Walk the open book and record byte offsets for each page.
// Must be called after openBook() and before showPage().
void scanPages();

// Fill buf with up to maxLen characters from line `lineNum` on page `pageNum`.
// Null-terminates buf. Returns number of characters written (0 = end of text).
int getLine(int pageNum, int lineNum, char* buf, int maxLen);
