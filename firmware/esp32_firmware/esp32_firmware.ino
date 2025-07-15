#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include "esp_camera.h"
#include "config.h"

// Global variables
bool pirDetected = false;
unsigned long lastDetectionTime = 0;
bool wifiConnected = false;

// Camera configuration
camera_config_t config;

// Function prototypes
void setupCamera();
void setupWiFi();
void setupSensors();
void setupPIR();
bool captureAndSend();
float readTemperature();
float readHumidity();
float readIlluminance();
void debugPrint(String message);
void handlePIRInterrupt();

void setup() {
  Serial.begin(DEBUG_SERIAL_SPEED);
  debugPrint("Starting WhatAreYouDoing ESP32-CAM...");
  
  // Initialize components
  setupCamera();
  setupWiFi();
  setupSensors();
  setupPIR();
  
  debugPrint("Setup completed. Waiting for motion detection...");
}

void loop() {
  // Check if PIR detected motion and cooldown period has passed
  if (pirDetected && (millis() - lastDetectionTime > DETECTION_COOLDOWN)) {
    pirDetected = false;
    
    debugPrint("Motion detected! Capturing and sending data...");
    
    if (captureAndSend()) {
      debugPrint("Data sent successfully");
    } else {
      debugPrint("Failed to send data");
    }
    
    lastDetectionTime = millis();
  }
  
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    debugPrint("WiFi disconnected. Reconnecting...");
    setupWiFi();
  }
  
  delay(100);  // Small delay to prevent busy loop
}

void setupCamera() {
  debugPrint("Initializing camera...");
  
  // Camera pin configuration for M5Stack Unit CAM
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = 32;
  config.pin_d1 = 35;
  config.pin_d2 = 34;
  config.pin_d3 = 5;
  config.pin_d4 = 39;
  config.pin_d5 = 18;
  config.pin_d6 = 36;
  config.pin_d7 = 19;
  config.pin_xclk = 27;
  config.pin_pclk = 21;
  config.pin_vsync = 22;
  config.pin_href = 26;
  config.pin_sscb_sda = 25;
  config.pin_sscb_scl = 23;
  config.pin_pwdn = -1;
  config.pin_reset = 15;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = CAMERA_FRAME_SIZE;
  config.jpeg_quality = CAMERA_JPEG_QUALITY;
  config.fb_count = 1;
  
  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    debugPrint("Camera init failed with error 0x" + String(err, HEX));
    return;
  }
  
  debugPrint("Camera initialized successfully");
}

void setupWiFi() {
  debugPrint("Connecting to WiFi...");
  
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(1000);
    debugPrint(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    debugPrint("WiFi connected!");
    debugPrint("IP address: " + WiFi.localIP().toString());
  } else {
    wifiConnected = false;
    debugPrint("WiFi connection failed!");
  }
}

void setupSensors() {
  debugPrint("Initializing I2C sensors...");
  
  // Initialize I2C
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  
  // Test sensor communication
  Wire.beginTransmission(SHT40_I2C_ADDRESS);
  if (Wire.endTransmission() == 0) {
    debugPrint("SHT40 sensor detected");
  } else {
    debugPrint("SHT40 sensor not found");
  }
  
  Wire.beginTransmission(BH1750_I2C_ADDRESS);
  if (Wire.endTransmission() == 0) {
    debugPrint("BH1750 sensor detected");
    // Initialize BH1750
    Wire.beginTransmission(BH1750_I2C_ADDRESS);
    Wire.write(0x01);  // Power on
    Wire.endTransmission();
    Wire.beginTransmission(BH1750_I2C_ADDRESS);
    Wire.write(0x10);  // Continuous H-resolution mode
    Wire.endTransmission();
  } else {
    debugPrint("BH1750 sensor not found");
  }
}

void setupPIR() {
  debugPrint("Initializing PIR sensor...");
  
  pinMode(PIR_SENSOR_PIN, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIR_SENSOR_PIN), handlePIRInterrupt, RISING);
  
  debugPrint("PIR sensor initialized");
}

void handlePIRInterrupt() {
  pirDetected = true;
}

bool captureAndSend() {
  if (!wifiConnected) {
    debugPrint("WiFi not connected");
    return false;
  }
  
  // Capture image
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    debugPrint("Camera capture failed");
    return false;
  }
  
  // Read sensor data
  float temperature = readTemperature();
  float humidity = readHumidity();
  float illuminance = readIlluminance();
  
  // Create JSON metadata
  StaticJsonDocument<200> jsonDoc;
  jsonDoc["temperature"] = temperature;
  jsonDoc["humidity"] = humidity;
  jsonDoc["illuminance"] = illuminance;
  
  String jsonString;
  serializeJson(jsonDoc, jsonString);
  
  // Send HTTP request with retry logic
  bool success = false;
  for (int attempt = 0; attempt < RETRY_ATTEMPTS && !success; attempt++) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.setTimeout(SERVER_TIMEOUT);
    
    // Create multipart form data
    String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
    String contentType = "multipart/form-data; boundary=" + boundary;
    
    // Build the multipart body
    String body = "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"metadata\"\r\n\r\n";
    body += jsonString + "\r\n";
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"image\"; filename=\"image.jpg\"\r\n";
    body += "Content-Type: image/jpeg\r\n\r\n";
    
    String footer = "\r\n--" + boundary + "--\r\n";
    
    // Calculate content length
    int contentLength = body.length() + fb->len + footer.length();
    
    // Set headers
    http.addHeader("Content-Type", contentType);
    http.addHeader("Content-Length", String(contentLength));
    
    // Begin POST request
    int httpResponseCode = http.POST("");
    
    // Send the multipart data
    WiFiClient* client = http.getStreamPtr();
    client->print(body);
    client->write(fb->buf, fb->len);
    client->print(footer);
    
    if (httpResponseCode == 200) {
      String response = http.getString();
      debugPrint("HTTP Response: " + response);
      success = true;
    } else {
      debugPrint("HTTP Error (attempt " + String(attempt + 1) + "): " + String(httpResponseCode));
      if (attempt < RETRY_ATTEMPTS - 1) {
        delay(RETRY_DELAY);
      }
    }
    
    http.end();
  }
  
  // Release frame buffer
  esp_camera_fb_return(fb);
  
  return success;
}

float readTemperature() {
  // SHT40 temperature reading
  Wire.beginTransmission(SHT40_I2C_ADDRESS);
  Wire.write(0xFD);  // High precision measurement command
  Wire.endTransmission();
  
  delay(10);  // Wait for measurement
  
  Wire.requestFrom(SHT40_I2C_ADDRESS, 6);
  
  if (Wire.available() >= 6) {
    uint16_t temp_raw = (Wire.read() << 8) | Wire.read();
    uint8_t temp_crc = Wire.read();
    uint16_t hum_raw = (Wire.read() << 8) | Wire.read();
    uint8_t hum_crc = Wire.read();
    
    // Convert to temperature (°C)
    float temperature = -45.0 + 175.0 * temp_raw / 65535.0;
    return temperature;
  }
  
  return 25.0;  // Default value if sensor fails
}

float readHumidity() {
  // SHT40 humidity reading
  Wire.beginTransmission(SHT40_I2C_ADDRESS);
  Wire.write(0xFD);  // High precision measurement command
  Wire.endTransmission();
  
  delay(10);  // Wait for measurement
  
  Wire.requestFrom(SHT40_I2C_ADDRESS, 6);
  
  if (Wire.available() >= 6) {
    uint16_t temp_raw = (Wire.read() << 8) | Wire.read();
    uint8_t temp_crc = Wire.read();
    uint16_t hum_raw = (Wire.read() << 8) | Wire.read();
    uint8_t hum_crc = Wire.read();
    
    // Convert to humidity (%)
    float humidity = -6.0 + 125.0 * hum_raw / 65535.0;
    return humidity;
  }
  
  return 50.0;  // Default value if sensor fails
}

float readIlluminance() {
  // BH1750 illuminance reading
  Wire.requestFrom(BH1750_I2C_ADDRESS, 2);
  
  if (Wire.available() >= 2) {
    uint16_t lux_raw = (Wire.read() << 8) | Wire.read();
    float lux = lux_raw / 1.2;  // Convert to lux
    return lux;
  }
  
  return 300.0;  // Default value if sensor fails
}

void debugPrint(String message) {
  if (DEBUG_ENABLED) {
    Serial.println("[DEBUG] " + message);
  }
} 