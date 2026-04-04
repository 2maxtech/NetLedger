from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "NetLedger"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://netbill:netbill@db:5432/netbill"
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # MikroTik RouterOS
    MIKROTIK_URL: str = "http://192.168.40.30"
    MIKROTIK_USER: str = "admin"
    MIKROTIK_PASSWORD: str = ""

    BILLING_GENERATE_DAY: int = 1
    BILLING_DUE_DAY: int = 15
    BILLING_REMINDER_DAYS_BEFORE_DUE: int = 5
    BILLING_THROTTLE_DAYS_AFTER_DUE: int = 3
    BILLING_DISCONNECT_DAYS_AFTER_DUE: int = 5
    BILLING_TERMINATE_DAYS_AFTER_DUE: int = 35
    THROTTLE_DOWNLOAD_MBPS: int = 1
    THROTTLE_UPLOAD_KBPS: int = 512

    # Email notifications (configure via .env)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@netledger.io"

    class Config:
        env_file = ".env"


settings = Settings()
