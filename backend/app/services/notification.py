import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.app_setting import AppSetting
from app.models.customer import Customer
from app.models.notification import Notification, NotificationStatus, NotificationType

logger = logging.getLogger(__name__)

# Jinja2 environment for email templates
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)


async def _get_tenant_smtp(db: AsyncSession, tenant_id) -> dict:
    """Get SMTP settings for a tenant, falling back to global config."""
    if tenant_id:
        result = await db.execute(
            select(AppSetting).where(AppSetting.key.like("smtp_%"), AppSetting.owner_id == tenant_id)
        )
        tenant_smtp = {s.key: s.value for s in result.scalars().all()}
        if tenant_smtp.get("smtp_host"):
            return tenant_smtp
    # Fall back to global env settings
    return {
        "smtp_host": settings.SMTP_HOST,
        "smtp_port": str(settings.SMTP_PORT),
        "smtp_user": settings.SMTP_USER,
        "smtp_password": settings.SMTP_PASSWORD,
        "smtp_from": settings.SMTP_FROM,
        "smtp_from_name": getattr(settings, "SMTP_FROM_NAME", "NetLedger"),
    }


async def _get_tenant_branding(db: AsyncSession, tenant_id) -> dict:
    """Get branding settings for a tenant (company_name, logo_url, primary_color)."""
    branding_keys = ["company_name", "company_logo_url", "primary_color"]
    if tenant_id:
        result = await db.execute(
            select(AppSetting).where(
                AppSetting.key.in_(branding_keys),
                AppSetting.owner_id == tenant_id,
            )
        )
        return {s.key: s.value for s in result.scalars().all()}
    return {}


def _detect_email_category(subject: str) -> str:
    """Detect email category from subject line for HTML template selection.
    Returns: 'invoice', 'reminder', 'overdue', or 'generic'."""
    subj_lower = subject.lower()
    if "overdue" in subj_lower:
        return "overdue"
    if "reminder" in subj_lower:
        return "reminder"
    if "invoice" in subj_lower:
        return "invoice"
    return "generic"


def _extract_template_vars_from_text(plain_text: str, customer_name: str) -> dict:
    """Extract template variables from the rendered plain text message.
    This parses values like amounts and dates from the already-rendered notification text."""
    import re
    vars = {"customer_name": customer_name}

    # Extract amount (e.g. "₱1,500.00" or "₱500")
    amount_match = re.search(r"₱[\d,]+(?:\.\d{2})?", plain_text)
    if amount_match:
        vars["amount"] = amount_match.group(0)

    # Extract due date patterns - try full format first (e.g. "January 15, 2026")
    date_match = re.search(
        r"(?:due (?:on |date: ?)?)(\w+ \d{1,2},? \d{4})",
        plain_text, re.IGNORECASE,
    )
    if date_match:
        vars["due_date"] = date_match.group(1)
    else:
        # Try shorter pattern (e.g. "Jan 15")
        short_match = re.search(r"due (?:on )?(\w{3} \d{1,2})", plain_text, re.IGNORECASE)
        if short_match:
            vars["due_date"] = short_match.group(1)

    # Extract plan name from "for plan <name>" or "for <plan_name>"
    plan_match = re.search(r"(?:for (?:plan )?)([\w\s]+?)(?:\s+has been|\s+is (?:due|now)|\.|,)", plain_text, re.IGNORECASE)
    if plan_match:
        vars["plan_name"] = plan_match.group(1).strip()

    return vars


async def _get_portal_url(db: AsyncSession, tenant_id) -> str:
    """Get the customer portal URL for a tenant."""
    if not tenant_id:
        return ""
    result = await db.execute(
        select(AppSetting).where(
            AppSetting.key == "portal_slug",
            AppSetting.owner_id == tenant_id,
        )
    )
    slug_setting = result.scalar_one_or_none()
    if slug_setting and slug_setting.value:
        return f"{settings.BASE_URL}/portal/{slug_setting.value}"
    return ""


def render_html_email(
    category: str,
    subject: str,
    template_vars: dict,
    branding: dict,
    portal_url: str = "",
    primary_color: str = "#e8700a",
) -> str:
    """Render a branded HTML email by combining a content template with the base layout.

    Args:
        category: 'invoice', 'reminder', 'overdue', or 'generic'
        subject: Email subject line
        template_vars: Variables for the content template (customer_name, amount, etc.)
        branding: Tenant branding settings dict
        portal_url: Optional customer portal URL
        primary_color: Brand color for buttons/header
    """
    company_name = branding.get("company_name", "NetLedger")
    logo_url = branding.get("company_logo_url", "")
    color = branding.get("primary_color", primary_color)

    # If logo is a relative /api/v1/uploads/ path, make it absolute
    if logo_url and logo_url.startswith("/"):
        logo_url = f"{settings.BASE_URL}{logo_url}"

    # Prepare content template variables
    content_vars = dict(template_vars)
    content_vars["portal_url"] = portal_url
    content_vars["primary_color"] = color

    # Render content from category-specific template
    template_map = {
        "invoice": "email_invoice.html",
        "reminder": "email_reminder.html",
        "overdue": "email_overdue.html",
    }

    if category in template_map:
        try:
            content_tpl = _jinja_env.get_template(template_map[category])
            content_html = content_tpl.render(**content_vars)
        except Exception as e:
            logger.warning(f"Failed to render {category} content template: {e}")
            # Fallback: convert plain text to HTML paragraphs
            content_html = _plain_text_to_html(template_vars.get("_plain_text", ""))
    else:
        # Generic: convert plain text body to simple HTML
        content_html = _plain_text_to_html(template_vars.get("_plain_text", ""))

    # Render base template with branded header/footer
    base_tpl = _jinja_env.get_template("email_base.html")
    return base_tpl.render(
        subject=subject,
        content=content_html,
        company_name=company_name,
        logo_url=logo_url,
        primary_color=color,
    )


def _plain_text_to_html(text: str) -> str:
    """Convert plain text to simple HTML paragraphs for the generic email fallback."""
    if not text:
        return ""
    import html
    escaped = html.escape(text)
    paragraphs = escaped.split("\n\n")
    html_parts = []
    for p in paragraphs:
        lines = p.strip().replace("\n", "<br>")
        if lines:
            html_parts.append(
                f'<p style="color:#374151;font-size:14px;line-height:1.6;margin:0 0 16px;">{lines}</p>'
            )
    return "\n".join(html_parts)


async def send_email_tenant(db: AsyncSession, tenant_id, to: str, subject: str, body: str, html: str | None = None, pdf_bytes: bytes | None = None, pdf_name: str | None = None) -> bool:
    """Send email using tenant's SMTP settings.
    When both body (plain text) and html are provided, sends multipart/alternative."""
    smtp_cfg = await _get_tenant_smtp(db, tenant_id)
    host = smtp_cfg.get("smtp_host", "")
    if not host:
        logger.warning("SMTP not configured, skipping email send")
        return False

    port = int(smtp_cfg.get("smtp_port", 587))
    user = smtp_cfg.get("smtp_user", "")
    password = smtp_cfg.get("smtp_password", "")
    from_addr = smtp_cfg.get("smtp_from", user)
    from_name = smtp_cfg.get("smtp_from_name", "NetLedger")

    try:
        if html and pdf_bytes:
            # HTML + attachment: mixed outer, alternative inner
            msg = MIMEMultipart("mixed")
            msg["From"] = f"{from_name} <{from_addr}>"
            msg["To"] = to
            msg["Subject"] = subject

            alt_part = MIMEMultipart("alternative")
            alt_part.attach(MIMEText(body, "plain"))
            alt_part.attach(MIMEText(html, "html"))
            msg.attach(alt_part)

            pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_part.add_header("Content-Disposition", "attachment", filename=pdf_name)
            msg.attach(pdf_part)
        elif html:
            # HTML + plain text fallback, no attachment
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{from_name} <{from_addr}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            msg.attach(MIMEText(html, "html"))
        elif pdf_bytes and pdf_name:
            # Plain text + attachment
            msg = MIMEMultipart()
            msg["From"] = f"{from_name} <{from_addr}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_part.add_header("Content-Disposition", "attachment", filename=pdf_name)
            msg.attach(pdf_part)
        else:
            # Plain text only
            msg = MIMEMultipart()
            msg["From"] = f"{from_name} <{from_addr}>"
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            if port != 465:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.sendmail(from_addr, [to], msg.as_string())

        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        return False


async def send_email(to: str, subject: str, body: str) -> bool:
    """Legacy: Send email via global SMTP config."""
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        logger.warning("SMTP not configured, skipping email send")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        return False


async def process_pending_notifications(db: AsyncSession) -> dict:
    """Process all pending notifications — send emails and SMS.
    Email notifications are rendered with branded HTML templates."""
    from app.services.sms import send_sms

    result = await db.execute(
        select(Notification).where(Notification.status == NotificationStatus.pending).limit(50)
    )
    notifications = result.scalars().all()

    sent = 0
    failed = 0
    skipped = 0

    # Cache branding per tenant to avoid repeated DB queries
    _branding_cache: dict = {}
    _portal_cache: dict = {}

    for notif in notifications:
        cust_result = await db.execute(
            select(Customer).where(Customer.id == notif.customer_id)
        )
        customer = cust_result.scalar_one_or_none()

        if not customer:
            notif.status = NotificationStatus.failed
            failed += 1
            continue

        if notif.type == NotificationType.sms:
            if not customer.phone or customer.phone == "0000000000":
                notif.status = NotificationStatus.failed
                failed += 1
                continue
            success = await send_sms(customer.phone, notif.message, db, tenant_id=notif.owner_id)
        elif notif.type == NotificationType.email:
            if not customer.email or customer.email.endswith("@imported.local"):
                notif.status = NotificationStatus.failed
                failed += 1
                continue

            # Render branded HTML version of the email
            html_body = None
            try:
                tid_key = str(notif.owner_id) if notif.owner_id else "_global"

                # Fetch and cache branding
                if tid_key not in _branding_cache:
                    _branding_cache[tid_key] = await _get_tenant_branding(db, notif.owner_id)
                branding = _branding_cache[tid_key]

                # Fetch and cache portal URL
                if tid_key not in _portal_cache:
                    _portal_cache[tid_key] = await _get_portal_url(db, notif.owner_id)
                portal_url = _portal_cache[tid_key]

                # Detect email category and extract template vars
                category = _detect_email_category(notif.subject)
                tpl_vars = _extract_template_vars_from_text(notif.message, customer.full_name)
                tpl_vars["_plain_text"] = notif.message

                html_body = render_html_email(
                    category=category,
                    subject=notif.subject,
                    template_vars=tpl_vars,
                    branding=branding,
                    portal_url=portal_url,
                )
            except Exception as e:
                logger.warning(f"HTML email render failed for notification {notif.id}, sending plain text: {e}")
                html_body = None

            success = await send_email_tenant(
                db, notif.owner_id, customer.email, notif.subject, notif.message, html=html_body
            )
        else:
            skipped += 1
            continue

        if success:
            notif.status = NotificationStatus.sent
            notif.sent_at = datetime.now(timezone.utc)
            sent += 1
        else:
            notif.status = NotificationStatus.failed
            failed += 1

    await db.flush()
    return {"sent": sent, "failed": failed, "skipped": skipped}
