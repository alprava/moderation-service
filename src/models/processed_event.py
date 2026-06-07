import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON
from src.database import Base


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    sender_service = Column(String(50), nullable=False)  # "b2b"
    idempotency_key = Column(String(36), nullable=False, index=True)
    product_id = Column(String(32), nullable=False)
    event_type = Column(String(20), nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    response_cached = Column(JSON, nullable=True)
