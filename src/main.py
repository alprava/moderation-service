from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.database import Base, engine, SessionLocal
from src.exceptions import register_exception_handlers
from src.seed import seed_blocking_reasons


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Создаём таблицы и добавляем начальные данные"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_blocking_reasons(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Регистрация обработчиков ошибок
register_exception_handlers(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}


# Подключение роутеров
from src.routes import events
app.include_router(events.router)

from src.routes import queue
app.include_router(queue.router)

from src.routes import tickets
app.include_router(tickets.router)
