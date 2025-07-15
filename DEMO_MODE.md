# デモモード - WhatAreYouDoing?

顧客向けデモンストレーション用の完全自動化モード。ESP32デバイスを使用せずに、本番環境と全く同じように振る舞います。

## デモモードの概要

デモモードでは、サーバーが自動的に以下を実行します：

- **自動画像取得**: Webカメラストリーム（`http://192.168.3.3:5000/video_feed`）から定期的に画像を取得
- **モックセンサーデータ**: 時間帯に連動したリアルな温度・湿度・照度データを生成
- **完全な処理フロー**: 本番と同じデータベース保存、AI分析、API応答

**顧客は通常のAPIエンドポイントを使用**するだけで、ESP32との違いを感じることなく全機能を体験できます。

## デモモードの有効化

### 1. 環境設定

```bash
cd server
cp env.example .env
```

`.env`ファイルを以下のように編集：

```bash
# Gemini API Settings
GEMINI_API_KEY=your_actual_api_key_here

# Demo Mode Settings (重要！)
DEMO_MODE=true
DEMO_CAMERA_URL=http://192.168.3.3:5000/video_feed
DEMO_CAPTURE_INTERVAL=30

# その他の設定はデフォルトのまま
DATABASE_URL=sqlite:///./data/whatareyoudoing.db
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

### 2. 依存関係のインストール

```bash
cd server
uv sync
```

### 3. サーバー起動

```bash
uv run python main.py
```

## デモモードでの動作確認

### 起動ログ例

```
2025-01-15 16:30:00,123 - __main__ - INFO - Application started successfully
2025-01-15 16:30:00,124 - __main__ - INFO - Demo mode enabled - starting auto data collection
2025-01-15 16:30:00,125 - demo_mode - INFO - Starting demo data collection (interval: 30s)
2025-01-15 16:30:00,126 - demo_mode - INFO - Camera URL: http://192.168.3.3:5000/video_feed
2025-01-15 16:30:00,127 - demo_mode - INFO - Demo collection loop started
2025-01-15 16:30:01,200 - demo_mode - INFO - Event created in demo mode: ID 1
2025-01-15 16:30:02,800 - demo_mode - INFO - Starting AI analysis for demo event 1
2025-01-15 16:30:05,600 - demo_mode - INFO - Demo AI analysis completed for event 1: PC_WORK
2025-01-15 16:30:05,601 - demo_mode - INFO - Demo cycle completed. Next capture in 30s
```

### API動作確認

```bash
# ヘルスチェック（デモモード情報を含む）
curl http://localhost:8000/api/health

# 最新の分析結果
curl http://localhost:8000/api/now

# 統計情報
curl http://localhost:8000/api/stats
```

**ヘルスチェックのレスポンス例：**

```json
{
  "status": "healthy",
  "timestamp": "2025-01-15T16:30:10.123456",
  "ai_model": "gemini-1.5-flash-latest",
  "api_configured": true,
  "supported_categories": ["PC_WORK", "GAMING", "SLEEPING", "USING_SMARTPHONE", "AWAY", "OTHER"],
  "demo_mode": {
    "demo_mode": true,
    "status": "running",
    "camera_url": "http://192.168.3.3:5000/video_feed",
    "capture_interval": 30
  }
}
```

## デモモード設定

| 環境変数 | デフォルト値 | 説明 |
|----------|-------------|------|
| `DEMO_MODE` | `false` | デモモードの有効/無効 |
| `DEMO_CAMERA_URL` | `http://192.168.3.3:5000/video_feed` | Webカメラストリームのurl |
| `DEMO_CAPTURE_INTERVAL` | `30` | 画像キャプチャ間隔（秒） |

### 設定例

```bash
# 高頻度デモ（15秒間隔）
DEMO_CAPTURE_INTERVAL=15

# 異なるカメラURL
DEMO_CAMERA_URL=http://192.168.1.100:8080/video_feed

# 低頻度デモ（60秒間隔）
DEMO_CAPTURE_INTERVAL=60
```

## モックセンサーデータの仕様

### 温度データ
- **基準値**: 23.0°C
- **時間帯変動**: 昼間（6-18時）は+20%、深夜（22-6時）は-30%
- **ランダム変動**: ±3.0°C

### 湿度データ
- **基準値**: 55.0%
- **変動範囲**: 30-80%
- **ランダム変動**: ±15%

### 照度データ
- **朝（6-8時）**: 200 lux ± 50
- **昼間（8-18時）**: 400 lux ± 100
- **夕方（18-22時）**: 150 lux ± 50
- **深夜（22-6時）**: 50 lux ± 30

## 🎭 顧客向けデモンストレーション

### デモシナリオ

1. **サーバー起動デモ**:
   ```bash
   uv run python main.py
   ```
   → ログでデモモード有効を確認

2. **リアルタイム分析デモ**:
   ```bash
   # 30秒ごとに結果を確認
   watch -n 5 "curl -s http://localhost:8000/api/now | jq"
   ```

3. **システム状態デモ**:
   ```bash
   curl http://localhost:8000/api/health | jq
   ```

### デモポイント

- **完全自動化**: 人的介入なしで継続的にデータ収集・分析
- **本番同等性**: 実際のESP32と全く同じAPIとデータフロー
- **リアルタイム性**: 30秒間隔で最新の行動分類結果を提供
- **堅牢性**: エラーハンドリングと自動リトライ機能

## 🔧 トラブルシューティング

### よくある問題

**Q: デモモードが開始されない**
```
Production mode - waiting for ESP32 data
```
→ `.env`ファイルで`DEMO_MODE=true`が設定されているか確認

**Q: カメラ接続エラー**
```
ERROR - Error capturing image: Connection refused
```
→ `http://192.168.3.3:5000/`がブラウザでアクセス可能か確認

**Q: AI分析エラー**
```
Demo AI analysis failed
```
→ `GEMINI_API_KEY`が正しく設定されているか確認

### デバッグ情報

**ログレベルの変更**:
```python
# main.py の先頭で
logging.basicConfig(level=logging.DEBUG)
```

**デモ状態の確認**:
```bash
curl http://localhost:8000/api/health | jq '.demo_mode'
```

## 本番モードへの切り替え

デモ終了後、本番モードに戻すには：

```bash
# .envファイルで
DEMO_MODE=false

# サーバー再起動
uv run python main.py
```

起動ログが以下のように表示されることを確認：
```
Production mode - waiting for ESP32 data
```

## デモチェックリスト

デモ実行前の確認事項：

- [ ] `.env`ファイルで`DEMO_MODE=true`
- [ ] `GEMINI_API_KEY`が設定済み  
- [ ] Webカメラストリーム（`http://192.168.3.3:5000/`）がアクセス可能
- [ ] `uv sync`で依存関係インストール済み
- [ ] サーバー起動ログで「Demo mode enabled」を確認
- [ ] `/api/health`でデモモード情報を確認
- [ ] `/api/now`で分析結果を確認

---

デモモードにより、顧客はESP32デバイスなしでWhatAreYouDoing?システムの完全な機能を体験できます。 