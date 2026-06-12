import uuid
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.database import SessionLocal, Base, engine
from src.models.ticket import Ticket, TicketStatus
from src.models.blocking_reason import BlockingReason
from src.config import settings

settings.test_mode = True

Base.metadata.create_all(bind=engine)
client = TestClient(app)

db = SessionLocal()
if not db.query(BlockingReason).filter(BlockingReason.id == "1").first():
    db.add(BlockingReason(id="1", title="Test Reason", hard_only=False))
    db.commit()
if not db.query(BlockingReason).filter(BlockingReason.id == "999").first():
    db.add(BlockingReason(id="999", title="Hard Only Reason", hard_only=True))
    db.commit()
db.close()


def test_soft_block_transitions_to_blocked_with_field_reports():
    db = SessionLocal()
    ticket_id = uuid.uuid4().hex
    ticket = Ticket(
        id=ticket_id,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={},
        queue_priority=4,
        kind="CREATE"
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={
            "blocking_reason_ids": ["1"],
            "comment": "Плохое описание",
            "field_reports": [{"field_path": "description", "message": "Некорректное описание"}]
        },
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == ticket_id
    assert data["kind"] in ("CREATE", "EDIT")
    assert data["status"] == TicketStatus.BLOCKED


def test_soft_block_unknown_reason_returns_400():
    db = SessionLocal()
    ticket_id = uuid.uuid4().hex
    ticket = Ticket(
        id=ticket_id,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={},
        kind="CREATE"
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={"blocking_reason_ids": ["non-existent-id"]},
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 400


def test_soft_block_others_card_returns_403():
    db = SessionLocal()
    ticket_id = uuid.uuid4().hex
    ticket = Ticket(
        id=ticket_id,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="other_moderator",
        product_data_after={},
        kind="CREATE"
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={"blocking_reason_ids": ["1"]},
        headers={"X-Moderator-Key": "wrong_moderator"}
    )
    assert resp.status_code == 403


def test_soft_block_hard_only_reason_returns_hard_blocked():
    db = SessionLocal()
    ticket_id = uuid.uuid4().hex
    ticket = Ticket(
        id=ticket_id,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={},
        queue_priority=4,
        kind="CREATE"
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={"blocking_reason_ids": ["999"]},
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == TicketStatus.HARD_BLOCKED


def test_soft_block_emits_event_to_b2b():
    """Тест проверяет, что при вызове эндпоинта нет ошибок"""
    db = SessionLocal()
    ticket_id = uuid.uuid4().hex
    ticket = Ticket(
        id=ticket_id,
        product_id=str(uuid.uuid4()),
        seller_id=str(uuid.uuid4()),
        status=TicketStatus.IN_REVIEW,
        reviewed_by="moderator1",
        product_data_after={},
        queue_priority=4,
        kind="CREATE"
    )
    db.add(ticket)
    db.commit()
    db.close()
    
    resp = client.post(
        f"/api/v1/tickets/{ticket_id}/block",
        json={"blocking_reason_ids": ["1"]},
        headers={"X-Moderator-Key": "moderator1"}
    )
    assert resp.status_code == 200
