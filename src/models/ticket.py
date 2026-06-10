import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, Text, Integer
from src.database import Base


class TicketStatus:
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    HARD_BLOCKED = "HARD_BLOCKED"


class Ticket(Base):
    __tablename__ = "tickets"
    
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    product_id = Column(String(32), nullable=False, index=True)
    seller_id = Column(String(32), nullable=False)
    
    status = Column(String(20), nullable=False, default=TicketStatus.PENDING)
    
    product_data_before = Column(JSON, nullable=True)
    product_data_after = Column(JSON, nullable=True)
    
    blocking_reason_id = Column(String(32), nullable=True)
    moderator_comment = Column(Text, nullable=True)
    field_reports = Column(JSON, nullable=True)
    hard_block = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(32), nullable=True)
    
    queue_priority = Column(Integer, default=4)
    in_review_expires_at = Column(DateTime, nullable=True)
    
    # kind — обязательно CREATE или EDIT, без default
    kind = Column(String(10), nullable=False)
