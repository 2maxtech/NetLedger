from fastapi import APIRouter, Depends

from agent.core.security import verify_api_key
from agent.services import nftables

router = APIRouter(prefix="/agent/firewall", tags=["firewall"], dependencies=[Depends(verify_api_key)])


@router.get("/ruleset")
async def get_ruleset():
    return await nftables.get_ruleset()


@router.get("/tables")
async def get_tables():
    return await nftables.get_tables()


@router.get("/chain/{table}/{chain}")
async def get_chain(table: str, chain: str, family: str = "inet"):
    return await nftables.get_chain_rules(table, chain, family)


@router.post("/rule")
async def add_rule(body: dict):
    return {"result": await nftables.add_rule(
        body["table"], body["chain"], body["rule"], body.get("family", "inet")
    )}


@router.delete("/rule")
async def delete_rule(body: dict):
    return {"result": await nftables.delete_rule(
        body["table"], body["chain"], body["handle"], body.get("family", "inet")
    )}


@router.post("/apply")
async def apply_ruleset(body: dict):
    return {"result": await nftables.apply_ruleset(body["ruleset"])}


@router.post("/flush")
async def flush_chain(body: dict):
    return {"result": await nftables.flush_chain(
        body["table"], body["chain"], body.get("family", "inet")
    )}


@router.post("/table")
async def create_table(body: dict):
    return {"result": await nftables.create_table(body["name"], body.get("family", "inet"))}


@router.post("/chain")
async def create_chain(body: dict):
    return {"result": await nftables.create_chain(
        body["table"], body["name"],
        body.get("type", "filter"), body.get("hook", "input"),
        body.get("priority", 0), body.get("policy", "accept"),
        body.get("family", "inet"),
    )}
