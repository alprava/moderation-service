import uuid
from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


class B2BEventType(str, Enum):
    PRODUCT_CREATED = "PRODUCT_CREATED"
    PRODUCT_EDITED = "PRODUCT_EDITED"
    PRODUCT_DELETED = "PRODUCT_DELETED"


class ProductPayload(BaseModel):
    """Вложенный payload с данными товара"""
    product_id: uuid.UUID
    seller_id: uuid.UUID
    json_after: Optional[dict] = None


class B2BEventRequest(BaseModel):
    """Событие от B2B-сервиса (US-MOD-01) по openapi"""
    idempotency_key: uuid.UUID
    event_type: B2BEventType
    occurred_at: str
    payload: ProductPayload
