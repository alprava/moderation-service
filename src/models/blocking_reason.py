import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Text
from src.database import Base


class BlockingReason(Base):
    __tablename__ = "blocking_reasons"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    title = Column(String(255), nullable=False)
    comment = Column(Text, nullable=True)
    hard_only = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
