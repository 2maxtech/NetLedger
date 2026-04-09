import logging
import os
import smtplib
import uuid
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission, require_role
from app.core.tenant import get_tenant_id
from app.models.app_setting import AppSetting
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

SMTP_KEYS = ["smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from", "smtp_from_name"]


async def save_setting(db: AsyncSession, key: str, value: str, tenant_id: uuid.UUID | None = None) -> None:
    query = select(AppSetting).where(AppSetting.key == key)
    if tenant_id is not None:
        query = query.where(AppSetting.owner_id == tenant_id)
    else:
        query = query.where(AppSetting.owner_id.is_(None))
    result = await db.execute(query)
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(AppSetting(key=key, value=value, owner_id=tenant_id))


async def get_smtp_settings(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> dict:
    query = select(AppSetting).where(AppSetting.key.in_(SMTP_KEYS))
    if tenant_id is not None:
        query = query.where(AppSetting.owner_id == tenant_id)
    else:
        query = query.where(AppSetting.owner_id.is_(None))
    result = await db.execute(query)
    return {s.key: s.value for s in result.scalars().all()}


@router.get("/smtp")
async def get_smtp(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get SMTP settings (password masked)."""
    tid = uuid.UUID(tenant_id)
    settings = await get_smtp_settings(db, tenant_id=tid)
    if "smtp_password" in settings and settings["smtp_password"]:
        settings["smtp_password"] = "********"
    return settings


@router.put("/smtp")
async def update_smtp(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Save SMTP settings."""
    tid = uuid.UUID(tenant_id)
    allowed = {k: v for k, v in body.items() if k in SMTP_KEYS}
    for key, value in allowed.items():
        await save_setting(db, key, str(value), tenant_id=tid)
    await db.flush()
    return {"status": "saved", "keys_updated": list(allowed.keys())}


@router.post("/smtp/test")
async def test_smtp(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Send a test email using stored SMTP settings."""
    tid = uuid.UUID(tenant_id)
    to_email = body.get("to")
    if not to_email:
        raise HTTPException(status_code=400, detail="'to' email address required")

    settings = await get_smtp_settings(db, tenant_id=tid)
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


@router.get("/sms")
async def get_sms(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get SMS settings (api_key masked)."""
    tid = uuid.UUID(tenant_id)
    result = await db.execute(select(AppSetting).where(AppSetting.key.like("sms_%"), AppSetting.owner_id == tid))
    sms = {s.key: s.value for s in result.scalars().all()}
    return {
        "provider": sms.get("sms_provider", ""),
        "api_key": "***" if sms.get("sms_api_key") else "",
        "sender_name": sms.get("sms_sender_name", ""),
    }


@router.put("/sms")
async def update_sms(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Save SMS settings."""
    tid = uuid.UUID(tenant_id)
    mapping = {
        "provider": "sms_provider",
        "api_key": "sms_api_key",
        "sender_name": "sms_sender_name",
    }
    for field, key in mapping.items():
        if field in body:
            await save_setting(db, key, str(body[field]), tenant_id=tid)
    await db.flush()
    return {"status": "saved"}


@router.post("/sms/test")
async def test_sms_endpoint(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Send a test SMS using stored SMS settings."""
    from app.services.sms import send_sms
    phone = body.get("phone", "")
    if not phone:
        raise HTTPException(status_code=400, detail="phone required")
    tid = uuid.UUID(tenant_id)
    success = await send_sms(phone, "NetLedger SMS test", db, tenant_id=tid)
    return {"success": success}


# --- Billing Settings ---

BILLING_KEYS = [
    "billing_reminder_days_before_due",
    "billing_throttle_days_after_due",
    "billing_disconnect_days_after_due",
    "billing_terminate_days_after_due",
    "billing_default_due_day",
    "billing_auto_generate",
    "billing_send_invoice_email",
    "billing_send_invoice_sms",
    "nat_redirect_enabled",
]

BILLING_DEFAULTS = {
    "billing_reminder_days_before_due": "5",
    "billing_throttle_days_after_due": "3",
    "billing_disconnect_days_after_due": "5",
    "billing_terminate_days_after_due": "35",
    "billing_default_due_day": "15",
    "billing_auto_generate": "true",
    "billing_send_invoice_email": "true",
    "billing_send_invoice_sms": "true",
    "nat_redirect_enabled": "false",
}


async def get_billing_settings(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> dict:
    query = select(AppSetting).where(AppSetting.key.in_(BILLING_KEYS))
    if tenant_id is not None:
        query = query.where(AppSetting.owner_id == tenant_id)
    else:
        query = query.where(AppSetting.owner_id.is_(None))
    result = await db.execute(query)
    saved = {s.key: s.value for s in result.scalars().all()}
    return {k: saved.get(k, v) for k, v in BILLING_DEFAULTS.items()}


@router.get("/billing")
async def get_billing(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    return await get_billing_settings(db, tenant_id=tid)


@router.put("/billing")
async def update_billing(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    allowed = {k: v for k, v in body.items() if k in BILLING_KEYS}
    for key, value in allowed.items():
        await save_setting(db, key, str(value), tenant_id=tid)
    await db.flush()
    return {"status": "saved", "keys_updated": list(allowed.keys())}


# --- Notification Templates ---

TEMPLATE_KEYS = [
    "tpl_invoice_email_subject",
    "tpl_invoice_email_body",
    "tpl_invoice_sms",
    "tpl_reminder_sms",
    "tpl_overdue_email_subject",
    "tpl_overdue_email_body",
    "tpl_overdue_sms",
]

TEMPLATE_DEFAULTS = {
    "tpl_invoice_email_subject": "Invoice - {amount} due {due_date_short}",
    "tpl_invoice_email_body": "Hi {customer_name},\n\nYour invoice of {amount} for plan {plan_name} has been generated.\nDue date: {due_date}\n\nPlease pay before the due date to avoid service interruption.\n{portal_url}\nPay online: {payment_url}\n\nThank you!",
    "tpl_invoice_sms": "Hi {customer_name}, your bill of {amount} is due on {due_date_short}. Please pay on time to avoid disconnection. Pay online: {payment_url}",
    "tpl_reminder_sms": "Hi {customer_name}, your bill of {amount} is due on {due_date}. Please pay before the due date to avoid service interruption. Pay now: {payment_url}",
    "tpl_overdue_email_subject": "Overdue Notice - {amount}",
    "tpl_overdue_email_body": "Hi {customer_name},\n\nYour invoice of {amount} is now overdue. Please settle your balance immediately to avoid service interruption.\n{portal_url}\nPay now: {payment_url}\n\nThank you!",
    "tpl_overdue_sms": "Hi {customer_name}, your bill of {amount} is overdue. Please pay immediately to avoid disconnection. Pay now: {payment_url}",
}


async def get_template_settings(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> dict:
    query = select(AppSetting).where(AppSetting.key.in_(TEMPLATE_KEYS))
    if tenant_id is not None:
        query = query.where(AppSetting.owner_id == tenant_id)
    else:
        query = query.where(AppSetting.owner_id.is_(None))
    result = await db.execute(query)
    saved = {s.key: s.value for s in result.scalars().all()}
    return {k: saved.get(k, v) for k, v in TEMPLATE_DEFAULTS.items()}


@router.get("/notifications")
async def get_notification_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    return await get_template_settings(db, tenant_id=tid)


@router.put("/notifications")
async def update_notification_templates(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    tid = uuid.UUID(tenant_id)
    allowed = {k: v for k, v in body.items() if k in TEMPLATE_KEYS}
    for key, value in allowed.items():
        await save_setting(db, key, str(value), tenant_id=tid)
    await db.flush()
    return {"status": "saved", "keys_updated": list(allowed.keys())}


# --- Branding / Company Profile ---

BRANDING_KEYS = [
    "company_name",
    "company_address",
    "company_phone",
    "company_email",
    "company_logo_url",
    "invoice_footer",
    "invoice_prefix",
    "portal_slug",
]


def _slugify(name: str) -> str:
    """Convert company name to URL-safe slug."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


async def get_branding_settings(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> dict:
    query = select(AppSetting).where(AppSetting.key.in_(BRANDING_KEYS))
    if tenant_id is not None:
        query = query.where(AppSetting.owner_id == tenant_id)
    else:
        query = query.where(AppSetting.owner_id.is_(None))
    result = await db.execute(query)
    return {s.key: s.value for s in result.scalars().all()}


@router.get("/branding")
async def get_branding(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get company branding settings."""
    tid = uuid.UUID(tenant_id)
    return await get_branding_settings(db, tenant_id=tid)


@router.put("/branding")
async def update_branding(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Save company branding settings."""
    tid = uuid.UUID(tenant_id)
    allowed = {k: v for k, v in body.items() if k in BRANDING_KEYS}
    # Auto-generate portal_slug from company_name
    if "company_name" in allowed and allowed["company_name"]:
        slug = _slugify(allowed["company_name"])
        # Check uniqueness — append tenant short id if collision
        existing = await db.execute(
            select(AppSetting).where(
                AppSetting.key == "portal_slug",
                AppSetting.value == slug,
                AppSetting.owner_id != tid,
            )
        )
        if existing.scalar_one_or_none():
            slug = f"{slug}-{str(tid)[:4]}"
        allowed["portal_slug"] = slug
    for key, value in allowed.items():
        await save_setting(db, key, str(value), tenant_id=tid)
    await db.flush()
    return {"status": "saved", "keys_updated": list(allowed.keys())}


# --- Hotspot Captive Portal Branding ---

HOTSPOT_BRANDING_KEYS = [
    "hotspot_title",
    "hotspot_welcome_message",
    "hotspot_logo_url",
    "hotspot_background_color",
    "hotspot_text_color",
]

HOTSPOT_BRANDING_DEFAULTS = {
    "hotspot_title": "Welcome",
    "hotspot_welcome_message": "Enter your voucher code to connect",
    "hotspot_logo_url": "",
    "hotspot_background_color": "#1a1a2e",
    "hotspot_text_color": "#ffffff",
}


async def get_hotspot_branding_settings(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> dict:
    query = select(AppSetting).where(AppSetting.key.in_(HOTSPOT_BRANDING_KEYS))
    if tenant_id is not None:
        query = query.where(AppSetting.owner_id == tenant_id)
    else:
        query = query.where(AppSetting.owner_id.is_(None))
    result = await db.execute(query)
    saved = {s.key: s.value for s in result.scalars().all()}
    return {k: saved.get(k, v) for k, v in HOTSPOT_BRANDING_DEFAULTS.items()}


@router.get("/hotspot-branding")
async def get_hotspot_branding(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get hotspot captive portal branding settings."""
    tid = uuid.UUID(tenant_id)
    return await get_hotspot_branding_settings(db, tenant_id=tid)


@router.put("/hotspot-branding")
async def update_hotspot_branding(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Save hotspot captive portal branding settings."""
    tid = uuid.UUID(tenant_id)
    allowed = {k: v for k, v in body.items() if k in HOTSPOT_BRANDING_KEYS}
    for key, value in allowed.items():
        await save_setting(db, key, str(value), tenant_id=tid)
    await db.flush()
    return {"status": "saved", "keys_updated": list(allowed.keys())}


# --- Payment Gateway (PayMongo) Settings ---

PAYMENT_KEYS = [
    "paymongo_secret_key", "paymongo_public_key", "paymongo_webhook_secret",
    "paymongo_fee_mode", "paymongo_fee_percent", "paymongo_fee_flat",
]
PAYMENT_DEFAULTS = {
    "paymongo_secret_key": "", "paymongo_public_key": "", "paymongo_webhook_secret": "",
    "paymongo_fee_mode": "pass_to_customer", "paymongo_fee_percent": "2.5", "paymongo_fee_flat": "15",
}


async def get_payment_settings(db: AsyncSession, tenant_id: uuid.UUID | None = None) -> dict:
    query = select(AppSetting).where(AppSetting.key.in_(PAYMENT_KEYS))
    if tenant_id is not None:
        query = query.where(AppSetting.owner_id == tenant_id)
    else:
        query = query.where(AppSetting.owner_id.is_(None))
    result = await db.execute(query)
    saved = {s.key: s.value for s in result.scalars().all()}
    return {k: saved.get(k, v) for k, v in PAYMENT_DEFAULTS.items()}


@router.get("/payments")
async def get_payments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get payment gateway settings (secret key masked)."""
    tid = uuid.UUID(tenant_id)
    settings = await get_payment_settings(db, tenant_id=tid)
    if settings.get("paymongo_secret_key"):
        settings["paymongo_secret_key"] = "********"
    if settings.get("paymongo_webhook_secret"):
        settings["paymongo_webhook_secret"] = "********"
    return settings


@router.put("/payments")
async def update_payments(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Save payment gateway settings."""
    tid = uuid.UUID(tenant_id)
    allowed = {k: v for k, v in body.items() if k in PAYMENT_KEYS}
    # Don't overwrite secrets with masked placeholder
    for secret_key in ("paymongo_secret_key", "paymongo_webhook_secret"):
        if allowed.get(secret_key) == "********":
            del allowed[secret_key]
    for key, value in allowed.items():
        await save_setting(db, key, str(value), tenant_id=tid)
    await db.flush()
    return {"status": "saved", "keys_updated": list(allowed.keys())}


@router.post("/payments/test")
async def test_payments(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Test PayMongo API connection with the provided secret key."""
    from app.services.paymongo import test_connection
    secret_key = body.get("secret_key", "")
    if not secret_key:
        raise HTTPException(status_code=400, detail="secret_key required")
    success = await test_connection(secret_key)
    return {"success": success}


@router.post("/branding/logo")
async def upload_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("settings")),
    tenant_id: str = Depends(get_tenant_id),
):
    """Upload company logo image."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "png"
    filename = f"logo-{uuid.uuid4().hex[:8]}.{ext}"
    upload_dir = "/app/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    tid = uuid.UUID(tenant_id)
    url = f"/api/v1/uploads/{filename}"
    await save_setting(db, "company_logo_url", url, tenant_id=tid)
    await db.flush()
    return {"status": "uploaded", "url": url}
