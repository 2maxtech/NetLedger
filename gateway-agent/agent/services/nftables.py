import asyncio
import json
import logging

logger = logging.getLogger(__name__)


async def _run_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{stderr.decode()}")
    return stdout.decode()


async def get_ruleset() -> dict:
    """Get current nftables ruleset as JSON."""
    output = await _run_cmd("nft -j list ruleset")
    return json.loads(output)


async def get_tables() -> list:
    """List all nftables tables."""
    output = await _run_cmd("nft -j list tables")
    data = json.loads(output)
    return data.get("nftables", [])


async def add_rule(table: str, chain: str, rule: str, family: str = "inet") -> str:
    """Add a rule to a chain."""
    cmd = f'nft add rule {family} {table} {chain} {rule}'
    return await _run_cmd(cmd)


async def delete_rule(table: str, chain: str, handle: int, family: str = "inet") -> str:
    """Delete a rule by handle."""
    cmd = f'nft delete rule {family} {table} {chain} handle {handle}'
    return await _run_cmd(cmd)


async def get_chain_rules(table: str, chain: str, family: str = "inet") -> dict:
    """Get rules for a specific chain."""
    output = await _run_cmd(f"nft -j list chain {family} {table} {chain}")
    return json.loads(output)


async def apply_ruleset(ruleset: str) -> str:
    """Apply a complete nftables ruleset from string."""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(mode='w', suffix='.nft', delete=False) as f:
        f.write(ruleset)
        tmp_path = f.name
    try:
        return await _run_cmd(f"nft -f {tmp_path}")
    finally:
        os.unlink(tmp_path)


async def flush_chain(table: str, chain: str, family: str = "inet") -> str:
    """Flush all rules in a chain."""
    return await _run_cmd(f"nft flush chain {family} {table} {chain}")


async def create_table(name: str, family: str = "inet") -> str:
    """Create a new table."""
    return await _run_cmd(f"nft add table {family} {name}")


async def create_chain(
    table: str,
    name: str,
    chain_type: str = "filter",
    hook: str = "input",
    priority: int = 0,
    policy: str = "accept",
    family: str = "inet",
) -> str:
    """Create a new chain."""
    return await _run_cmd(
        f'nft add chain {family} {table} {name} {{ type {chain_type} hook {hook} priority {priority}\\; policy {policy}\\; }}'
    )
