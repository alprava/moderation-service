from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta

from src.database import get_db
from src.models.ticket import Ticket, TicketStatus
from src.config import settings

router = APIRouter(prefix="/api/v1/queue", tags=["Queue"])


def verify_moderator_key(x_moderator_key: str = Header(...)) -> str:
    """Проверка ключа модератора (упрощённо)"""
    if not x_moderator_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-Moderator-Key header is required"}
        )
    return x_moderator_key


@router.get("/next", status_code=200)
def get_next_card(
    moderator_id: str = Depends(verify_moderator_key),
    db: Session = Depends(get_db),
):
    """Получить следующую карточку из очереди (US-MOD-02)"""
    
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
    
    # 2. Ищем самую старую PENDING карточку
    ticket = db.query(Ticket).filter(
        Ticket.status == TicketStatus.PENDING
    ).order_by(Ticket.created_at.asc()).first()
    
    if not ticket:
        raise HTTPException(
            status_code=204,
            detail={"code": "NO_CONTENT", "message": "Queue is empty"}
        )
    
    # 3. Блокируем карточку
    ticket.status = TicketStatus.IN_REVIEW
    ticket.reviewed_by = moderator_id
    ticket.reviewed_at = datetime.now(timezone.utc)
    ticket.in_review_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.review_timeout_minutes)
    
    db.commit()
    db.refresh(ticket)
    
    # 4. Возвращаем карточку
    return {
        "ticket_id": ticket.id,
        "product_id": ticket.product_id,
        "seller_id": ticket.seller_id,
        "status": ticket.status,
        "product_data": ticket.product_data_after,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "in_review_expires_at": ticket.in_review_expires_at.isoformat() if ticket.in_review_expires_at else None,
    }
