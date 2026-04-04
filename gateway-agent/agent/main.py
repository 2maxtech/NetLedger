from fastapi import FastAPI

from agent.api.dhcp import router as dhcp_router
from agent.api.firewall import router as firewall_router
from agent.api.network import router as network_router
from agent.api.pppoe import router as pppoe_router
from agent.api.system import router as system_router

app = FastAPI(title="2maXnetBill Gateway Agent")

app.include_router(pppoe_router)
app.include_router(system_router)
app.include_router(firewall_router)
app.include_router(network_router)
app.include_router(dhcp_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway-agent"}
