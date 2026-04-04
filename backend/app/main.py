import app.models  # noqa: F401 — ensures all models are registered in SQLAlchemy mapper
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.customers import router as customers_router
from app.api.admin.plans import router as plans_router
from app.api.admin.billing import router as billing_router
from app.api.admin.pppoe import router as pppoe_router
from app.api.admin.network import router as network_router
from app.api.admin.security import router as security_router
from app.api.portal import router as portal_router
from app.api.admin.users import router as users_router
from app.api.auth import router as auth_router
from app.api.websocket import router as ws_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_PREFIX}/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(plans_router, prefix=settings.API_V1_PREFIX)
app.include_router(customers_router, prefix=settings.API_V1_PREFIX)
app.include_router(users_router, prefix=settings.API_V1_PREFIX)
app.include_router(pppoe_router, prefix=settings.API_V1_PREFIX)
app.include_router(network_router, prefix=settings.API_V1_PREFIX)
app.include_router(billing_router, prefix=settings.API_V1_PREFIX)
app.include_router(portal_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router, prefix=settings.API_V1_PREFIX)
app.include_router(security_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}
