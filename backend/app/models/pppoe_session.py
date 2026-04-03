import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class PPPoESession(BaseModel):
    __tablename__ = "pppoe_sessions"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    mac_address: Mapped[str] = mapped_column(String(17), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bytes_in: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bytes_out: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    disconnect_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    customer = relationship("Customer", lazy="selectin")
