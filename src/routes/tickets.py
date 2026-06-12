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
    field_path: str
    message: str


class SoftBlockRequest(BaseModel):
    blocking_reason_ids: List[str]
    comment: Optional[str] = None
    field_reports: Optional[List[FieldReport]] = None


def verify_moderator_key(x_moderator_key: str = Header(...)) -> str:
    if not x_moderator_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-Moderator-Key header is required"}
        )
    return x_moderator_key


def send_event_to_b2b(product_id: str, hard_block: bool, 
                       blocking_reason_ids: List[str], comment: str, 
                       field_reports: List[dict], idempotency_key: str) -> None:
    """Отправка события BLOCKED в B2B (формат для B2B)"""
    if settings.test_mode:
        return
    
    event_data = {
        "idempotency_key": idempotency_key,
        "product_id": product_id,
        "event_type": "BLOCKED",
        "hard_block": hard_block,
        "blocking_reason_id": blocking_reason_ids[0] if blocking_reason_ids else None,
        "moderator_comment": comment,
        "field_reports": field_reports,
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
        if not settings.test_mode:
            raise HTTPException(
                status_code=500,
                detail={"code": "B2B_UNAVAILABLE", "message": "Failed to send event to B2B"}
            )


@router.post("/{ticket_id}/block", status_code=200)
def soft_block_ticket(
    ticket_id: str,
    request: SoftBlockRequest,
    db: Session = Depends(get_db),
    moderator_id: str = Depends(verify_moderator_key),
):
    """Мягкая блокировка тикета (US-MOD-04)"""
    
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "Ticket not found"}
        )
    
    if ticket.status != TicketStatus.IN_REVIEW:
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "message": f"Ticket is {ticket.status}, expected IN_REVIEW"}
        )
    
    if ticket.reviewed_by != moderator_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "This ticket is not assigned to you"}
        )
    
    if not request.blocking_reason_ids:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": "blocking_reason_ids is required"}
        )
    
    reason_id = request.blocking_reason_ids[0]
    reason = db.query(BlockingReason).filter(
        BlockingReason.id == reason_id,
        BlockingReason.is_active == True
    ).first()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_REQUEST", "message": f"Blocking reason {reason_id} not found or inactive"}
        )
    
    hard_block = reason.hard_only
    
    if hard_block:
        ticket.status = TicketStatus.HARD_BLOCKED
    else:
        ticket.status = TicketStatus.BLOCKED
    
    ticket.blocking_reason_id = reason_id
    ticket.moderator_comment = request.comment
    
    # Внутреннее хранение: используем field_path и message (по контракту moderation)
    ticket.field_reports = [
        {"field_path": fr.field_path, "message": fr.message}
        for fr in request.field_reports
    ] if request.field_reports else []
    
    ticket.updated_at = datetime.now(timezone.utc)
    ticket.reviewed_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(ticket)
    
    # Для отправки в B2B: конвертируем в формат {field_name, comment}
    b2b_field_reports = [
        {"field_name": fr.field_path, "comment": fr.message, "sku_id": None}
        for fr in request.field_reports
    ] if request.field_reports else []
    
    idem_key = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ticket.product_id}:BLOCKED:{ticket.id}"))
    
    send_event_to_b2b(
        product_id=ticket.product_id,
        hard_block=hard_block,
        blocking_reason_ids=request.blocking_reason_ids,
        comment=request.comment or "",
        field_reports=b2b_field_reports,
        idempotency_key=idem_key
    )
    
    response_kind = ticket.kind if ticket.kind else ("CREATE" if ticket.created_at else "EDIT")
    
    return {
        "id": ticket.id,
        "product_id": ticket.product_id,
        "seller_id": ticket.seller_id,
        "kind": response_kind,
        "status": ticket.status,
        "queue_priority": ticket.queue_priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }
