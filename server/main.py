"""
FastAPI server for WhatAreYouDoing project
"""

import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import aiofiles
import json
from dotenv import load_dotenv

from database import get_db, init_db, EventCRUD, IMAGES_DIR
from models import SensorData, EventResponse, StatusResponse, EventDetail, ActionCategory, AIProcessStatus
from ai_analyzer import analyzer

# 環境変数の読み込み
load_dotenv()

# ログの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPIアプリケーションの初期化
app = FastAPI(
    title="WhatAreYouDoing API",
    description="行動判定特化システムのAPIサーバー",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# データベースの初期化
@app.on_event("startup")
async def startup_event():
    """アプリケーション起動時の処理"""
    try:
        init_db()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def process_ai_analysis(
    event_id: int,
    image_path: str,
    temperature: float,
    humidity: float,
    illuminance: float
):
    """
    AI分析をバックグラウンドで実行
    
    Args:
        event_id: イベントID
        image_path: 画像パス
        temperature: 温度
        humidity: 湿度
        illuminance: 照度
    """
    try:
        logger.info(f"Starting AI analysis for event {event_id}")
        
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
                logger.info(f"AI analysis completed for event {event_id}: {result['status']}")
            else:
                # 分析エラー：エラー状態に設定
                EventCRUD.set_event_error(db, event_id, result.get("error", "Unknown error"))
                logger.error(f"AI analysis failed for event {event_id}: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error in AI analysis for event {event_id}: {e}")
            EventCRUD.set_event_error(db, event_id, str(e))
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Critical error in AI analysis task: {e}")


@app.post("/api/events", response_model=EventResponse)
async def create_event(
    background_tasks: BackgroundTasks,
    metadata: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    ESP32からのイベントデータを受信
    
    Args:
        background_tasks: バックグラウンドタスク
        metadata: センサーデータ（JSON形式）
        image: アップロード画像
        db: データベースセッション
        
    Returns:
        イベント作成レスポンス
    """
    try:
        # メタデータをJSONとして解析
        try:
            sensor_data = json.loads(metadata)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON metadata: {metadata}")
            raise HTTPException(status_code=400, detail="Invalid metadata format")
        
        # センサーデータの検証
        try:
            validated_data = SensorData(**sensor_data)
        except Exception as e:
            logger.error(f"Invalid sensor data: {e}")
            raise HTTPException(status_code=400, detail="Invalid sensor data")
        
        # 画像ファイルの検証
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        # 画像を保存
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        image_filename = f"{timestamp}.jpg"
        image_path = os.path.join(IMAGES_DIR, image_filename)
        
        try:
            async with aiofiles.open(image_path, "wb") as buffer:
                content = await image.read()
                await buffer.write(content)
            logger.info(f"Image saved: {image_path}")
        except Exception as e:
            logger.error(f"Failed to save image: {e}")
            raise HTTPException(status_code=500, detail="Failed to save image")
        
        # データベースにイベントを保存
        try:
            event = EventCRUD.create_event(
                db,
                image_path=image_path,
                temperature=validated_data.temperature,
                humidity=validated_data.humidity,
                illuminance=validated_data.illuminance
            )
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            # 保存された画像を削除
            if os.path.exists(image_path):
                os.remove(image_path)
            raise HTTPException(status_code=500, detail="Failed to create event")
        
        # バックグラウンドでAI分析を開始
        background_tasks.add_task(
            process_ai_analysis,
            event.id,
            image_path,
            validated_data.temperature,
            validated_data.humidity,
            validated_data.illuminance
        )
        
        logger.info(f"Event created successfully: {event.id}")
        
        return EventResponse(
            message="Event received and processing started",
            event_id=event.id,
            timestamp=event.timestamp
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/now", response_model=StatusResponse)
async def get_current_status(db: Session = Depends(get_db)):
    """
    最新の分類済み行動ステータスを取得
    
    Args:
        db: データベースセッション
        
    Returns:
        最新のステータス情報
    """
    try:
        event = EventCRUD.get_latest_completed_event(db)
        
        if not event:
            return StatusResponse(
                status=None,
                timestamp=datetime.utcnow(),
                confidence="No data available"
            )
        
        return StatusResponse(
            status=event.status_category,
            timestamp=event.timestamp,
            temperature=event.temperature,
            humidity=event.humidity,
            illuminance=event.illuminance,
            confidence=event.ai_process_status
        )
        
    except Exception as e:
        logger.error(f"Error getting current status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/events/by-time/{year}/{month}/{day}/{hour}/{minute}", response_model=StatusResponse)
async def get_status_by_time(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    db: Session = Depends(get_db)
):
    """
    指定した日時に最も近い時間の行動ステータスを取得
    
    Args:
        year: 年
        month: 月
        day: 日
        hour: 時
        minute: 分
        db: データベースセッション
        
    Returns:
        指定時刻に最も近いステータス情報
    """
    try:
        # 日時の妥当性チェック
        try:
            target_time = datetime(year, month, day, hour, minute)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date/time")
        
        event = EventCRUD.get_event_by_time(db, year, month, day, hour, minute)
        
        if not event:
            return StatusResponse(
                status=None,
                timestamp=target_time,
                confidence="No data available for specified time"
            )
        
        return StatusResponse(
            status=event.status_category,
            timestamp=event.timestamp,
            temperature=event.temperature,
            humidity=event.humidity,
            illuminance=event.illuminance,
            confidence=event.ai_process_status
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status by time: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/health")
async def health_check():
    """
    ヘルスチェック用エンドポイント
    
    Returns:
        サーバーの状態情報
    """
    try:
        model_info = analyzer.get_model_info()
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "ai_model": model_info["model_name"],
            "api_configured": model_info["api_key_configured"],
            "supported_categories": model_info["supported_categories"]
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@app.get("/api/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """
    統計情報を取得
    
    Args:
        db: データベースセッション
        
    Returns:
        統計情報
    """
    try:
        pending_events = EventCRUD.get_pending_events(db)
        latest_event = EventCRUD.get_latest_completed_event(db)
        
        return {
            "pending_events": len(pending_events),
            "latest_event_time": latest_event.timestamp.isoformat() if latest_event else None,
            "latest_status": latest_event.status_category if latest_event else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    
    # 環境変数から設定を取得
    HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    PORT = int(os.getenv("SERVER_PORT", "8000"))
    
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT) 