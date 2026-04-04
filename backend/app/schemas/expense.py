import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.expense import ExpenseCategory


class ExpenseCreate(BaseModel):
    category: ExpenseCategory
    description: str
    amount: Decimal
    date: date
    receipt_number: str | None = None


class ExpenseUpdate(BaseModel):
    category: ExpenseCategory | None = None
    description: str | None = None
    amount: Decimal | None = None
    date: date | None = None
    receipt_number: str | None = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    category: ExpenseCategory
    description: str
    amount: Decimal
    date: date
    receipt_number: str | None
    recorded_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
