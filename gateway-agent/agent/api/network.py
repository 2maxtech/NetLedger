from fastapi import APIRouter, Depends

from agent.core.security import verify_api_key
from agent.services import network

router = APIRouter(prefix="/agent/network", tags=["network"], dependencies=[Depends(verify_api_key)])


@router.get("/interfaces")
async def get_interfaces():
    return await network.get_interfaces()


@router.get("/routes")
async def get_routes():
    return await network.get_routes()


@router.post("/route")
async def add_route(body: dict):
    return {"result": await network.add_route(
        body["destination"], body["gateway"], body.get("interface")
    )}


@router.delete("/route")
async def delete_route(body: dict):
    return {"result": await network.delete_route(body["destination"])}


@router.post("/interface")
async def configure_interface(body: dict):
    return {"result": await network.configure_interface(
        body["name"], body.get("address"), body.get("state")
    )}


@router.get("/nat")
async def get_nat():
    return await network.get_nat_rules()


@router.post("/nat/masquerade")
async def add_masquerade(body: dict):
    return {"result": await network.add_nat_masquerade(body["out_interface"])}


@router.post("/nat/port-forward")
async def add_port_forward(body: dict):
    return {"result": await network.add_port_forward(
        body["protocol"], body["dport"], body["dest_ip"], body["dest_port"],
        body.get("in_interface"),
    )}
