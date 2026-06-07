import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.models.ticket import Ticket, TicketStatus
from src.models.processed_event import ProcessedEvent
from src.schemas.events import B2BEventRequest, B2BEventType


def process_b2b_event(db: Session, event: B2BEventRequest) -> None:
    """Обработка событий от B2B (US-MOD-01)"""
    
    # 1. Идемпотентность
    existing = db.query(ProcessedEvent).filter(
        ProcessedEvent.sender_service == "b2b",
        ProcessedEvent.idempotency_key == str(event.idempotency_key)
    ).first()
    if existing:
        return  # уже обработано
    
    # 2. Найти или создать тикет
    ticket = db.query(Ticket).filter(Ticket.product_id == str(event.product_id)).first()
    
    if event.event == B2BEventType.CREATED:
        if ticket:
            # Тикет уже существует — обновляем данные
            ticket.product_data_after = event.payload
            ticket.status = TicketStatus.PENDING
            ticket.updated_at = datetime.now(timezone.utc)
        else:
            # Создаём новый тикет
            ticket = Ticket(
                product_id=str(event.product_id),
                seller_id=str(event.seller_id),
                status=TicketStatus.PENDING,
                product_data_after=event.payload,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(ticket)
    
    elif event.event == B2BEventType.EDITED:
        if not ticket:
            # Тикет не найден — может быть, надо создать? По канону — создаём
            ticket = Ticket(
                product_id=str(event.product_id),
                seller_id=str(event.seller_id),
                status=TicketStatus.PENDING,
                product_data_after=event.payload,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(ticket)
        else:
            # Если тикет был MODERATED/BLOCKED — возвращаем в IN_REVIEW
            if ticket.status in (TicketStatus.APPROVED, TicketStatus.BLOCKED):
                ticket.status = TicketStatus.IN_REVIEW
            # Обновляем данные
            ticket.product_data_before = ticket.product_data_after
            ticket.product_data_after = event.payload
            ticket.updated_at = datetime.now(timezone.utc)
    
    elif event.event == B2BEventType.DELETED:
        if ticket:
            # Удаляем тикет или помечаем как удалённый
            db.delete(ticket)
    
    # 3. Записать идемпотентность
    db.add(ProcessedEvent(
        sender_service="b2b",
        idempotency_key=str(event.idempotency_key),
        product_id=str(event.product_id),
        event_type=event.event.value,
    ))
    db.commit()
