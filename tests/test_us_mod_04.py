import uuid
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.ticket import Ticket, TicketStatus
from src.models.blocking_reason import BlockingReason

# Создаём тестовую базу
Base.metadata.create_all(bind=engine)

client = TestClient(app)

# Добавляем тестовые причины блокировки
db = SessionLocal()
if not db.query(BlockingReason).filter(BlockingReason.id == "1").first():
    db.add(BlockingReason(id="1", title="Test Reason", hard_only=False))
    db.commit()
if not db.query(BlockingReason).filter(BlockingReason.id == "999").first():
    db.add(BlockingReason(id="999", title="Hard Only Reason", hard_only=True))
    db.commit()
db.close()


def test_soft_block_transitions_to_blocked_with_field_reports():
    """Мягкая блокировка → статус BLOCKED, сохраняются field_reports"""
    db = SessionLocal()
    ticket = Ticket(
        id=uuid.uuid4().hex,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={}
    )
    db.add(ticket)
    db.commit()
    ticket_id = ticket.id
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={
            "blocking_reason_ids": ["1"],
            "moderator_comment": "Плохое описание",
            "field_reports": [{"field_path": "description", "message": "Некорректное описание"}]
        },
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == TicketStatus.BLOCKED
    assert data["blocking_reason_id"] == "1"
    assert data["moderator_comment"] == "Плохое описание"
    assert len(data["field_reports"]) == 1


def test_soft_block_unknown_reason_returns_400():
    """Несуществующая причина блокировки → 400"""
    db = SessionLocal()
    ticket = Ticket(
        id=uuid.uuid4().hex,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={}
    )
    db.add(ticket)
    db.commit()
    ticket_id = ticket.id
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={"blocking_reason_ids": ["non-existent-id"]},
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 400


def test_soft_block_others_card_returns_403():
    """Чужая карточка (не принадлежит модератору) → 403"""
    db = SessionLocal()
    ticket = Ticket(
        id=uuid.uuid4().hex,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="other_moderator",
        product_data_after={}
    )
    db.add(ticket)
    db.commit()
    ticket_id = ticket.id
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={"blocking_reason_ids": ["1"]},
        headers={"X-Moderator-Key": "wrong_moderator"}
    )
    assert resp.status_code == 403


def test_soft_block_invalid_field_path_returns_400():
    """Некорректное поле field_path → 400"""
    db = SessionLocal()
    ticket = Ticket(
        id=uuid.uuid4().hex,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={}
    )
    db.add(ticket)
    db.commit()
    ticket_id = ticket.id
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={
            "blocking_reason_ids": ["1"],
            "field_reports": [{"field_path": "invalid_field", "message": "test"}]
        },
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 400


def test_soft_block_hard_only_reason_returns_400():
    """hard_only причина для мягкой блокировки → 400"""
    db = SessionLocal()
    ticket = Ticket(
        id=uuid.uuid4().hex,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={}
    )
    db.add(ticket)
    db.commit()
    ticket_id = ticket.id
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={"blocking_reason_ids": ["999"]},
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 400
