from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import httpx
import uuid
from pydantic import BaseModel
from typing import Optional, List

from src.database import get_db
from src.models.ticket import Ticket, TicketStatus
from src.models.blocking_reason import BlockingReason
from src.config import settings

router = APIRouter(prefix="/api/v1/tickets", tags=["Tickets"])


class FieldReport(BaseModel):
    field_name: str
    sku_id: Optional[str] = None
    comment: str


class SoftBlockRequest(BaseModel):
    reason_id: str
    comment: Optional[str] = None
    field_reports: Optional[List[FieldReport]] = None


def verify_moderator_key(x_moderator_key: str = Header(...)) -> str:
    """Проверка ключа модератора"""
    if not x_moderator_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-Moderator-Key header is required"}
        )
    return x_moderator_key


def send_event_to_b2b(product_id: str, hard_block: bool, 
                       blocking_reason_id: str, moderator_comment: str, 
                       field_reports: list, idempotency_key: str) -> None:
    """Отправка события BLOCKED в B2B"""
    event_data = {
        "idempotency_key": idempotency_key,
        "product_id": product_id,
        "event_type": "BLOCKED",
        "hard_block": hard_block,
        "blocking_reason_id": blocking_reason_id,
        "moderator_comment": moderator_comment,
        "field_reports": field_reports or [],
        "occurred_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{settings.b2b_url}/api/v1/moderation/events",
                json=event_data,
                headers={"X-Service-Key": settings.service_key},
                timeout=5.0
            )
            response.raise_for_status()
    except Exception as e:
        print(f"Error sending event to B2B: {e}")


@router.post("/{ticket_id}/block", status_code=200)
def soft_block_ticket(
    ticket_id: str,
    request: SoftBlockRequest,
    db: Session = Depends(get_db),
    moderator_id: str = Depends(verify_moderator_key),
):
    """Мягкая блокировка тикета (US-MOD-04)"""
    
    # 1. Находим тикет
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Ticket not found"}
        )
    
    # 2. Проверяем, что тикет в статусе IN_REVIEW
    if ticket.status != TicketStatus.IN_REVIEW:
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "message": f"Ticket is {ticket.status}, expected IN_REVIEW"}
        )
    
    # 3. Проверяем, что модератор владеет тикетом
    if ticket.reviewed_by != moderator_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "This ticket is not assigned to you"}
        )
    
    # 4. Валидируем причину блокировки
    reason = db.query(BlockingReason).filter(
        BlockingReason.id == request.reason_id,
        BlockingReason.is_active == True
    ).first()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": f"Blocking reason {request.reason_id} not found or inactive"}
        )
    
    # 5. Проверяем, что причина не hard_only
    if reason.hard_only:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": "This reason is for hard block only, use hard block endpoint"}
        )
    
    # 6. Валидация field_reports
    valid_fields = {"title", "description", "product_images", "category", "sku_name", "sku_image", "sku_price"}
    if request.field_reports:
        for fr in request.field_reports:
            if fr.field_name not in valid_fields:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "INVALID_REQUEST", "message": f"Invalid field_name: {fr.field_name}"}
                )
    
    # 7. Обновляем тикет
    ticket.status = TicketStatus.BLOCKED
    ticket.blocking_reason_id = request.reason_id
    ticket.moderator_comment = request.comment
    ticket.field_reports = [fr.dict() for fr in request.field_reports] if request.field_reports else []
    ticket.updated_at = datetime.now(timezone.utc)
    ticket.reviewed_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(ticket)
    
    # 8. Отправляем событие в B2B
    idem_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ticket.product_id}:BLOCKED:{ticket.id}"))
    send_event_to_b2b(
        product_id=ticket.product_id,
        hard_block=False,
        blocking_reason_id=request.reason_id,
        moderator_comment=request.comment or "",
        field_reports=[fr.dict() for fr in request.field_reports] if request.field_reports else [],
        idempotency_key=idem_key
    )
    
    return {
        "ticket_id": ticket.id,
        "status": ticket.status,
        "blocking_reason_id": ticket.blocking_reason_id,
        "moderator_comment": ticket.moderator_comment,
        "field_reports": ticket.field_reports,
        "reviewed_by": ticket.reviewed_by,
        "reviewed_at": ticket.reviewed_at.isoformat() if ticket.reviewed_at else None,
    }
