import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from src.models.ticket import Ticket, TicketStatus
from src.models.processed_event import ProcessedEvent
from src.schemas.events import B2BEventRequest, B2BEventType


def process_b2b_event(db: Session, event: B2BEventRequest) -> None:
    """Обработка событий от B2B (US-MOD-01)"""
    
    existing = db.query(ProcessedEvent).filter(
        ProcessedEvent.sender_service == "b2b",
        ProcessedEvent.idempotency_key == str(event.idempotency_key)
    ).first()
    if existing:
        return
    
    product_id = str(event.payload.product_id)
    seller_id = str(event.payload.seller_id)
    
    if event.event_type == B2BEventType.PRODUCT_CREATED:
        kind = "CREATE"
        ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
        if ticket:
            ticket.product_data_after = event.payload.json_after
            ticket.status = TicketStatus.PENDING
            ticket.updated_at = datetime.now(timezone.utc)
            ticket.kind = kind
        else:
            ticket = Ticket(
                product_id=product_id,
                seller_id=seller_id,
                status=TicketStatus.PENDING,
                product_data_after=event.payload.json_after,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                kind=kind,
                queue_priority=4
            )
            db.add(ticket)
    
    elif event.event_type == B2BEventType.PRODUCT_EDITED:
        kind = "EDIT"
        ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
        if not ticket:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_REQUEST", "message": f"Ticket for product {product_id} not found"}
            )
        if ticket.status in (TicketStatus.APPROVED, TicketStatus.BLOCKED):
            ticket.status = TicketStatus.PENDING
        ticket.product_data_before = ticket.product_data_after
        ticket.product_data_after = event.payload.json_after
        ticket.updated_at = datetime.now(timezone.utc)
        ticket.kind = kind
    
    elif event.event_type == B2BEventType.PRODUCT_DELETED:
        ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
        if ticket:
            db.delete(ticket)
    
    db.add(ProcessedEvent(
        sender_service="b2b",
        idempotency_key=str(event.idempotency_key),
        product_id=product_id,
        event_type=event.event_type.value,
    ))
    db.commit()
