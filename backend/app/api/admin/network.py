from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.mikrotik import mikrotik

router = APIRouter(prefix="/network", tags=["network"])


@router.get("/active-sessions")
async def get_active_sessions(current_user: User = Depends(get_current_user)):
    """Get active PPPoE sessions from MikroTik."""
    try:
        sessions = await mikrotik.get_active_sessions()
        return {"sessions": sessions, "total": len(sessions)}
    except Exception as e:
        return {"sessions": [], "total": 0, "error": str(e)}


@router.get("/status")
async def get_network_status(current_user: User = Depends(get_current_user)):
    """Check MikroTik connectivity."""
    try:
        identity = await mikrotik.get_identity()
        resources = await mikrotik.get_resources()
        return {
            "connected": True,
            "identity": identity,
            "uptime": resources.get("uptime", ""),
            "cpu_load": resources.get("cpu-load", ""),
            "free_memory": resources.get("free-memory", ""),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.get("/subscribers")
async def get_subscribers(current_user: User = Depends(get_current_user)):
    """List PPPoE secrets from MikroTik."""
    try:
        secrets = await mikrotik.get_secrets()
        return {"subscribers": secrets, "total": len(secrets)}
    except Exception as e:
        return {"subscribers": [], "total": 0, "error": str(e)}
