import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.ticket import Ticket, TicketStatus

# Создаём тестовую базу
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def test_next_returns_oldest_pending():
    """Самая старая PENDING карточка переходит в IN_REVIEW"""
    db = SessionLocal()
    # Очищаем таблицу
    db.query(Ticket).delete()
    
    older_id = str(uuid.uuid4())
    newer_id = str(uuid.uuid4())
    
    ticket1_id = uuid.uuid4().hex
    ticket2_id = uuid.uuid4().hex
    
    ticket1 = Ticket(
        id=ticket1_id,
        product_id=older_id,
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.PENDING,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        product_data_after={},
        queue_priority=4
    )
    ticket2 = Ticket(
        id=ticket2_id,
        product_id=newer_id,
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        product_data_after={},
        queue_priority=4
    )
    db.add_all([ticket1, ticket2])
    db.commit()
    db.close()
    
    moderator_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/queue/claim",
        headers={"X-Moderator-Key": moderator_id}
    )
    assert resp.status_code == 200
    data = resp.json()
    
    # Проверяем формат ответа по контракту
    assert "id" in data
    assert data["id"] == ticket1_id
    assert data["product_id"] == older_id
    assert "kind" in data
    assert data["status"] == TicketStatus.IN_REVIEW
    assert "queue_priority" in data
    
    db = SessionLocal()
    ticket = db.query(Ticket).filter(Ticket.product_id == older_id).first()
    assert ticket.status == TicketStatus.IN_REVIEW
    assert ticket.reviewed_by == moderator_id
    db.close()


def test_concurrent_two_moderators_get_different_cards():
    """Два модератора получают разные карточки"""
    db = SessionLocal()
    db.query(Ticket).delete()
    
    product_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    for pid in product_ids:
        ticket = Ticket(
            id=uuid.uuid4().hex,
            product_id=pid,
            seller_id=str(uuid.uuid4()),
            status=TicketStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            product_data_after={},
            queue_priority=4
        )
        db.add(ticket)
    db.commit()
    db.close()
    
    moderator1 = str(uuid.uuid4())
    moderator2 = str(uuid.uuid4())
    
    resp1 = client.post("/api/v1/queue/claim", headers={"X-Moderator-Key": moderator1})
    resp2 = client.post("/api/v1/queue/claim", headers={"X-Moderator-Key": moderator2})
    
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    
    data1 = resp1.json()
    data2 = resp2.json()
    
    assert data1["product_id"] != data2["product_id"]


def test_empty_queue_returns_204():
    """Пустая очередь возвращает 204"""
    db = SessionLocal()
    db.query(Ticket).delete()
    db.commit()
    db.close()
    
    moderator_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/queue/claim",
        headers={"X-Moderator-Key": moderator_id}
    )
    assert resp.status_code == 204
    assert resp.text == ""


def test_moderator_already_has_in_review_returns_409():
    """Модератор уже имеет IN_REVIEW карточку → 409"""
    db = SessionLocal()
    db.query(Ticket).delete()
    
    moderator_id = str(uuid.uuid4())
    
    ticket = Ticket(
        id=uuid.uuid4().hex,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by=moderator_id,
        product_data_after={},
        queue_priority=4
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    resp = client.post(
        "/api/v1/queue/claim",
        headers={"X-Moderator-Key": moderator_id}
    )
    assert resp.status_code == 409
