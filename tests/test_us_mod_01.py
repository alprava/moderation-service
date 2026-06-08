import uuid
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.ticket import Ticket, TicketStatus

# Создаём тестовую базу
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_created_pending():
    """PRODUCT_CREATED → создаёт тикет в PENDING"""
    product_id = str(uuid.uuid4())
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "event_type": "PRODUCT_CREATED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": product_id,
            "seller_id": str(uuid.uuid4()),
            "json_after": {"title": "Test Product"}
        }
    }
    resp = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp.status_code == 200
    
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
    assert ticket is not None
    assert ticket.status == TicketStatus.PENDING
    db.close()


def test_edited_returns_to_pending():
    """PRODUCT_EDITED после APPROVED/BLOCKED → возвращает в PENDING (очередь)"""
    db = SessionLocal()
    product_id = str(uuid.uuid4())
    ticket = Ticket(
        product_id=product_id,
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.APPROVED,
        product_data_after={}
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "event_type": "PRODUCT_EDITED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": product_id,
            "seller_id": str(uuid.uuid4()),
            "json_after": {"title": "Updated"}
        }
    }
    resp = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp.status_code == 200
    
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
    assert ticket.status == TicketStatus.PENDING
    db.close()


def test_deleted_archived():
    """PRODUCT_DELETED → удаляет тикет"""
    db = SessionLocal()
    product_id = str(uuid.uuid4())
    ticket = Ticket(
        product_id=product_id,
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.PENDING,
        product_data_after={}
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "event_type": "PRODUCT_DELETED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": product_id,
            "seller_id": str(uuid.uuid4()),
            "json_after": None
        }
    }
    resp = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp.status_code == 200
    
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
    assert ticket is None
    db.close()


def test_duplicate_event_no_side_effects():
    """Повторное событие с тем же idempotency_key → 200 без изменений"""
    product_id = str(uuid.uuid4())
    idem_key = str(uuid.uuid4())
    event = {
        "idempotency_key": idem_key,
        "event_type": "PRODUCT_CREATED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": product_id,
            "seller_id": str(uuid.uuid4()),
            "json_after": {}
        }
    }
    resp1 = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    resp2 = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp1.status_code == resp2.status_code == 200
    
    db = SessionLocal()
    count = db.query(Ticket).filter(Ticket.product_id == product_id).count()
    assert count == 1
    db.close()


def test_missing_service_header_401():
    """Без X-Service-Key → 401"""
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "event_type": "PRODUCT_CREATED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": str(uuid.uuid4()),
            "seller_id": str(uuid.uuid4()),
            "json_after": {}
        }
    }
    resp = client.post("/api/v1/b2b/events", json=event)
    assert resp.status_code == 401


def test_edited_missing_ticket_returns_400():
    """PRODUCT_EDITED для несуществующего тикета → 400"""
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "event_type": "PRODUCT_EDITED",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "product_id": str(uuid.uuid4()),
            "seller_id": str(uuid.uuid4()),
            "json_after": {}
        }
    }
    resp = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp.status_code == 400
