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
    """CREATED → создаёт тикет в PENDING"""
    product_id = str(uuid.uuid4())
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": product_id,
        "seller_id": str(uuid.uuid4()),
        "event": "CREATED",
        "date": datetime.now(timezone.utc).isoformat(),
        "payload": {"title": "Test Product"}
    }
    resp = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp.status_code == 200
    
    # Проверяем тикет в БД
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
    assert ticket is not None
    assert ticket.status == TicketStatus.PENDING
    db.close()


def test_edited_returns_to_review():
    """EDITED после MODERATED/BLOCKED → возвращает в IN_REVIEW"""
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
        "product_id": product_id,
        "seller_id": str(uuid.uuid4()),
        "event": "EDITED",
        "date": datetime.now(timezone.utc).isoformat(),
        "payload": {"title": "Updated"}
    }
    resp = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp.status_code == 200
    
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
    assert ticket.status == TicketStatus.IN_REVIEW
    db.close()


def test_deleted_archived():
    """DELETED → удаляет тикет"""
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
        "product_id": product_id,
        "seller_id": str(uuid.uuid4()),
        "event": "DELETED",
        "date": datetime.now(timezone.utc).isoformat(),
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
        "product_id": product_id,
        "seller_id": str(uuid.uuid4()),
        "event": "CREATED",
        "date": datetime.now(timezone.utc).isoformat(),
    }
    resp1 = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    resp2 = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp1.status_code == resp2.status_code == 200
    
    db = SessionLocal()
    count = db.query(Ticket).filter(Ticket.product_id == product_id).count()
    assert count == 1  # только один тикет
    db.close()


def test_missing_service_header_401():
    """Без X-Service-Key → 401"""
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": str(uuid.uuid4()),
        "seller_id": str(uuid.uuid4()),
        "event": "CREATED",
        "date": datetime.now(timezone.utc).isoformat(),
    }
    resp = client.post("/api/v1/b2b/events", json=event)  # без заголовка
    assert resp.status_code == 401


def test_edited_updates_in_review():
    """EDITED во время IN_REVIEW обновляет поля"""
    db = SessionLocal()
    product_id = str(uuid.uuid4())
    ticket = Ticket(
        product_id=product_id,
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        product_data_after={"title": "Old"}
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    event = {
        "idempotency_key": str(uuid.uuid4()),
        "product_id": product_id,
        "seller_id": str(uuid.uuid4()),
        "event": "EDITED",
        "date": datetime.now(timezone.utc).isoformat(),
        "payload": {"title": "New"}
    }
    resp = client.post("/api/v1/b2b/events", json=event, headers={"X-Service-Key": "moderation-secret-key"})
    assert resp.status_code == 200
    
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.product_id == product_id).first()
    assert ticket.status == TicketStatus.IN_REVIEW  # статус не меняется
    assert ticket.product_data_after["title"] == "New"
    db.close()
