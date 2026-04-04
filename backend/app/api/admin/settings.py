import logging
import smtplib
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.app_setting import AppSetting
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

SMTP_KEYS = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from", "smtp_from_name"]


async def save_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(AppSetting(key=key, value=value))


async def get_smtp_settings(db: AsyncSession) -> dict:
    result = await db.execute(select(AppSetting).where(AppSetting.key.in_(SMTP_KEYS)))
    return {s.key: s.value for s in result.scalars().all()}


@router.get("/smtp")
async def get_smtp(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Get SMTP settings (password masked)."""
    settings = await get_smtp_settings(db)
    if "smtp_password" in settings and settings["smtp_password"]:
        settings["smtp_password"] = "********"
    return settings


@router.put("/smtp")
async def update_smtp(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Save SMTP settings."""
    allowed = {k: v for k, v in body.items() if k in SMTP_KEYS}
    for key, value in allowed.items():
        await save_setting(db, key, str(value))
    await db.flush()
    return {"status": "saved", "keys_updated": list(allowed.keys())}


@router.post("/smtp/test")
async def test_smtp(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Send a test email using stored SMTP settings."""
    to_email = body.get("to")
    if not to_email:
        raise HTTPException(status_code=400, detail="'to' email address required")

    settings = await get_smtp_settings(db)
    host = settings.get("smtp_host", "")
    port = int(settings.get("smtp_port", 587))
    user = settings.get("smtp_user", "")
    password = settings.get("smtp_password", "")
    from_addr = settings.get("smtp_from", user)
    from_name = settings.get("smtp_from_name", "NetLedger")

    if not host:
        raise HTTPException(status_code=400, detail="SMTP not configured (smtp_host missing)")

    try:
        msg = MIMEText("This is a test email from NetLedger.")
        msg["Subject"] = "NetLedger SMTP Test"
        msg["From"] = f"{from_name} <{from_addr}>"
        msg["To"] = to_email

        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if port != 465:
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to_email], msg.as_string())

        return {"status": "sent", "to": to_email}
    except Exception as e:
        logger.error(f"SMTP test failed: {e}")
        raise HTTPException(status_code=502, detail=f"SMTP error: {e}")
