import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class BandwidthUsage(BaseModel):
    __tablename__ = "bandwidth_usage"
    __table_args__ = (UniqueConstraint("customer_id", "date", name="uq_bandwidth_customer_date"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_bytes_in: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_bytes_out: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    peak_download_mbps: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    peak_upload_mbps: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
