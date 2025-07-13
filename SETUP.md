# WhatAreYouDoing セットアップガイド

## 概要

このドキュメントは、WhatAreYouDoingプロジェクトの完全なセットアップ手順を説明します。

## システム要件

### ハードウェア
- M5Stack ESP32-CAM (Unit CAM)
- PIR人感センサー
- SHT40 温湿度センサー
- BH1750 照度センサー
- Grove接続ケーブル
- ミニPC（Raspberry Pi等）

### ソフトウェア
- Python 3.12以上
- Arduino IDE
- uv (Pythonパッケージマネージャー)

## 1. サーバー側のセットアップ

### 1.1 プロジェクトの準備

```bash
# プロジェクトディレクトリに移動
cd /path/to/WhatAreYouDoing

# サーバーディレクトリに移動
cd server

# UV仮想環境のセットアップ
uv sync

# 環境変数ファイルの作成
cp env.example .env
```

### 1.2 環境変数の設定

`.env`ファイルを編集して、以下の設定を行います：

```bash
# Gemini API Settings
GEMINI_API_KEY=your_actual_api_key_here

# Database Settings
DATABASE_URL=sqlite:///./data/whatareyoudoing.db

# Data Management
DATA_RETENTION_DAYS=90

# Server Settings
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Data Directories
DATA_DIR=./data
IMAGES_DIR=./data/images
LOGS_DIR=./logs
```

### 1.3 Google Gemini API キーの取得

1. [Google AI Studio](https://makersuite.google.com/app/apikey)にアクセス
2. 新しいAPIキーを作成
3. 作成したAPIキーを`.env`ファイルに設定

### 1.4 サーバーの起動

```bash
# 仮想環境をアクティブ化
source .venv/bin/activate

# サーバーを起動
python main.py
```

または

```bash
# uvを使用してサーバーを起動
uv run python main.py
```

### 1.5 動作確認

ブラウザで`http://localhost:8000/docs`にアクセスし、API文書が表示されることを確認します。

## 2. ESP32-CAM ファームウェアのセットアップ

### 2.1 Arduino IDE の設定

1. Arduino IDEを開く
2. `ファイル` → `環境設定`で追加のボードマネージャーURLに以下を追加：
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. `ツール` → `ボード` → `ボードマネージャー`で「ESP32」を検索してインストール

### 2.2 必要なライブラリのインストール

Arduino IDEのライブラリマネージャーで以下をインストール：

- ArduinoJson (by Benoit Blanchon)
- AsyncTCP (by me-no-dev)
- ESPAsyncWebServer (by me-no-dev)

### 2.3 設定ファイルの作成

```bash
# ファームウェアディレクトリに移動
cd firmware/esp32_firmware

# 設定ファイルを作成
cp config.h.example config.h
```

`config.h`ファイルを編集して、以下の設定を行います：

```cpp
// Wi-Fi Settings
#define WIFI_SSID "your_wifi_network_name"
#define WIFI_PASSWORD "your_wifi_password"

// Server Settings
#define SERVER_URL "http://192.168.1.100:8000/api/events"  // サーバーのIPアドレスに変更
```

### 2.4 ファームウェアのアップロード

1. ESP32-CAMをPCに接続
2. Arduino IDEで`esp32_firmware.ino`を開く
3. `ツール` → `ボード`で「ESP32 Wrover Module」を選択
4. 適切なポートを選択
5. `アップロード`をクリック

## 3. ハードウェアの接続

### 3.1 センサーの接続

```
ESP32-CAM Grove Port:
├── SHT40 (温湿度センサー)
├── BH1750 (照度センサー)
└── PIR センサー → GPIO 13
```

### 3.2 配線図

```
ESP32-CAM
├── Grove Port (I2C)
│   ├── SDA (GPIO 21) → SHT40 & BH1750
│   ├── SCL (GPIO 22) → SHT40 & BH1750
│   ├── VCC (5V) → センサー電源
│   └── GND → センサーGND
└── GPIO 13 → PIR センサー出力
```

## 4. システムの動作確認

### 4.1 基本テスト

```bash
# テストスクリプトを実行
cd tests
python test_server.py
```

### 4.2 手動テスト

1. ESP32-CAMの電源を入れる
2. シリアルモニターで接続状況を確認
3. PIRセンサーの前で動いて検知をテスト
4. サーバーのログで画像とデータの受信を確認

### 4.3 APIエンドポイントのテスト

```bash
# 現在の状態を確認
curl http://localhost:8000/api/now

# 健康状態を確認
curl http://localhost:8000/api/health

# 統計情報を確認
curl http://localhost:8000/api/stats
```

## 5. 運用とメンテナンス

### 5.1 ログの確認

```bash
# サーバーログを確認
tail -f server/logs/app.log

# ESP32のログを確認（シリアルモニター）
```

### 5.2 データベースの管理

```bash
# データベースの場所
ls -la server/data/

# 古いデータの削除（自動実行されるが、手動でも可能）
# 実装により異なる
```

### 5.3 システムの自動起動

#### サーバーの自動起動（systemd）

```bash
# systemdサービスファイルを作成
sudo nano /etc/systemd/system/whatareyoudoing.service
```

```ini
[Unit]
Description=WhatAreYouDoing API Server
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/WhatAreYouDoing/server
ExecStart=/path/to/WhatAreYouDoing/server/.venv/bin/python main.py
Restart=always
RestartSec=10
Environment=PATH=/path/to/WhatAreYouDoing/server/.venv/bin

[Install]
WantedBy=multi-user.target
```

```bash
# サービスを有効化
sudo systemctl enable whatareyoudoing.service
sudo systemctl start whatareyoudoing.service
sudo systemctl status whatareyoudoing.service
```

## 6. トラブルシューティング

### 6.1 よくある問題

#### ESP32-CAMが接続できない
- Wi-Fi設定を確認
- サーバーのIPアドレスを確認
- ファイアウォールの設定を確認

#### 画像がアップロードされない
- カメラの初期化エラーをチェック
- メモリ不足の可能性
- サーバーのディスク容量を確認

#### AI分析が動作しない
- Gemini APIキーが正しいか確認
- インターネット接続を確認
- APIの利用制限を確認

### 6.2 デバッグ方法

```bash
# サーバーのデバッグモード
DEBUG=true uv run python main.py

# ESP32のデバッグ（シリアルモニター）
# config.hでDEBUG_ENABLEDをtrueに設定
```

## 7. 高度な設定

### 7.1 SSL/HTTPS対応

```python
# main.py でSSL設定
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=HOST, 
        port=PORT,
        ssl_keyfile="path/to/private.key",
        ssl_certfile="path/to/certificate.crt"
    )
```

### 7.2 データベースの最適化

```python
# 定期的なデータベース最適化
# crontabで実行
# 0 2 * * * /path/to/cleanup_script.py
```

### 7.3 複数のESP32-CAMの管理

各ESP32-CAMに異なるIDを割り当てて管理する場合の設定例：

```cpp
// config.h
#define DEVICE_ID "camera_01"
```

これにより、複数のカメラからのデータを区別できます。

## 8. 参考資料

- [M5Stack ESP32-CAM 公式ドキュメント](https://docs.m5stack.com/en/unit/esp32cam)
- [Google Gemini API ドキュメント](https://ai.google.dev/docs)
- [FastAPI 公式ドキュメント](https://fastapi.tiangolo.com/)
- [Arduino ESP32 ドキュメント](https://docs.espressif.com/projects/arduino-esp32/en/latest/) 