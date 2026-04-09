import asyncio
import base64
import json
import logging
import os
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session, get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

UPLOAD_DIR = "/app/uploads/chat"

ALLOWED_MIME_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

TENANT_SYSTEM_PROMPT = """You are NetLedger Support, an AI assistant for ISP billing software.
You help ISP operators use NetLedger to manage their subscribers, billing, and MikroTik routers.

RULES:
- Only answer questions about NetLedger, ISP billing, and MikroTik
- If asked about anything else, politely say "I can only help with NetLedger-related questions"
- Be concise and helpful
- If the user reports a bug, acknowledge it and say the team has been notified
- When the user attaches an image, describe what you see and help diagnose the issue

TENANT DATA:
{context}

FEATURES:
- Dashboard with real-time router stats (1-second refresh)
- Customer management with MikroTik PPPoE sync
- Plans with bandwidth profiles synced to MikroTik
- Automated billing (invoice generation, reminders, graduated enforcement)
- Customer portal with online payments (GCash/Maya via PayMongo)
- Hotspot with voucher system
- SMS notifications via Semaphore
- Email notifications via SMTP with branded HTML templates
- CSV and PDF export for customers, invoices, payments
- Bulk actions (generate invoices, send reminders, change status, mark paid, delete)
- Settings: Billing, Payments (PayMongo), SMTP, SMS, Branding, Notifications, Hotspot
- Dark mode toggle"""

PUBLIC_SYSTEM_PROMPT = """You are NetLedger Support, an AI assistant for NetLedger ISP billing software by 2max Tech.
You help answer questions about NetLedger features, pricing, and how to get started.

RULES:
- Only answer questions about NetLedger
- If asked about anything else, politely decline
- Be concise and friendly
- Encourage visitors to sign up (free during beta) or try the demo

KEY INFO:
- NetLedger is free during beta -- no restrictions, unlimited subscribers and routers
- Two deployment options: Cloud (SaaS) at netl.2max.tech, or Self-Hosted (Docker on your own server)
- Supports MikroTik routers (PPPoE and Hotspot)
- Self-hosted works on x86 and ARM64 (Raspberry Pi 4/5)
- Features: automated billing, customer portal, GCash/Maya payments, SMS/email notifications, CSV/PDF export, real-time dashboard, dark mode
- Sign up at netl.2max.tech/register
- Try the demo: click "Try Demo" on the landing page
- Support: Built-in AI chat (that's you!), or email support@2max.tech"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _api_available() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def _get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


async def _optional_user(request: Request, db: AsyncSession) -> User | None:
    """Try to extract a user from the Authorization header. Returns None on failure."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            return None
        return user
    except Exception:
        return None


async def _build_tenant_context(db: AsyncSession, owner_id: uuid.UUID) -> str:
    """Build tenant context string. Uses chat_context module if available, otherwise returns minimal info."""
    try:
        from app.services.chat_context import build_tenant_context
        return await build_tenant_context(db, owner_id)
    except ImportError:
        # chat_context module not yet created -- return empty context
        return "(tenant context not available)"


def _load_image_base64(filename: str) -> tuple[str, str] | None:
    """Load an uploaded image and return (base64_data, media_type) or None."""
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(filepath):
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    media_type_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
    media_type = media_type_map.get(ext)
    if media_type is None:
        return None
    with open(filepath, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("ascii")
    return data, media_type


# ---------------------------------------------------------------------------
# Bug / feature-request auto-detection (fire-and-forget after main reply)
# ---------------------------------------------------------------------------

async def _classify_and_save(
    message: str,
    history: list[dict],
    reply: str,
    images: list[str],
    user_id: uuid.UUID,
    owner_id: uuid.UUID,
    tenant_name: str | None,
    tenant_email: str | None,
) -> None:
    """Classify the user message and, if it's a bug or feature request, persist a SupportTicket and notify the super admin."""
    try:
        client = _get_client()
        classify_response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            temperature=0,
            system="Classify the user's message. Reply with ONLY one word: bug, feature_request, or question. If unsure, reply question.",
            messages=[{"role": "user", "content": message}],
        )
        classification = classify_response.content[0].text.strip().lower()

        if classification not in ("bug", "feature_request"):
            return

        from app.models.support_ticket import SupportTicket

        async with async_session() as db:
            ticket = SupportTicket(
                subject=message[:500],
                description=message,
                category=classification,
                tenant_name=tenant_name,
                tenant_email=tenant_email,
                chat_history=json.dumps(
                    history
                    + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": reply},
                    ]
                ),
                image_urls=",".join(images) if images else None,
                owner_id=owner_id,
            )
            db.add(ticket)
            await db.flush()

            # Notify super admin (email + telegram)
            await _notify_super_admin(db, ticket)
            await _notify_telegram(ticket)
            await db.commit()

        logger.info("Support ticket saved (%s) from %s", classification, tenant_email)
    except Exception as e:
        logger.warning("Bug classification/save failed: %s", e)


async def _notify_super_admin(db: AsyncSession, ticket) -> None:
    """Send email notification to super admin about a new support ticket."""
    try:
        result = await db.execute(
            select(User).where(User.role == UserRole.super_admin).limit(1)
        )
        admin = result.scalar_one_or_none()
        if not admin or not admin.email:
            return

        subject = f"[NetLedger] New {ticket.category}: {ticket.subject[:100]}"
        body = f"""New support ticket from {ticket.tenant_name} ({ticket.tenant_email}):

Category: {ticket.category}
Message: {ticket.description}

Tenant: {ticket.tenant_name}
Email: {ticket.tenant_email}

View in admin panel: {settings.BASE_URL}/system/support
"""
        smtp_host = settings.SMTP_HOST or "mail.2max.tech"
        smtp_port = settings.SMTP_PORT or 587
        smtp_user = settings.SMTP_USER or "noreply@2max.tech"
        smtp_password = settings.SMTP_PASSWORD

        if smtp_host and smtp_user:
            msg = MIMEMultipart()
            msg["From"] = f"NetLedger Support <{smtp_user}>"
            msg["To"] = admin.email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                server.ehlo()
                if smtp_port != 465:
                    server.starttls()
                if smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, [admin.email], msg.as_string())

            logger.info("Super admin notified about support ticket: %s", ticket.subject[:60])
    except Exception as e:
        logger.warning("Failed to notify super admin: %s", e)


async def _notify_telegram(ticket) -> None:
    """Send Telegram notification for new support tickets."""
    bot_token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not bot_token or not chat_id:
        return
    try:
        import httpx
        category_emoji = "🐛" if ticket.category == "bug" else "💡"
        text = (
            f"{category_emoji} *New {ticket.category.replace('_', ' ').title()}*\n\n"
            f"*From:* {ticket.tenant_name}\n"
            f"*Email:* {ticket.tenant_email}\n\n"
            f"*Message:* {ticket.description[:500]}\n\n"
            f"[View in Admin]({settings.BASE_URL}/system/support)"
        )
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10,
            )
        logger.info("Telegram notification sent for ticket: %s", ticket.subject[:60])
    except Exception as e:
        logger.warning("Telegram notification failed: %s", e)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    images: list[str] = []


class ChatResponse(BaseModel):
    response: str


class ChatStatusResponse(BaseModel):
    available: bool


class UploadResponse(BaseModel):
    id: str
    url: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=ChatStatusResponse)
async def chat_status():
    """Check if AI chat is available (API key configured)."""
    if not _api_available():
        raise HTTPException(status_code=404, detail="Chat not available")
    return ChatStatusResponse(available=True)


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Send a message to the AI assistant. Works both authenticated and public."""
    if not _api_available():
        raise HTTPException(status_code=404, detail="Chat not available")

    # Optional auth
    user = await _optional_user(request, db)

    # Build system prompt
    if user is not None:
        owner_id = user.owner_id or user.id  # admin owns themselves, staff has owner_id
        context = await _build_tenant_context(db, owner_id)
        system_prompt = TENANT_SYSTEM_PROMPT.format(context=context)
    else:
        system_prompt = PUBLIC_SYSTEM_PROMPT

    # Build messages array from history + current message
    messages: list[dict] = []
    for entry in body.history:
        role = entry.get("role")
        content = entry.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Build current user message content blocks
    content_blocks: list[dict] = []

    # Add images if any
    for image_id in body.images:
        result = _load_image_base64(image_id)
        if result is not None:
            b64_data, media_type = result
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64_data,
                },
            })

    text = body.message.strip() or ("Please describe what you see in the image." if body.images else "Hi")
    content_blocks.append({"type": "text", "text": text})
    messages.append({"role": "user", "content": content_blocks})

    # Call Claude
    try:
        client = _get_client()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            temperature=0.3,
            system=system_prompt,
            messages=messages,
        )
        reply = response.content[0].text
    except anthropic.APIStatusError as e:
        logger.error("Anthropic API error: %s", e)
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable")
    except Exception as e:
        logger.error("Unexpected error calling Claude: %s", e)
        raise HTTPException(status_code=502, detail="AI service temporarily unavailable")

    # Fire-and-forget: classify message and save support ticket if it's a bug/feature request
    if user is not None:
        asyncio.create_task(
            _classify_and_save(
                message=body.message,
                history=body.history,
                reply=reply,
                images=body.images,
                user_id=user.id,
                owner_id=user.owner_id or user.id,
                tenant_name=user.company_name or user.full_name,
                tenant_email=user.email,
            )
        )

    return ChatResponse(response=reply)


@router.post("/upload", response_model=UploadResponse)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image for use in chat. Requires authentication."""
    if not _api_available():
        raise HTTPException(status_code=404, detail="Chat not available")

    # Require auth for uploads
    user = await _optional_user(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required for uploads")

    # Validate content type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, and WEBP images are allowed")

    # Read and validate size
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    # Save
    ext = ALLOWED_MIME_TYPES[file.content_type]
    filename = f"{uuid.uuid4()}.{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(data)

    return UploadResponse(
        id=filename,
        url=f"/api/v1/uploads/chat/{filename}",
    )
