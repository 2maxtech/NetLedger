import asyncio
import logging
from datetime import date, datetime, timezone

from app.celery_app import celery

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


@celery.task(name="app.tasks.bandwidth.collect_bandwidth_task")
def collect_bandwidth_task():
    """Collect bandwidth usage from all active routers. Runs every 15 minutes."""
    _run_async(_collect_bandwidth())


async def _collect_bandwidth():
    from app.core.database import async_session
    from app.models.router import Router
    from app.models.customer import Customer
    from app.models.bandwidth_usage import BandwidthUsage
    from app.services.mikrotik import get_mikrotik_client
    from sqlalchemy import select

    async with async_session() as db:
        try:
            result = await db.execute(select(Router).where(Router.is_active == True))
            routers = result.scalars().all()
            total = 0
            today = date.today()

            for router in routers:
                try:
                    client = get_mikrotik_client(
                        str(router.id), router.url, router.username, router.password
                    )
                    sessions = await client.get_active_sessions()

                    # Build lookup of customers by PPPoE username
                    cust_result = await db.execute(
                        select(Customer).where(Customer.router_id == router.id)
                    )
                    customers = {c.pppoe_username: c for c in cust_result.scalars().all()}

                    for s in sessions:
                        username = s.get("name", "")
                        cust = customers.get(username)
                        if not cust:
                            continue

                        bytes_in = int(s.get("bytes-in", 0) or 0)
                        bytes_out = int(s.get("bytes-out", 0) or 0)

                        # Upsert: update if record exists for today, else create
                        existing = await db.execute(
                            select(BandwidthUsage).where(
                                BandwidthUsage.customer_id == cust.id,
                                BandwidthUsage.date == today,
                            )
                        )
                        usage = existing.scalar_one_or_none()

                        if usage:
                            usage.total_bytes_in = max(usage.total_bytes_in, bytes_in)
                            usage.total_bytes_out = max(usage.total_bytes_out, bytes_out)
                        else:
                            usage = BandwidthUsage(
                                customer_id=cust.id,
                                date=today,
                                total_bytes_in=bytes_in,
                                total_bytes_out=bytes_out,
                                peak_download_mbps=0,
                                peak_upload_mbps=0,
                            )
                            db.add(usage)
                        total += 1

                except Exception as e:
                    logger.warning(f"Bandwidth collect failed for {router.name}: {e}")

            await db.commit()
            logger.info(f"Bandwidth: {total} records from {len(routers)} routers")
        except Exception:
            await db.rollback()
            raise


@celery.task(name="app.tasks.bandwidth.check_data_caps_task")
def check_data_caps_task():
    """Check data caps and throttle customers who exceed them. Runs every 2 hours."""
    _run_async(_check_data_caps())


async def _check_data_caps():
    from app.core.database import async_session
    from app.models.customer import Customer, CustomerStatus
    from app.models.plan import Plan
    from app.models.bandwidth_usage import BandwidthUsage
    from app.models.disconnect_log import DisconnectLog, DisconnectAction, DisconnectReason
    from app.models.router import Router
    from app.services.mikrotik import get_mikrotik_client
    from app.core.config import settings
    from sqlalchemy import select, func

    async with async_session() as db:
        try:
            result = await db.execute(
                select(Customer, Plan).join(Plan).where(
                    Customer.status == CustomerStatus.active,
                    Plan.data_cap_gb.isnot(None),
                    Plan.data_cap_gb > 0,
                )
            )

            first_of_month = date.today().replace(day=1)
            throttled = 0

            for customer, plan in result.all():
                usage_result = await db.execute(
                    select(
                        func.sum(BandwidthUsage.total_bytes_in + BandwidthUsage.total_bytes_out)
                    ).where(
                        BandwidthUsage.customer_id == customer.id,
                        BandwidthUsage.date >= first_of_month,
                    )
                )
                total_bytes = usage_result.scalar() or 0
                total_gb = total_bytes / (1024 ** 3)

                if total_gb >= plan.data_cap_gb:
                    router_result = await db.execute(
                        select(Router).where(Router.id == customer.router_id)
                    )
                    router = router_result.scalar_one_or_none()
                    if router:
                        try:
                            client = get_mikrotik_client(
                                str(router.id), router.url, router.username, router.password
                            )
                            throttle_name = f"{settings.THROTTLE_DOWNLOAD_MBPS}M-throttle"
                            rate = f"{settings.THROTTLE_UPLOAD_KBPS}k/{settings.THROTTLE_DOWNLOAD_MBPS}M"
                            await client.ensure_profile(throttle_name, rate)

                            # Find the secret by username and update its profile
                            secrets = await client.get_secrets()
                            for secret in secrets:
                                if secret.get("name") == customer.pppoe_username:
                                    await client.update_secret(
                                        secret[".id"], {"profile": throttle_name}
                                    )
                                    break

                            try:
                                await client.disable_user_queues(customer.pppoe_username)
                            except Exception as qe:
                                logger.warning(
                                    f"Disable shadow queues failed for {customer.pppoe_username}: {qe}"
                                )
                            await client.kick_session(customer.pppoe_username)
                            customer.status = CustomerStatus.suspended

                            db.add(DisconnectLog(
                                customer_id=customer.id,
                                action=DisconnectAction.throttle,
                                reason=DisconnectReason.expired,
                                performed_at=datetime.now(timezone.utc),
                                owner_id=customer.owner_id,
                            ))
                            throttled += 1
                        except Exception as e:
                            logger.warning(
                                f"Data cap throttle failed for {customer.pppoe_username}: {e}"
                            )

            await db.commit()
            logger.info(f"Data cap check: {throttled} throttled")
        except Exception:
            await db.rollback()
            raise
