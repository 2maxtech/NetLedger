import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SessionTraffic(BaseModel):
    __tablename__ = "session_traffic"

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pppoe_sessions.id"), nullable=False)
    bytes_in: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    bytes_out: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    packets_in: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    packets_out: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
