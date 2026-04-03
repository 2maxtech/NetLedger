from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.customer import Customer
from app.models.pppoe_session import PPPoESession
from app.models.user import User
from app.services import gateway

router = APIRouter(prefix="/pppoe", tags=["pppoe"])


@router.get("/sessions")
async def list_active_sessions(
    current_user: User = Depends(get_current_user),
):
    try:
        sessions = await gateway.get_active_sessions()
        return sessions
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway unreachable: {str(e)}")


@router.delete("/sessions/{session_id}")
async def kill_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(PPPoESession).where(PPPoESession.session_id == session_id, PPPoESession.ended_at.is_(None))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    cust_result = await db.execute(select(Customer).where(Customer.id == session.customer_id))
    customer = cust_result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    try:
        response = await gateway.disconnect_customer(str(customer.id), customer.pppoe_username)
        return {"status": "killed", "detail": response}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway error: {str(e)}")
