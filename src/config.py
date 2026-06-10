import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_title: str = "NeoMarket Moderation Service"
    app_version: str = "1.0.0"
    debug: bool = True
    
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./moderation.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key")
    
    # URL для связи с B2B
    b2b_url: str = os.getenv("B2B_URL", "http://localhost:8000")
    
    # Межсервисный ключ
    service_key: str = os.getenv("MOD_SERVICE_KEY", "moderation-secret-key")
    
    # Таймаут для IN_REVIEW (минуты)
    review_timeout_minutes: int = 30
    
    # Флаг для тестов (отключает отправку в B2B)
    test_mode: bool = False
    
    model_config = {"env_file": ".env"}


settings = Settings()
