# WhatAreYouDoing? 行動判定特化システム

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green.svg)
![ESP32](https://img.shields.io/badge/ESP32-CAM-red.svg)
![AI](https://img.shields.io/badge/AI-Gemini-orange.svg)

**WhatAreYouDoing?** は,ESP32-CAMとセンサーを使って部屋の状況をリアルタイムで監視し,Google Gemini AIが行動を自動分類するスマートホームシステムです.

## 主な機能

- **リアルタイム行動分類**: ESP32-CAMとAIによる6種類の行動自動判定
- **センサー統合**: 温度・湿度・照度データと画像の組み合わせ分析
- **REST API**: 他システムとの連携が容易なAPIインターフェース
- **デモモード**: ESP32なしでの動作確認・顧客デモが可能
- **自動データ管理**: 画像とメタデータの自動保存・古いデータの自動削除

## システム構成

```
[ESP32-CAM + センサー] → [APIサーバー] → [AI分析] → [データベース]
```

### ハードウェア構成

- **M5Stack ESP32-CAM (Unit CAM)** - メインカメラユニット
- **PIR人感センサー** - 動作検知トリガー（GPIO 13）
- **SHT40温湿度センサー** - 環境データ取得（I2C）
- **BH1750照度センサー** - 明るさ測定（I2C）

## クイックスタート

### 必要な環境

- Python 3.12以上
- uv (Pythonパッケージマネージャー)
- Google Gemini API キー
- Arduino IDE (ESP32開発用)

### 1. サーバー側セットアップ

```bash
# プロジェクトをクローン
git clone <repository-url>
cd WhatAreYouDoing

# サーバー環境をセットアップ
cd server
uv sync

# 環境変数を設定
cp env.example .env
# .envファイルを編集してGemini APIキーを設定
```

**`.env`ファイルの設定例:**
```bash
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=sqlite:///./data/whatareyoudoing.db
DATA_RETENTION_DAYS=90
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### 2. サーバー起動

```bash
cd server
uv run python main.py
```

サーバーが起動したら,ブラウザで `http://localhost:8000/docs` にアクセスしてAPI文書を確認できます.

### 3. ESP32-CAM セットアップ

```bash
# 設定ファイルを作成
cd firmware/esp32_firmware
cp config.h.example config.h
```

**`config.h`ファイルを編集:**
```cpp
#define WIFI_SSID "your_wifi_network"
#define WIFI_PASSWORD "your_wifi_password"
#define SERVER_URL "http://192.168.1.100:8000/api/events"
```

Arduino IDEでファームウェアをESP32-CAMにアップロードします.

## 📡 API使用方法

### エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|----------|----------------|------|
| `GET` | `/api/now` | 最新の行動ステータスを取得 |
| `GET` | `/api/events/by-time/{年}/{月}/{日}/{時}/{分}` | 指定時刻の行動ステータス |
| `GET` | `/api/health` | サーバーの健康状態確認 |
| `GET` | `/api/stats` | 統計情報取得 |
| `POST` | `/api/events` | イベントデータ受信（ESP32専用） |

### 使用例

#### 現在の状態を確認
```bash
curl http://localhost:8000/api/now
```

**レスポンス例:**
```json
{
  "status": "PC_WORK",
  "timestamp": "2025-07-13T00:36:37.139329",
  "temperature": 25.5,
  "humidity": 60.2,
  "illuminance": 350.0,
  "confidence": "completed"
}
```

#### 特定の時刻の状態を確認
```bash
curl http://localhost:8000/api/events/by-time/2025/7/13/14/30
```

#### システムの健康状態確認
```bash
curl http://localhost:8000/api/health
```

**レスポンス例:**
```json
{
  "status": "healthy",
  "timestamp": "2025-07-13T00:37:31.873695",
  "ai_model": "gemini-1.5-flash-latest",
  "api_configured": true,
  "supported_categories": [
    "PC_WORK", "GAMING", "SLEEPING", 
    "USING_SMARTPHONE", "AWAY", "OTHER"
  ]
}
```

## 行動カテゴリー

| カテゴリー | 説明 | 判定条件 |
|------------|------|----------|
| `PC_WORK` | PC作業中 | デスクに座り,エアコン上にコントローラーあり |
| `GAMING` | ゲーム中 | デスクに座り,エアコン上にコントローラーなし |
| `SLEEPING` | 睡眠中 | ベッドに横になっている |
| `USING_SMARTPHONE` | スマホ操作中 | ベッドに座っている,またはPC以外での活動 |
| `AWAY` | 不在 | 部屋に人が映っていない |
| `OTHER` | その他 | 上記に該当しない,または判定困難 |

## システム設定

### AI分析の重要ルール

このシステムの特徴的な機能として,**ゲームコントローラーの物理的配置**を判定に使用します：

1. **不在判定最優先**: 人が映っていない場合は常に `AWAY`
2. **PC作業 vs ゲーム判定**: 
   - エアコン上にコントローラーが見える → `PC_WORK`
   - エアコン上にコントローラーが見えない → `GAMING`
3. **環境データ活用**: 照度が低い場合の睡眠判定など

### データ管理

- **自動保存**: 画像は`server/data/images/`,データベースは`server/data/whatareyoudoing.db`
- **データ保持**: 90日経過後のデータ自動削除（設定可能）
- **画像形式**: JPEG（VGA 640x480）

## 開発・テスト

### テストの実行

```bash
# APIサーバーのテスト
python tests/test_server.py
```

### デバッグモード

```bash
# デバッグログを有効にして起動
DEBUG=true uv run python main.py
```

## トラブルシューティング

### よくある問題

**Q: ESP32-CAMが接続できない**
- Wi-Fi設定（SSID/パスワード）を確認
- サーバーのIPアドレスが正しいか確認
- ファイアウォール設定を確認

**Q: AI分析が動作しない**
- Gemini APIキーが正しく設定されているか確認
- インターネット接続を確認
- `curl http://localhost:8000/api/health`でAPI設定確認

**Q: 画像がアップロードされない**
- ESP32のシリアルモニターでエラーメッセージ確認
- サーバーのディスク容量確認
- カメラの初期化エラーをチェック

### ログの確認

```bash
# サーバーログ
tail -f server/logs/app.log

# ESP32ログ（Arduino IDEのシリアルモニター）
```

## プロジェクト構造

```
WhatAreYouDoing/
├── README.md              # このファイル
├── SETUP.md              # 詳細セットアップガイド
├── .gitignore            # Git除外設定
├── server/               # Pythonサーバーコード
│   ├── main.py          # FastAPI メインアプリケーション
│   ├── ai_analyzer.py   # AI分析ロジック
│   ├── database.py      # データベース操作
│   ├── models.py        # データモデル定義
│   ├── pyproject.toml   # Python依存関係管理
│   └── env.example      # 環境変数テンプレート
├── firmware/            # ESP32ファームウェア
│   └── esp32_firmware/
│       ├── esp32_firmware.ino  # Arduino主コード
│       └── config.h.example    # 設定テンプレート
└── tests/               # テストコード
    └── test_server.py   # API テストスクリプト
```
## 動作例

システムが正常に動作している場合,以下のような情報を取得できます：

```bash
# 現在の状態確認
$ curl http://localhost:8000/api/now
{
  "status": "AWAY",
  "timestamp": "2025-07-13T00:36:37.139329",
  "temperature": 25.5,
  "humidity": 60.2,
  "illuminance": 350.0,
  "confidence": "completed"
}

```

