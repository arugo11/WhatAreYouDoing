#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include "esp_camera.h"
#include "config.h"

bool pirDetected = false;
unsigned long lastDetectionTime = 0;
bool wifiConnected = false;

// カメラの設定
camera_config_t config;

// プロトタイプ宣言
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
  
  // コンポーネント初期化
  setupCamera();
  setupWiFi();
  setupSensors();
  setupPIR();
  
  debugPrint("Setup completed. Waiting for motion detection...");
}

void loop() {
  // 人感センサが動きを感知してクールダウン時間が過ぎたかチェック
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
  
  // WiFi接続の確認
  if (WiFi.status() != WL_CONNECTED) {
    debugPrint("WiFi disconnected. Reconnecting...");
    setupWiFi();
  }
  
  delay(100);  // 無限ループ対策
}

void setupCamera() {
  debugPrint("Initializing camera...");
  
  // unit cam用のカメラピン設定
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
  
  // カメラを初期化
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
  
  // I2C通信の初期化
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
  
  // センサーとの通信テスト
  Wire.beginTransmission(SHT40_I2C_ADDRESS);
  if (Wire.endTransmission() == 0) {
    debugPrint("SHT40 sensor detected");
  } else {
    debugPrint("SHT40 sensor not found");
  }
  
  Wire.beginTransmission(BH1750_I2C_ADDRESS);
  if (Wire.endTransmission() == 0) {
    debugPrint("BH1750 sensor detected");
    // 照度センサーを初期化
    Wire.beginTransmission(BH1750_I2C_ADDRESS);
    Wire.write(0x01);  // 電源をオン
    Wire.endTransmission();
    Wire.beginTransmission(BH1750_I2C_ADDRESS);
    Wire.write(0x10);  // 連続高解像度モード
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
  
  // 画像を取得
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    debugPrint("Camera capture failed");
    return false;
  }
  
  // センサーデータを取得
  float temperature = readTemperature();
  float humidity = readHumidity();
  float illuminance = readIlluminance();
  
  // JSONに整形
  StaticJsonDocument<200> jsonDoc;
  jsonDoc["temperature"] = temperature;
  jsonDoc["humidity"] = humidity;
  jsonDoc["illuminance"] = illuminance;
  
  String jsonString;
  serializeJson(jsonDoc, jsonString);
  
  // HTTPリクエストを送信
  bool success = false; // 成功フラグ
  for (int attempt = 0; attempt < RETRY_ATTEMPTS && !success; attempt++) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.setTimeout(SERVER_TIMEOUT);
    

    String boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW";
    String contentType = "multipart/form-data; boundary=" + boundary;

    String body = "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"metadata\"\r\n\r\n";
    body += jsonString + "\r\n";
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"image\"; filename=\"image.jpg\"\r\n";
    body += "Content-Type: image/jpeg\r\n\r\n";
    
    String footer = "\r\n--" + boundary + "--\r\n";
    
    // コンテンツ長の算出
    int contentLength = body.length() + fb->len + footer.length();
    
    // ヘッダーの設定
    http.addHeader("Content-Type", contentType);
    http.addHeader("Content-Length", String(contentLength));
    
    // POSTリクエスト
    int httpResponseCode = http.POST("");
    
    // マルチパートデータ送信
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
  
  // フレームバッファ
  esp_camera_fb_return(fb);
  
  return success;
}

float readTemperature() {
  // SHT40温度読み取り
  Wire.beginTransmission(SHT40_I2C_ADDRESS);
  Wire.write(0xFD);
  Wire.endTransmission();
  
  delay(10);  // wait
  
  Wire.requestFrom(SHT40_I2C_ADDRESS, 6);
  
  if (Wire.available() >= 6) {
    uint16_t temp_raw = (Wire.read() << 8) | Wire.read();
    uint8_t temp_crc = Wire.read();
    uint16_t hum_raw = (Wire.read() << 8) | Wire.read();
    uint8_t hum_crc = Wire.read();
    
    // セルシウス温度に変換
    float temperature = -45.0 + 175.0 * temp_raw / 65535.0;
    return temperature;
  }
  
  return 25.0;  // センサー失敗時のダミーの値
}

float readHumidity() {
  // SHT40湿度読み取り
  Wire.beginTransmission(SHT40_I2C_ADDRESS);
  Wire.write(0xFD);
  Wire.endTransmission();
  
  delay(10);  // wait
  
  Wire.requestFrom(SHT40_I2C_ADDRESS, 6);
  
  if (Wire.available() >= 6) {
    uint16_t temp_raw = (Wire.read() << 8) | Wire.read();
    uint8_t temp_crc = Wire.read();
    uint16_t hum_raw = (Wire.read() << 8) | Wire.read();
    uint8_t hum_crc = Wire.read();
    
    // 湿度に変換
    float humidity = -6.0 + 125.0 * hum_raw / 65535.0;
    return humidity;
  }
  
  return 50.0;  // センサー失敗時のダミー値
}

float readIlluminance() {
  // BH1750照度読み取り
  Wire.requestFrom(BH1750_I2C_ADDRESS, 2);
  
  if (Wire.available() >= 2) {
    uint16_t lux_raw = (Wire.read() << 8) | Wire.read();
    float lux = lux_raw / 1.2;  // luxに変換
    return lux;
  }
  
  return 300.0;  // センサー失敗時のダミー値
}

void debugPrint(String message) {
  if (DEBUG_ENABLED) {
    Serial.println("[DEBUG] " + message);
  }
} 