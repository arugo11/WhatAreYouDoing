"""
Database models and CRUD operations
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
import logging

# 環境変数から設定を取得
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/whatareyoudoing.db")
DATA_DIR = os.getenv("DATA_DIR", "./data")
IMAGES_DIR = os.getenv("IMAGES_DIR", "./data/images")

# データディレクトリの作成
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# データベースエンジンの設定
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ログの設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Event(Base):
    """イベントテーブル"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    image_path = Column(String, nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    illuminance = Column(Float, nullable=True)
    status_category = Column(String, nullable=True)
    ai_process_status = Column(String, default="pending", nullable=False)


def get_db():
    """データベースセッションの取得"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """データベースの初期化"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


class EventCRUD:
    """イベントのCRUD操作"""
    
    @staticmethod
    def create_event(
        db: Session,
        image_path: Optional[str] = None,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        illuminance: Optional[float] = None
    ) -> Event:
        """新しいイベントを作成"""
        try:
            event = Event(
                image_path=image_path,
                temperature=temperature,
                humidity=humidity,
                illuminance=illuminance,
                ai_process_status="pending"
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            logger.info(f"Created event with ID: {event.id}")
            return event
        except Exception as e:
            logger.error(f"Error creating event: {e}")
            db.rollback()
            raise

    @staticmethod
    def update_event_status(
        db: Session,
        event_id: int,
        status_category: str,
        ai_process_status: str = "completed"
    ) -> Optional[Event]:
        """イベントのステータスを更新"""
        try:
            event = db.query(Event).filter(Event.id == event_id).first()
            if event:
                event.status_category = status_category
                event.ai_process_status = ai_process_status
                db.commit()
                db.refresh(event)
                logger.info(f"Updated event {event_id} status to {status_category}")
                return event
            else:
                logger.warning(f"Event with ID {event_id} not found")
                return None
        except Exception as e:
            logger.error(f"Error updating event status: {e}")
            db.rollback()
            raise

    @staticmethod
    def get_latest_completed_event(db: Session) -> Optional[Event]:
        """最新の完了したイベントを取得"""
        try:
            event = db.query(Event).filter(
                Event.ai_process_status == "completed"
            ).order_by(Event.timestamp.desc()).first()
            return event
        except Exception as e:
            logger.error(f"Error getting latest completed event: {e}")
            return None

    @staticmethod
    def get_event_by_time(
        db: Session,
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int
    ) -> Optional[Event]:
        """指定した時間に最も近いイベントを取得"""
        try:
            target_time = datetime(year, month, day, hour, minute)
            
            # 指定時刻に最も近いイベントを取得
            event = db.query(Event).filter(
                Event.ai_process_status == "completed"
            ).order_by(
                func.abs(func.julianday(Event.timestamp) - func.julianday(target_time))
            ).first()
            
            return event
        except Exception as e:
            logger.error(f"Error getting event by time: {e}")
            return None

    @staticmethod
    def get_pending_events(db: Session, limit: int = 10) -> List[Event]:
        """未処理のイベントを取得"""
        try:
            events = db.query(Event).filter(
                Event.ai_process_status == "pending"
            ).order_by(Event.timestamp.asc()).limit(limit).all()
            return events
        except Exception as e:
            logger.error(f"Error getting pending events: {e}")
            return []

    @staticmethod
    def delete_old_events(db: Session, days_to_keep: int = 90) -> int:
        """古いイベントを削除"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            deleted_count = db.query(Event).filter(
                Event.timestamp < cutoff_date
            ).delete()
            db.commit()
            logger.info(f"Deleted {deleted_count} old events")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting old events: {e}")
            db.rollback()
            raise

    @staticmethod
    def set_event_error(db: Session, event_id: int, error_message: str = "AI processing error") -> Optional[Event]:
        """イベントをエラー状態に設定"""
        try:
            event = db.query(Event).filter(Event.id == event_id).first()
            if event:
                event.ai_process_status = "error"
                db.commit()
                db.refresh(event)
                logger.warning(f"Set event {event_id} to error state: {error_message}")
                return event
            return None
        except Exception as e:
            logger.error(f"Error setting event error: {e}")
            db.rollback()
            raise 