"""
AI Analysis Module for WhatAreYouDoing
Uses Google Gemini API to classify user actions
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import google.generativeai as genai
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

from models import ActionCategory, AIProcessStatus

# Load environment variables from .env file
load_dotenv()

# ログの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini APIの設定
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable is not set")
    raise ValueError("GEMINI_API_KEY environment variable is required")

genai.configure(api_key=GEMINI_API_KEY)


class AIAnalyzer:
    """AI分析クラス"""
    
    def __init__(self, model_name: str = "gemini-1.5-flash-latest"):
        """
        初期化
        
        Args:
            model_name: 使用するGeminiモデル名
        """
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)
        logger.info(f"AI Analyzer initialized with model: {model_name}")
    
    def _generate_prompt(self, temperature: float, humidity: float, illuminance: float) -> str:
        """
        プロンプトを生成
        
        Args:
            temperature: 温度
            humidity: 湿度
            illuminance: 照度
            
        Returns:
            分析用プロンプト
        """
        prompt = f"""あなたは私の部屋の状況を分析し、行動を分類する専門家です。提供された画像とセンサーデータに基づき、私の現在の状態を6つの定義済みカテゴリーの中から最も確からしいもの1つに分類してください。

# カテゴリー定義
- PC_WORK: デスクのPCに向かって作業している。
- GAMING: デスクのPCに向かってゲームをしている。
- SLEEPING: ベッドで寝ている。
- USING_SMARTPHONE: ベッドや椅子でスマートフォンを操作している。
- AWAY: 部屋に誰もいない。
- OTHER: 上記のいずれにも当てはまらない、または判断が困難な場合。

# 行動分類のための重要ルール
これは私の私室です。以下のルールに従って、より正確な判断を行ってください。

1. **最優先判断：不在(AWAY)かどうか**
   - 画像に人物が明確に映っていない場合、状態は「AWAY」です。他のルールは無視してください。

2. **PC作業(PC_WORK)とゲーム(GAMING)の判断**
   - 私がデスクの椅子に座っている場合、**エアコンの上**を確認してください。
   - **エアコンの上にゲームコントローラーがはっきりと見える場合**、私の状態は「**PC_WORK**」です。
   - **エアコンの上にゲームコントローラーが見えない場合**、私の状態は「**GAMING**」です。

3. **睡眠(SLEEPING)の判断**
   - 私がベッドの中に横になっている場合、状態は「SLEEPING」です。
   - 特に部屋が暗い（照度データが低い）場合は、この可能性が極めて高いです。

4. **スマホ操作(USING_SMARTPHONE)の判断**
   - 私がベッドの上で、横にならずに体を起こしている場合、状態は「USING_SMARTPHONE」です。
   - PCの前に座っていない場合もこの可能性を考慮してください。

# 提供データ
- センサー情報:
  - 温度: {temperature} °C
  - 湿度: {humidity} %
  - 照度: {illuminance} lux

# 出力形式
あなたの回答は、必ず以下のJSON形式のみで出力してください。他の説明文は一切含めないでください。
{{"status": "ここに判断したカテゴリー名"}}"""
        
        return prompt
    
    def _load_image(self, image_path: str) -> Optional[Image.Image]:
        """
        画像ファイルを読み込む
        
        Args:
            image_path: 画像ファイルパス
            
        Returns:
            PIL Image オブジェクト
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return None
            
            image = Image.open(image_path)
            # 画像サイズを適切に調整（メモリ使用量を抑制）
            if image.width > 1024 or image.height > 1024:
                image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            return image
        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        reraise=True
    )
    def _call_gemini_api(self, prompt: str, image: Image.Image) -> Dict[str, Any]:
        """
        Gemini APIを呼び出す（リトライ機能付き）
        
        Args:
            prompt: 分析用プロンプト
            image: 分析対象の画像
            
        Returns:
            API応答の辞書
        """
        try:
            # 画像をバイト配列に変換
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Gemini APIに送信
            response = self.model.generate_content(
                [prompt, {"mime_type": "image/jpeg", "data": img_byte_arr}],
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            
            # レスポンスをJSONとして解析
            response_text = response.text.strip()
            logger.debug(f"Gemini API response: {response_text}")
            
            return json.loads(response_text)
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response_text}")
            raise
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
    
    def analyze_image(
        self,
        image_path: str,
        temperature: float,
        humidity: float,
        illuminance: float
    ) -> Dict[str, Any]:
        """
        画像とセンサーデータを分析して行動を分類
        
        Args:
            image_path: 分析対象の画像パス
            temperature: 温度
            humidity: 湿度
            illuminance: 照度
            
        Returns:
            分析結果の辞書
        """
        try:
            # 画像を読み込み
            image = self._load_image(image_path)
            if not image:
                return {
                    "status": ActionCategory.OTHER,
                    "error": "Failed to load image",
                    "process_status": AIProcessStatus.ERROR
                }
            
            # プロンプトを生成
            prompt = self._generate_prompt(temperature, humidity, illuminance)
            
            # Gemini APIを呼び出し
            logger.info(f"Analyzing image: {image_path}")
            api_response = self._call_gemini_api(prompt, image)
            
            # 応答を検証
            detected_status = api_response.get("status", ActionCategory.OTHER)
            if detected_status not in ActionCategory.get_all_categories():
                logger.warning(f"Unknown status category: {detected_status}, defaulting to OTHER")
                detected_status = ActionCategory.OTHER
            
            logger.info(f"Analysis completed: {detected_status}")
            
            return {
                "status": detected_status,
                "process_status": AIProcessStatus.COMPLETED,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "sensor_data": {
                    "temperature": temperature,
                    "humidity": humidity,
                    "illuminance": illuminance
                }
            }
            
        except Exception as e:
            logger.error(f"Analysis failed for {image_path}: {e}")
            return {
                "status": ActionCategory.OTHER,
                "error": str(e),
                "process_status": AIProcessStatus.ERROR
            }
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        モデル情報を取得
        
        Returns:
            モデル情報の辞書
        """
        return {
            "model_name": self.model_name,
            "api_key_configured": bool(GEMINI_API_KEY),
            "supported_categories": ActionCategory.get_all_categories()
        }


# グローバルインスタンス
analyzer = AIAnalyzer() 