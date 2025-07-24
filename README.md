# WhatAreYouDoing? 行動判定システム

ESP32-CAMとGoogle Gemini AIを使用して部屋の状況をリアルタイムで監視し、行動を自動分類するシステムです。

## 主な機能

- **リアルタイム行動分類**: 6種類の行動を自動判定（PC_WORK, GAMING, SLEEPING, AWAKE_IN_BED, AWAY, OTHER）
- **センサー統合**: 温度・湿度・照度データと画像分析の組み合わせ
- **REST API**: 他システムとの連携用APIインターフェース

## 必要な環境

- Python 3.12以上
- uv（Pythonパッケージマネージャー）
- Google Gemini API キー
- Arduino IDE（ESP32開発用）

## セットアップ

### 1. サーバーセットアップ

```bash
cd server
uv sync
cp env.example .env
# .envファイルを編集してGemini APIキーを設定
uv run python main.py
```

### 2. ESP32-CAM セットアップ

```bash
cd firmware/esp32_firmware
cp config.h.example config.h
# config.hファイルでWiFi設定とサーバーURLを設定
# Arduino IDEでファームウェアをアップロード
```

## API使用例

```bash
# 現在の状態確認
curl http://localhost:8000/api/now

# 健康状態確認
curl http://localhost:8000/api/health

# 特定時刻の状態
curl http://localhost:8000/api/events/by-time/2025/7/13/14/30
```
