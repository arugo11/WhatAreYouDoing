# WhatAreYouDoing セットアップガイド

## システム要件

### ハードウェア
- M5Stack ESP32-CAM
- PIR人感センサー、SHT40温湿度センサー、BH1750照度センサー

### ソフトウェア
- Python 3.12以上
- Arduino IDE
- uv（Pythonパッケージマネージャー）

## 1. サーバーセットアップ

```bash
cd server
uv sync
cp env.example .env
```

### 環境変数設定（.env）

```bash
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=sqlite:///./data/whatareyoudoing.db
DATA_RETENTION_DAYS=90
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### サーバー起動

```bash
uv run python main.py
```

## 2. ESP32-CAM セットアップ

### Arduino IDE設定

1. ボードマネージャーURLに追加:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
2. ESP32ボードをインストール
3. 必要ライブラリをインストール: ArduinoJson, AsyncTCP, ESPAsyncWebServer

### ファームウェア設定

```bash
cd firmware/esp32_firmware
cp config.h.example config.h
```

config.hを編集:
```cpp
#define WIFI_SSID "your_wifi_network"
#define WIFI_PASSWORD "your_wifi_password"
#define SERVER_URL "http://192.168.1.100:8000/api/events"
```

### アップロード

1. ESP32-CAMを接続
2. Arduino IDEで「ESP32 Wrover Module」を選択
3. esp32_firmware.inoをアップロード

## 3. ハードウェア接続

```
ESP32-CAM Grove Port (I2C):
├── SHT40, BH1750 → SDA/SCL
└── PIR センサー → GPIO 13
```

## 4. 動作確認

```bash
# API確認
curl http://localhost:8000/api/health

# テスト実行
cd tests
python test_server.py
```
