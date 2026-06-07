import uuid
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class B2BEventType(str, Enum):
    CREATED = "CREATED"
    EDITED = "EDITED"
    DELETED = "DELETED"


class B2BEventRequest(BaseModel):
    """Событие от B2B-сервиса (US-MOD-01)"""
    idempotency_key: uuid.UUID
    product_id: uuid.UUID
    seller_id: uuid.UUID
    event: B2BEventType
    date: str  # ISO format datetime
    payload: Optional[dict] = None  # дополнительные данные (например, product_data)
