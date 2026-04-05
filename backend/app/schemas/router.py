import uuid
from datetime import datetime

from pydantic import BaseModel


class RouterCreate(BaseModel):
    name: str
    url: str
    username: str = "admin"
    password: str = ""
    location: str | None = None


class RouterUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    location: str | None = None
    is_active: bool | None = None
    maintenance_mode: bool | None = None
    maintenance_message: str | None = None


class RouterResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    username: str
    location: str | None
    is_active: bool
    created_at: datetime
    maintenance_mode: bool = False
    maintenance_message: str | None = None
    wg_tunnel_ip: str | None = None
    wg_peer_public_key: str | None = None

    model_config = {"from_attributes": True}


class RouterStatusResponse(BaseModel):
    id: uuid.UUID
    name: str
    connected: bool
    identity: str | None = None
    uptime: str | None = None
    cpu_load: str | None = None
    free_memory: int = 0
    total_memory: int = 0
    active_sessions: int = 0
    version: str | None = None
    error: str | None = None


class AreaCreate(BaseModel):
    name: str
    description: str | None = None
    router_id: uuid.UUID | None = None


class AreaUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    router_id: uuid.UUID | None = None


class AreaResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    router_id: uuid.UUID | None
    router: RouterResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
