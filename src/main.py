"""
NeoMarket Moderation Service
Точка входа FastAPI
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.database import Base, engine
from src.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Создаём таблицы при старте (для разработки)"""
    Base.metadata.create_all(bind=engine)
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


# Подключение роутеров (будем добавлять по мере создания)
# from src.routes import events
# app.include_router(events.router)

# Подключение роутеров
from src.routes import events
app.include_router(events.router)

# Подключение роутеров
from src.routes import queue
app.include_router(queue.router)
