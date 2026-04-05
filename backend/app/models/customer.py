import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class CustomerStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    disconnected = "disconnected"
    terminated = "terminated"


class Customer(BaseModel):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("pppoe_username", "owner_id", name="uq_customers_pppoe_owner"),
        UniqueConstraint("email", "owner_id", name="uq_customers_email_owner"),
    )

    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    pppoe_username: Mapped[str] = mapped_column(String(100), nullable=False)
    pppoe_password: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus), default=CustomerStatus.active, nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    mikrotik_secret_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mikrotik_queue_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mac_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    router_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routers.id"), nullable=True
    )
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("areas.id"), nullable=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    billing_due_day: Mapped[int] = mapped_column(Integer, default=15, server_default="15", nullable=False)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)

    plan = relationship("Plan", lazy="selectin")
    router = relationship("Router", lazy="selectin")
    area = relationship("Area", lazy="selectin")
