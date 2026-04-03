import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ActivityEventType(str, enum.Enum):
    login = "login"
    logout = "logout"
    auth_fail = "auth_fail"
    ip_change = "ip_change"
    plan_change = "plan_change"
    throttled = "throttled"
    disconnected = "disconnected"


class CustomerActivity(BaseModel):
    __tablename__ = "customer_activities"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    event_type: Mapped[ActivityEventType] = mapped_column(Enum(ActivityEventType), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
