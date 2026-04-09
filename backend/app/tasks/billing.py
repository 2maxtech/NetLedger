import asyncio
import logging

from app.celery_app import celery
from app.core.config import settings

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.run(coro)


def _get_celery_session():
    """Create a fresh async engine + session for Celery tasks (avoids shared pool conflicts)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=2, max_overflow=0)
    session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return session, engine


@celery.task(name="app.tasks.billing.generate_monthly_invoices_task")
def generate_monthly_invoices_task():
    """Generate monthly invoices for all active customers. Runs on 1st of month."""
    from app.services.billing import generate_monthly_invoices

    async def _run():
        session, engine = _get_celery_session()
        try:
            async with session() as db:
                try:
                    result = await generate_monthly_invoices(db)
                    await db.commit()
                    logger.info(f"Monthly invoices: generated={result['generated']}, skipped={result['skipped']}")
                    return result
                except Exception:
                    await db.rollback()
                    raise
        finally:
            await engine.dispose()

    return _run_async(_run())


@celery.task(name="app.tasks.billing.check_overdue_invoices_task")
def check_overdue_invoices_task():
    """Check for overdue invoices and mark them. Runs daily."""
    from app.services.billing import check_overdue_invoices

    async def _run():
        session, engine = _get_celery_session()
        try:
            async with session() as db:
                try:
                    count = await check_overdue_invoices(db)
                    await db.commit()
                    logger.info(f"Overdue invoices marked: {count}")
                    return {"marked_overdue": count}
                except Exception:
                    await db.rollback()
                    raise
        finally:
            await engine.dispose()

    return _run_async(_run())


@celery.task(name="app.tasks.billing.process_graduated_disconnect_task")
def process_graduated_disconnect_task():
    """Process graduated disconnect enforcement. Runs daily."""
    from app.services.billing import process_graduated_disconnect

    async def _run():
        session, engine = _get_celery_session()
        try:
            async with session() as db:
                try:
                    result = await process_graduated_disconnect(db)
                    await db.commit()
                    logger.info(f"Graduated disconnect: {result}")
                    return result
                except Exception:
                    await db.rollback()
                    raise
        finally:
            await engine.dispose()

    return _run_async(_run())


@celery.task(name="app.tasks.billing.send_billing_reminders_task")
def send_billing_reminders_task():
    """Send billing reminders. Runs daily."""
    from app.services.billing import send_billing_reminders

    async def _run():
        session, engine = _get_celery_session()
        try:
            async with session() as db:
                try:
                    count = await send_billing_reminders(db)
                    await db.commit()
                    logger.info(f"Billing reminders sent: {count}")
                    return {"reminders_sent": count}
                except Exception:
                    await db.rollback()
                    raise
        finally:
            await engine.dispose()

    return _run_async(_run())


@celery.task(name="app.tasks.billing.process_notifications_task")
def process_notifications_task():
    """Process and send pending notifications. Runs every 5 minutes."""
    from app.services.notification import process_pending_notifications

    async def _run():
        session, engine = _get_celery_session()
        try:
            async with session() as db:
                try:
                    result = await process_pending_notifications(db)
                    await db.commit()
                    logger.info(f"Notifications processed: {result}")
                    return result
                except Exception:
                    await db.rollback()
                    raise
        finally:
            await engine.dispose()

    return _run_async(_run())
