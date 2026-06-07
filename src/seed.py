from sqlalchemy.orm import Session
from src.models.blocking_reason import BlockingReason


def seed_blocking_reasons(db: Session):
    """Заполняем справочник причин блокировки"""
    reasons = [
        BlockingReason(id="1", title="Описание не соответствует", comment="Товар описан неверно", hard_only=False),
        BlockingReason(id="2", title="Плохое качество фото", comment="Фото размытые или не отражают товар", hard_only=False),
        BlockingReason(id="3", title="Нарушение авторских прав", comment="Использованы чужие фото", hard_only=True),
        BlockingReason(id="4", title="Контрафакт", comment="Товар поддельный", hard_only=True),
    ]
    for reason in reasons:
        existing = db.query(BlockingReason).filter(BlockingReason.id == reason.id).first()
        if not existing:
            db.add(reason)
    db.commit()
