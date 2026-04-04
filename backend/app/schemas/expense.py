import uuid
import datetime as dt
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from app.models.expense import ExpenseCategory


class ExpenseCreate(BaseModel):
    category: ExpenseCategory
    description: str
    amount: Decimal
    expense_date: dt.date
    receipt_number: Optional[str] = None


class ExpenseUpdate(BaseModel):
    category: Optional[ExpenseCategory] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = None
    expense_date: Optional[dt.date] = None
    receipt_number: Optional[str] = None


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    category: ExpenseCategory
    description: str
    amount: Decimal
    date: dt.date
    receipt_number: Optional[str]
    recorded_by: Optional[uuid.UUID]
    created_at: dt.datetime

    model_config = {"from_attributes": True}
