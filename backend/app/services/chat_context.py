"""Build tenant context summary for AI chat system prompt."""

import uuid

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.app_setting import AppSetting
from app.models.customer import Customer, CustomerStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.router import Router


async def build_tenant_context(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Build a text summary of tenant's current state for the AI system prompt.

    Returns a concise multi-line string with customer counts, router status,
    invoice summaries, integration configuration, and recent activity.
    """
    lines: list[str] = []

    # --- Customer counts by status ---
    result = await db.execute(
        select(Customer.status, func.count(Customer.id))
        .where(Customer.owner_id == tenant_id)
        .group_by(Customer.status)
    )
    status_counts: dict[str, int] = {row[0].value: row[1] for row in result}
    total = sum(status_counts.values())
    lines.append(
        f"Customers: {total} total"
        f" ({status_counts.get('active', 0)} active,"
        f" {status_counts.get('suspended', 0)} suspended,"
        f" {status_counts.get('disconnected', 0)} disconnected,"
        f" {status_counts.get('terminated', 0)} terminated)"
    )

    # --- Routers ---
    result = await db.execute(
        select(Router.name, Router.is_active, Router.maintenance_mode)
        .where(Router.owner_id == tenant_id)
    )
    routers = result.all()
    if routers:
        lines.append(f"Routers ({len(routers)}):")
        for r in routers:
            if r.maintenance_mode:
                state = "maintenance"
            elif r.is_active:
                state = "active"
            else:
                state = "inactive"
            lines.append(f"  - {r.name}: {state}")
    else:
        lines.append("Routers: none configured")

    # --- Overdue invoices ---
    result = await db.execute(
        select(func.count(Invoice.id), func.coalesce(func.sum(Invoice.amount), 0))
        .where(and_(Invoice.owner_id == tenant_id, Invoice.status == InvoiceStatus.overdue))
    )
    row = result.one()
    lines.append(f"Overdue invoices: {row[0]} (total: ₱{float(row[1]):,.2f})")

    # --- Pending invoices ---
    result = await db.execute(
        select(func.count(Invoice.id))
        .where(and_(Invoice.owner_id == tenant_id, Invoice.status == InvoiceStatus.pending))
    )
    pending = result.scalar_one()
    lines.append(f"Pending invoices: {pending}")

    # --- Integration / settings status ---
    result = await db.execute(
        select(AppSetting.key, AppSetting.value)
        .where(AppSetting.owner_id == tenant_id)
    )
    settings = {r.key: r.value for r in result.all()}

    smtp_configured = bool(settings.get("smtp_host"))
    sms_configured = bool(settings.get("sms_api_key"))
    paymongo_configured = bool(settings.get("paymongo_secret_key"))
    billing_configured = bool(settings.get("billing_default_due_day"))

    lines.append(f"Email (SMTP): {'configured' if smtp_configured else 'not configured'}")
    lines.append(f"SMS (Semaphore): {'configured' if sms_configured else 'not configured'}")
    lines.append(f"Online payments (PayMongo): {'configured' if paymongo_configured else 'not configured'}")
    lines.append(f"Billing: {'configured' if billing_configured else 'not configured'}")

    # --- Recent audit log entries ---
    try:
        result = await db.execute(
            select(AuditLog.action, AuditLog.entity_type, AuditLog.details, AuditLog.created_at)
            .where(AuditLog.owner_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
        logs = result.all()
        if logs:
            lines.append("Recent activity (last 10):")
            for log in logs:
                detail = f": {log.details}" if log.details else ""
                lines.append(
                    f"  - {log.action} {log.entity_type}{detail}"
                    f" ({log.created_at.strftime('%Y-%m-%d %H:%M')})"
                )
    except Exception:
        pass  # audit_logs table may not exist on older installs

    return "\n".join(lines)
