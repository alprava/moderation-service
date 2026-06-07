from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas.events import B2BEventRequest
from src.services.event_service import process_b2b_event
from src.config import settings

router = APIRouter(prefix="/api/v1/b2b", tags=["B2B Events"])


def verify_service_key(x_service_key: str | None = Header(default=None)) -> bool:
    """Проверка межсервисного ключа"""
    if x_service_key is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-Service-Key header is required"}
        )
    if x_service_key != settings.service_key:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Invalid X-Service-Key"}
        )
    return True


@router.post("/events", status_code=200)
def receive_b2b_event(
    event: B2BEventRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_service_key),
):
    """Приём событий о товарах от B2B (US-MOD-01)"""
    try:
        process_b2b_event(db, event)
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "INTERNAL_ERROR", "message": str(e)}
        )
