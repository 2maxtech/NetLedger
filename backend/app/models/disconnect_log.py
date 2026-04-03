import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class DisconnectAction(str, enum.Enum):
    throttle = "throttle"
    disconnect = "disconnect"
    reconnect = "reconnect"


class DisconnectReason(str, enum.Enum):
    non_payment = "non_payment"
    manual = "manual"
    expired = "expired"


class DisconnectLog(BaseModel):
    __tablename__ = "disconnect_logs"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    action: Mapped[DisconnectAction] = mapped_column(Enum(DisconnectAction), nullable=False)
    reason: Mapped[DisconnectReason] = mapped_column(Enum(DisconnectReason), nullable=False)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    customer = relationship("Customer", lazy="selectin")
    performer = relationship("User", lazy="selectin")
