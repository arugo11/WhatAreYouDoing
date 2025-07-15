"""
Demo Mode for WhatAreYouDoing - Server-side Auto Data Collection

本番環境と全く同じように振る舞うデモモード
ESP32の代わりに自動的にWebカメラとモックセンサーからデータを収集
"""

import asyncio
import json
import logging
import random
import tempfile
from datetime import datetime
from typing import Optional
from io import BytesIO
import aiohttp
import aiofiles
from sqlalchemy.orm import Session

from database import get_db, EventCRUD
from ai_analyzer import analyzer
from models import ActionCategory, AIProcessStatus

logger = logging.getLogger(__name__)


class MockSensorDataGenerator:
    """モックセンサーデータ生成クラス（時間帯連動）"""
    
    def __init__(self):
        """初期化"""
        self.base_temp = 23.0
        self.base_humidity = 55.0
        
    def _get_time_factor(self) -> float:
        """時間帯に基づく調整ファクターを取得"""
        current_hour = datetime.now().hour
        
        if 6 <= current_hour <= 18:
            return 1.2  # 昼間は暖かく明るい
        elif 18 < current_hour <= 22:
            return 1.0  # 夕方は標準
        else:
            return 0.7  # 深夜は涼しく暗い
    
    def generate_temperature(self) -> float:
        """温度データを生成 (°C)"""
        time_factor = self._get_time_factor()
        temp = self.base_temp * time_factor + random.uniform(-3.0, 3.0)
        return round(temp, 1)
    
    def generate_humidity(self) -> float:
        """湿度データを生成 (%)"""
        humidity = self.base_humidity + random.uniform(-15.0, 15.0)
        return round(max(30.0, min(80.0, humidity)), 1)
    
    def generate_illuminance(self) -> float:
        """照度データを生成 (lux)"""
        current_hour = datetime.now().hour
        
        # 時間帯に応じた照度設定
        if 6 <= current_hour <= 8:
            base_lux = 200.0  # 朝：中程度
        elif 8 < current_hour <= 18:
            base_lux = 400.0  # 昼間：明るい
        elif 18 < current_hour <= 22:
            base_lux = 150.0  # 夕方：室内照明
        else:
            base_lux = 50.0   # 深夜：暗い
        
        illuminance = base_lux + random.uniform(-50.0, 100.0)
        return round(max(10.0, illuminance), 1)
    
    def generate_sensor_data(self) -> dict:
        """すべてのセンサーデータを生成"""
        return {
            "temperature": self.generate_temperature(),
            "humidity": self.generate_humidity(),
            "illuminance": self.generate_illuminance()
        }


class DemoDataCollector:
    """デモ用データ収集クラス"""
    
    def __init__(self, camera_url: str, capture_interval: int = 30):
        """
        初期化
        
        Args:
            camera_url: Webカメラストリームのurl
            capture_interval: キャプチャ間隔（秒）
        """
        self.camera_url = camera_url
        self.capture_interval = capture_interval
        self.sensor_generator = MockSensorDataGenerator()
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        
    async def start(self):
        """デモデータ収集を開始"""
        if self.running:
            logger.warning("Demo data collector is already running")
            return
            
        self.running = True
        self.session = aiohttp.ClientSession()
        
        logger.info(f"Starting demo data collection (interval: {self.capture_interval}s)")
        logger.info(f"Camera URL: {self.camera_url}")
        
        # バックグラウンドタスクを開始
        asyncio.create_task(self._collection_loop())
    
    async def stop(self):
        """デモデータ収集を停止"""
        self.running = False
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("Demo data collection stopped")
    
    async def _capture_image_from_stream(self) -> Optional[str]:
        """
        MJPEGストリームから単一フレームを取得して一時ファイルに保存
        
        Returns:
            保存された画像ファイルのパス（エラー時はNone）
        """
        try:
            if not self.session:
                logger.error("Session not initialized")
                return None
                
            logger.debug(f"Capturing frame from MJPEG stream: {self.camera_url}")
            
            # タイムアウトを設定してMJPEGストリームから単一フレームを取得
            timeout = aiohttp.ClientTimeout(total=10)
            async with self.session.get(self.camera_url, timeout=timeout) as response:
                if response.status == 200:
                    logger.debug("Stream connected, extracting single frame...")
                    
                    # MJPEGストリームからフレームを抽出
                    boundary = b'--frame'
                    content_type_header = b'Content-Type: image/jpeg'
                    jpeg_header = b'\xff\xd8'  # JPEG開始マーカー
                    jpeg_footer = b'\xff\xd9'  # JPEG終了マーカー
                    
                    buffer = b''
                    jpeg_started = False
                    jpeg_data = b''
                    
                    async for chunk in response.content.iter_chunked(1024):
                        buffer += chunk
                        
                        # JPEGデータの開始を探す
                        if not jpeg_started and jpeg_header in buffer:
                            start_pos = buffer.find(jpeg_header)
                            jpeg_data = buffer[start_pos:]
                            jpeg_started = True
                            logger.debug("JPEG frame start detected")
                        elif jpeg_started:
                            jpeg_data += chunk
                            
                            # JPEGデータの終了を探す
                            if jpeg_footer in jpeg_data:
                                end_pos = jpeg_data.find(jpeg_footer) + 2
                                jpeg_data = jpeg_data[:end_pos]
                                logger.debug(f"JPEG frame extracted: {len(jpeg_data)} bytes")
                                break
                        
                        # 安全制限：データが大きすぎる場合は停止
                        if len(jpeg_data) > 1024 * 1024:  # 1MB制限
                            logger.warning("Frame too large, stopping capture")
                            break
                    
                    if jpeg_started and len(jpeg_data) > 1000:  # 最低1KB以上
                        # 一時ファイルに保存
                        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                        import random
                        temp_file = f"/tmp/demo_capture_{timestamp}_{random.randint(100,999)}.jpg"
                        
                        async with aiofiles.open(temp_file, "wb") as f:
                            await f.write(jpeg_data)
                        
                        logger.info(f"Frame captured successfully: {temp_file} ({len(jpeg_data)} bytes)")
                        return temp_file
                    else:
                        logger.error("Failed to extract valid JPEG frame from stream")
                        return None
                else:
                    logger.error(f"Failed to connect to camera stream: HTTP {response.status}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error("Timeout while capturing image from stream")
            return None
        except Exception as e:
            logger.error(f"Error capturing image from stream: {e}")
            return None
    
    async def _process_captured_data(self, image_path: str, sensor_data: dict):
        """
        キャプチャしたデータを処理（本番と同じフロー）
        
        Args:
            image_path: 画像ファイルパス
            sensor_data: センサーデータ
        """
        try:
            # データベースセッションを取得
            db = next(get_db())
            
            try:
                # データベースにイベントを作成
                event = EventCRUD.create_event(
                    db,
                    image_path=image_path,
                    temperature=sensor_data["temperature"],
                    humidity=sensor_data["humidity"],
                    illuminance=sensor_data["illuminance"]
                )
                
                logger.info(f"Event created in demo mode: ID {event.id}")
                logger.debug(f"Sensor data: {sensor_data}")
                
                # AI分析をバックグラウンドで実行（本番と同じ）
                asyncio.create_task(self._process_ai_analysis(
                    event.id,
                    image_path,
                    sensor_data["temperature"],
                    sensor_data["humidity"],
                    sensor_data["illuminance"]
                ))
                
            except Exception as e:
                logger.error(f"Failed to create event in demo mode: {e}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing captured data: {e}")
    
    async def _process_ai_analysis(
        self,
        event_id: int,
        image_path: str,
        temperature: float,
        humidity: float,
        illuminance: float
    ):
        """
        AI分析をバックグラウンドで実行（本番と同じロジック）
        
        Args:
            event_id: イベントID
            image_path: 画像パス
            temperature: 温度
            humidity: 湿度
            illuminance: 照度
        """
        try:
            logger.info(f"Starting AI analysis for demo event {event_id}")
            
            # データベースセッションを取得
            db = next(get_db())
            
            try:
                # イベントのステータスを「処理中」に変更
                EventCRUD.update_event_status(db, event_id, ActionCategory.OTHER, AIProcessStatus.PROCESSING)
                
                # AI分析を実行
                result = analyzer.analyze_image(image_path, temperature, humidity, illuminance)
                
                if result["process_status"] == AIProcessStatus.COMPLETED:
                    # 分析完了：結果をDBに保存
                    EventCRUD.update_event_status(
                        db, event_id, result["status"], AIProcessStatus.COMPLETED
                    )
                    logger.info(f"Demo AI analysis completed for event {event_id}: {result['status']}")
                else:
                    # 分析エラー：エラー状態に設定
                    EventCRUD.set_event_error(db, event_id, result.get("error", "Unknown error"))
                    logger.error(f"Demo AI analysis failed for event {event_id}: {result.get('error')}")
                    
            except Exception as e:
                logger.error(f"Error in demo AI analysis for event {event_id}: {e}")
                EventCRUD.set_event_error(db, event_id, str(e))
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Critical error in demo AI analysis task: {e}")
    
    async def _collection_loop(self):
        """メインの収集ループ"""
        logger.info("Demo collection loop started")
        
        while self.running:
            try:
                # Webカメラから画像を取得
                image_path = await self._capture_image_from_stream()
                if image_path is None:
                    logger.warning("Failed to capture image in demo mode, retrying in 5s")
                    await asyncio.sleep(5)
                    continue
                
                # モックセンサーデータを生成
                sensor_data = self.sensor_generator.generate_sensor_data()
                
                # データを処理（本番と同じフロー）
                await self._process_captured_data(image_path, sensor_data)
                
                logger.info(f"Demo cycle completed. Next capture in {self.capture_interval}s")
                
                # 次のキャプチャまで待機
                await asyncio.sleep(self.capture_interval)
                
            except asyncio.CancelledError:
                logger.info("Demo collection loop cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in demo collection loop: {e}")
                await asyncio.sleep(10)  # エラー時は少し長めに待機
        
        logger.info("Demo collection loop ended")


# グローバルなデモコレクターインスタンス
_demo_collector: Optional[DemoDataCollector] = None


async def start_demo_mode(camera_url: str, capture_interval: int = 30):
    """
    デモモードを開始
    
    Args:
        camera_url: Webカメラストリームのurl
        capture_interval: キャプチャ間隔（秒）
    """
    global _demo_collector
    
    if _demo_collector and _demo_collector.running:
        logger.warning("Demo mode is already running")
        return
    
    _demo_collector = DemoDataCollector(camera_url, capture_interval)
    await _demo_collector.start()


async def stop_demo_mode():
    """デモモードを停止"""
    global _demo_collector
    
    if _demo_collector:
        await _demo_collector.stop()
        _demo_collector = None


def is_demo_mode_running() -> bool:
    """デモモードが実行中かどうかを確認"""
    global _demo_collector
    return _demo_collector is not None and _demo_collector.running


def get_demo_status() -> dict:
    """デモモードの状態を取得"""
    global _demo_collector
    
    if not _demo_collector:
        return {
            "demo_mode": False,
            "status": "stopped"
        }
    
    return {
        "demo_mode": True,
        "status": "running" if _demo_collector.running else "stopped",
        "camera_url": _demo_collector.camera_url,
        "capture_interval": _demo_collector.capture_interval
    } 