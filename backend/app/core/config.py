from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "2maXnetBill"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "postgresql+asyncpg://netbill:netbill@db:5432/netbill"
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    GATEWAY_AGENT_URL: str = "https://gateway:8443"
    GATEWAY_API_KEY: str = "change-me-in-production"

    BILLING_GENERATE_DAY: int = 1
    BILLING_DUE_DAY: int = 15
    BILLING_REMINDER_DAYS_BEFORE_DUE: int = 5
    BILLING_THROTTLE_DAYS_AFTER_DUE: int = 3
    BILLING_DISCONNECT_DAYS_AFTER_DUE: int = 5
    BILLING_TERMINATE_DAYS_AFTER_DUE: int = 35
    THROTTLE_DOWNLOAD_MBPS: int = 1
    THROTTLE_UPLOAD_KBPS: int = 512

    class Config:
        env_file = ".env"


settings = Settings()
