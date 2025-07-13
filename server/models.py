"""
Pydantic models for the WhatAreYouDoing API
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SensorData(BaseModel):
    """センサーデータのモデル"""
    temperature: float = Field(..., description="温度 (°C)")
    humidity: float = Field(..., description="湿度 (%)")
    illuminance: float = Field(..., description="照度 (lux)")


class EventResponse(BaseModel):
    """イベント作成レスポンス"""
    message: str
    event_id: int
    timestamp: datetime


class StatusResponse(BaseModel):
    """ステータスレスポンス"""
    status: Optional[str] = Field(None, description="行動カテゴリー")
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    illuminance: Optional[float] = None
    confidence: Optional[str] = Field(None, description="AI処理状況")


class EventDetail(BaseModel):
    """イベント詳細情報"""
    id: int
    timestamp: datetime
    status_category: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    illuminance: Optional[float] = None
    ai_process_status: Optional[str] = None
    image_path: Optional[str] = None


# 行動カテゴリーの定義
class ActionCategory:
    """行動カテゴリーの定数定義"""
    PC_WORK = "PC_WORK"
    GAMING = "GAMING"
    SLEEPING = "SLEEPING"
    USING_SMARTPHONE = "USING_SMARTPHONE"
    AWAY = "AWAY"
    OTHER = "OTHER"

    @classmethod
    def get_all_categories(cls) -> list[str]:
        """すべてのカテゴリーを取得"""
        return [cls.PC_WORK, cls.GAMING, cls.SLEEPING, cls.USING_SMARTPHONE, cls.AWAY, cls.OTHER]


# AI処理状況の定義
class AIProcessStatus:
    """AI処理状況の定数定義"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error" 