import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, JSON, Text
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
    
    # Данные товара (снапшоты)
    product_data_before = Column(JSON, nullable=True)   # json_before
    product_data_after = Column(JSON, nullable=True)    # json_after
    
    # Результат модерации
    blocking_reason_id = Column(String(32), nullable=True)
    moderator_comment = Column(Text, nullable=True)
    field_reports = Column(JSON, nullable=True)  # [{field_name, sku_id, comment}]
    hard_block = Column(JSON, nullable=True)     # флаг жёсткой блокировки
    
    # Метаданные
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(32), nullable=True)
