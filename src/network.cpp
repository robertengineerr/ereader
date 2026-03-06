#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <SD.h>
#include "network.h"
#include "display.h"
#include "secrets.h"
#include "web_ui.h"

static WebServer server(80);
static File uploadFile;

static void handleRoot() {
  server.send(200, "text/html", HTML_PAGE);
}

static void handleFileList() {
  String json = "[";
  File root = SD.open("/");
  File f = root.openNextFile();
  bool first = true;
  while (f) {
    String name   = f.name();
    bool   isDir  = f.isDirectory();
    size_t size   = f.size();
    f.close();  // release handle before filtering
    if (!isDir) {
      String lower = name;
      lower.toLowerCase();
      if (lower.endsWith(".txt")) {
        if (!first) json += ",";
        json += "{\"name\":\"" + name + "\",\"size\":" + size + "}";
        first = false;
      }
    }
    f = root.openNextFile();
  }
  root.close();
  json += "]";
  server.send(200, "application/json", json);
}

static void handleFileUpload() {
  HTTPUpload& upload = server.upload();
  if (upload.status == UPLOAD_FILE_START) {
    // Strip any directory prefix the browser may include
    String fname = upload.filename;
    int slash = fname.lastIndexOf('/');
    if (slash >= 0) fname = fname.substring(slash + 1);

    String path = "/" + fname;
    String lower = path; lower.toLowerCase();
    if (!lower.endsWith(".txt")) path += ".txt";

    Serial.printf("Upload start: %s\n", path.c_str());
    uploadFile = SD.open(path, FILE_WRITE);
    if (!uploadFile) {
      Serial.printf("ERROR: SD.open failed for %s — SD mounted? Card present?\n", path.c_str());
    }
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    if (uploadFile) uploadFile.write(upload.buf, upload.currentSize);
  } else if (upload.status == UPLOAD_FILE_END) {
    if (uploadFile) {
      uploadFile.close();
      Serial.printf("Upload done: %u bytes\n", upload.totalSize);
    } else {
      Serial.println("Upload end — but file was never opened (write failed)");
    }
  }
}

static void handleDelete() {
  if (!server.hasArg("name")) { server.send(400, "text/plain", "Missing name"); return; }
  String path = server.arg("name");
  if (!path.startsWith("/")) path = "/" + path;
  if (SD.remove(path)) {
    server.send(200, "text/plain", "Deleted");
  } else {
    server.send(404, "text/plain", "Not found");
  }
}

void runWifiMode() {
  Serial.println("Connecting to WiFi...");
  showWifiScreen("Connecting...");

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 30) {
    delay(500);
    tries++;
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection failed — check secrets.h");
    showWifiScreen("Connect failed");
    return;
  }

  String ip = WiFi.localIP().toString();
  Serial.printf("Connected. IP: %s\n", ip.c_str());

  server.on("/",           HTTP_GET,    handleRoot);
  server.on("/api/files",  HTTP_GET,    handleFileList);
  server.on("/api/upload", HTTP_POST,
    []() { server.send(200, "text/plain", "OK"); },
    handleFileUpload
  );
  server.on("/api/file",   HTTP_DELETE, handleDelete);
  server.begin();

  showWifiScreen(ip.c_str());
  Serial.printf("Browse to http://%s\n", ip.c_str());

  while (true) {
    server.handleClient();
    delay(1);
  }
}
