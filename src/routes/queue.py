from fastapi import APIRouter, Depends, HTTPException, Header, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update

from src.database import get_db
from src.models.ticket import Ticket, TicketStatus
from src.config import settings

router = APIRouter(prefix="/api/v1/queue", tags=["Queue"])


def verify_moderator_key(x_moderator_key: str = Header(...)) -> str:
    """Проверка ключа модератора"""
    if not x_moderator_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-Moderator-Key header is required"}
        )
    return x_moderator_key


@router.post("/claim", status_code=200)
def claim_next_card(
    moderator_id: str = Depends(verify_moderator_key),
    db: Session = Depends(get_db),
):
    """
    Получить следующую карточку из очереди (US-MOD-02).
    POST /api/v1/queue/claim
    """
    
    # 1. Проверяем, нет ли у модератора уже карточки в IN_REVIEW
    existing = db.query(Ticket).filter(
        Ticket.reviewed_by == moderator_id,
        Ticket.status == TicketStatus.IN_REVIEW
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "CONFLICT", "message": "Moderator already has a card in review"}
        )
    
    # 2. Ищем самую старую PENDING карточку с учётом приоритета
    #    Сначала по queue_priority (1 — высший), потом по created_at
    ticket = db.query(Ticket).filter(
        Ticket.status == TicketStatus.PENDING
    ).order_by(
        Ticket.queue_priority.asc(),   # 1,2,3,4
        Ticket.created_at.asc()        # FIFO внутри приоритета
    ).with_for_update(skip_locked=True).first()
    
    if not ticket:
        # Пустая очередь — возвращаем 204 без тела
        return Response(status_code=204)
    
    # 3. Блокируем карточку
    ticket.status = TicketStatus.IN_REVIEW
    ticket.reviewed_by = moderator_id
    ticket.reviewed_at = datetime.now(timezone.utc)
    ticket.in_review_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.review_timeout_minutes)
    
    db.commit()
    db.refresh(ticket)
    
    # 4. Возвращаем карточку в формате TicketResponse (по контракту)
    return {
        "id": ticket.id,                      # id вместо ticket_id
        "product_id": ticket.product_id,
        "seller_id": ticket.seller_id,
        "kind": getattr(ticket, 'kind', 'product'),  # kind (по умолчанию 'product')
        "status": ticket.status,
        "queue_priority": ticket.queue_priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
    }
