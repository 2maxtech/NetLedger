import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Plan(BaseModel):
    __tablename__ = "plans"
    __table_args__ = (
        UniqueConstraint("name", "owner_id", name="uq_plans_name_owner"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    download_mbps: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_mbps: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_cap_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fup_download_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fup_upload_mbps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
