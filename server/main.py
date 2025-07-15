"""
FastAPI server for WhatAreYouDoing project
"""

import os
import logging
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import aiofiles
import json
from dotenv import load_dotenv

from database import get_db, init_db, EventCRUD, IMAGES_DIR
from models import SensorData, EventResponse, StatusResponse, EventDetail, ActionCategory, AIProcessStatus
from ai_analyzer import analyzer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Application started successfully")
        logger.info("Production mode - waiting for ESP32 data")
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise
    
    yield
    
    try:
        logger.info("Application shutdown completed")
    except Exception as e:
        logger.error(f"Error during application shutdown: {e}")


app = FastAPI(
    title="WhatAreYouDoing API",
    description="行動判定特化システムのAPIサーバー",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


async def process_ai_analysis(
    event_id: int,
    image_path: str,
    temperature: float,
    humidity: float,
    illuminance: float
):
    try:
        logger.info(f"Starting AI analysis for event {event_id}")
        
        db = next(get_db())
        
        try:
            EventCRUD.update_event_status(db, event_id, ActionCategory.OTHER, AIProcessStatus.PROCESSING)
            
            result = analyzer.analyze_image(image_path, temperature, humidity, illuminance)
            
            if result["process_status"] == AIProcessStatus.COMPLETED:
                EventCRUD.update_event_status(
                    db, event_id, result["status"], AIProcessStatus.COMPLETED
                )
                logger.info(f"AI analysis completed for event {event_id}: {result['status']}")
            else:
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
    try:
        try:
            sensor_data = json.loads(metadata)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON metadata: {metadata}")
            raise HTTPException(status_code=400, detail="Invalid metadata format")
        
        try:
            validated_data = SensorData(**sensor_data)
        except Exception as e:
            logger.error(f"Invalid sensor data: {e}")
            raise HTTPException(status_code=400, detail="Invalid sensor data")
        
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Invalid image format")
        
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
            if os.path.exists(image_path):
                os.remove(image_path)
            raise HTTPException(status_code=500, detail="Failed to create event")
        
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
    try:
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
    
    HOST = os.getenv("SERVER_HOST", "0.0.0.0")
    PORT = int(os.getenv("SERVER_PORT", "8000"))
    
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT) 