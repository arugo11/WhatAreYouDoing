# デモモード - 3分クイックスタート

顧客向けデモンストレーション用。ESP32なしで本番と全く同じように動作します。

## 3ステップ起動

### 1. 環境設定
```bash
cd server
cp env.example .env
```

`.env`ファイルで以下を設定：
```bash
GEMINI_API_KEY=your_actual_gemini_api_key
DEMO_MODE=true
```

### 2. サーバー起動
```bash
uv sync
uv run python main.py
```

**成功ログ例：**
```
Demo mode enabled - starting auto data collection
Camera URL: http://192.168.3.3:5000/video_feed
Demo collection loop started
```

### 3. API確認
```bash
# ヘルスチェック（デモモード情報含む）
curl http://localhost:8000/api/health

# リアルタイム分析結果
curl http://localhost:8000/api/now
```

## デモの特徴

- **完全自動化**: 30秒間隔で自動画像取得・AI分析
- **本番同等**: ESP32と全く同じAPIレスポンス
- **リアルタイム**: モックセンサーデータで時間帯連動
- **顧客体験**: 通常のAPIエンドポイントをそのまま使用

## トラブルシューティング

| 問題 | 解決方法 |
|------|----------|
| `Production mode` | `.env`で`DEMO_MODE=true`を確認 |
| カメラエラー | `http://192.168.3.3:5000/`がアクセス可能か確認 |
| AI分析エラー | `GEMINI_API_KEY`が正しく設定されているか確認 |

## 期待される結果

正常動作時のAPIレスポンス例：
```json
{
  "status": "PC_WORK",
  "timestamp": "2025-01-15T16:30:10",
  "temperature": 24.5,
  "humidity": 58.2,
  "illuminance": 380.0,
  "confidence": "completed"
}
```

詳細は `DEMO_MODE.md` を参照してください。 