#pragma once

// Connect to the home WiFi network defined in secrets.h, start the web
// server, and display the device IP on screen. Blocks forever (call only
// when entering upload mode at boot).
void runWifiMode();
