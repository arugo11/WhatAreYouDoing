"""
AIからのレスポンス処理
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

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable is not set")
    raise ValueError("GEMINI_API_KEY environment variable is required")

genai.configure(api_key=GEMINI_API_KEY)


class AIAnalyzer:
    """AI分析クラス"""
    
    def __init__(self, model_name: str = "gemini-1.5-flash-latest"):
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)
        logger.info(f"AI Analyzer initialized with model: {model_name}")
    
    def _generate_prompt(
        self,
        temperature: float,
        humidity: float,
        illuminance: float
       ) -> str:

        prompt = f"""あなたは私の部屋の状況を分析し,行動を分類する専門家です.提供された画像とセンサーデータに基づき,私の現在の状態を6つのカテゴリーの中から最も確からしいもの1つに分類してください.

カテゴリー:
- PC_WORK: デスクのPCに向かって作業している
- GAMING: デスクのPCに向かってゲームをしている  
- SLEEPING: ベッドで寝ている
- AWAKE_IN_BED: ベッドに横になっているが起きている状態
- AWAY: 部屋に誰もいない
- OTHER: 上記のいずれにも当てはまらない場合

判断ルール:
1. 人物が映っていない場合は「AWAY」
2. デスクに座っている場合:
   - エアコンの上にゲームコントローラーが見える場合は「PC_WORK」
   - エアコンの上にゲームコントローラーが見えない場合は「GAMING」
3. ベッドにいる場合:
   - 横になっている場合は「SLEEPING」
   - 起きている場合は「AWAKE_IN_BED」

センサー情報:
- 温度: {temperature} °C
- 湿度: {humidity} %
- 照度: {illuminance} lux

以下のJSON形式のみで出力してください:
{{"status": "カテゴリー名"}}"""
        
        return prompt
    
    def _load_image(self, image_path: str) -> Optional[Image.Image]:
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return None
            
            image = Image.open(image_path)
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
        try:
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='JPEG')
            img_byte_arr = img_byte_arr.getvalue()
            
            response = self.model.generate_content(
                [prompt, {"mime_type": "image/jpeg", "data": img_byte_arr}],
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            
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
        try:
            image = self._load_image(image_path)
            if not image:
                return {
                    "status": ActionCategory.OTHER,
                    "error": "Failed to load image",
                    "process_status": AIProcessStatus.ERROR
                }
            
            prompt = self._generate_prompt(temperature, humidity, illuminance)
            
            logger.info(f"Analyzing image: {image_path}")
            api_response = self._call_gemini_api(prompt, image)
            
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
        return {
            "model_name": self.model_name,
            "api_key_configured": bool(GEMINI_API_KEY),
            "supported_categories": ActionCategory.get_all_categories()
        }


analyzer = AIAnalyzer() 