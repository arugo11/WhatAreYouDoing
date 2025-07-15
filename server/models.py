"""
モデル群
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SensorData(BaseModel):
    temperature: float = Field(..., description="温度 (°C)")
    humidity: float = Field(..., description="湿度 (%)")
    illuminance: float = Field(..., description="照度 (lux)")


class EventResponse(BaseModel):
    message: str
    event_id: int
    timestamp: datetime


class StatusResponse(BaseModel):
    status: Optional[str] = Field(None, description="行動カテゴリー")
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    illuminance: Optional[float] = None
    confidence: Optional[str] = Field(None, description="AI処理状況")


class EventDetail(BaseModel):
    id: int
    timestamp: datetime
    status_category: Optional[str] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    illuminance: Optional[float] = None
    ai_process_status: Optional[str] = None
    image_path: Optional[str] = None


class ActionCategory:
    PC_WORK = "PC_WORK"
    GAMING = "GAMING"
    SLEEPING = "SLEEPING"
    AWAKE_IN_BED = "AWAKE_IN_BED"
    AWAY = "AWAY"
    OTHER = "OTHER"

    @classmethod
    def get_all_categories(cls) -> list[str]:
        return [cls.PC_WORK, cls.GAMING, cls.SLEEPING, cls.AWAKE_IN_BED, cls.AWAY, cls.OTHER]


class AIProcessStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error" 