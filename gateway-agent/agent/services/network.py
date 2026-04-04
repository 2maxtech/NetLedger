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


async def get_interfaces() -> list:
    """Get all network interfaces with IP addresses."""
    output = await _run_cmd("ip -j addr show")
    return json.loads(output)


async def get_routes() -> list:
    """Get routing table."""
    output = await _run_cmd("ip -j route show")
    return json.loads(output)


async def add_route(destination: str, gateway: str, interface: str | None = None) -> str:
    """Add a static route."""
    cmd = f"ip route add {destination} via {gateway}"
    if interface:
        cmd += f" dev {interface}"
    return await _run_cmd(cmd)


async def delete_route(destination: str) -> str:
    """Delete a route."""
    return await _run_cmd(f"ip route del {destination}")


async def configure_interface(name: str, address: str | None = None, state: str | None = None) -> str:
    """Configure a network interface."""
    results = []
    if state:
        results.append(await _run_cmd(f"ip link set {name} {state}"))
    if address:
        # Flush existing addresses first
        await _run_cmd(f"ip addr flush dev {name}")
        results.append(await _run_cmd(f"ip addr add {address} dev {name}"))
    return "\n".join(results)


async def get_nat_rules() -> dict:
    """Get NAT rules from nftables."""
    try:
        output = await _run_cmd("nft -j list chain inet nat postrouting 2>/dev/null || echo '{}'")
        return json.loads(output) if output.strip() != '{}' else {"rules": []}
    except Exception:
        return {"rules": []}


async def add_nat_masquerade(out_interface: str) -> str:
    """Add NAT masquerade for an outbound interface."""
    # Ensure nat table and postrouting chain exist
    await _run_cmd("nft add table inet nat 2>/dev/null || true")
    await _run_cmd("nft add chain inet nat postrouting '{ type nat hook postrouting priority 100; }' 2>/dev/null || true")
    return await _run_cmd(f'nft add rule inet nat postrouting oifname "{out_interface}" masquerade')


async def add_port_forward(
    protocol: str,
    dport: int,
    dest_ip: str,
    dest_port: int,
    in_interface: str | None = None,
) -> str:
    """Add a port forwarding (DNAT) rule."""
    await _run_cmd("nft add table inet nat 2>/dev/null || true")
    await _run_cmd("nft add chain inet nat prerouting '{ type nat hook prerouting priority -100; }' 2>/dev/null || true")

    rule = f"{protocol} dport {dport} dnat to {dest_ip}:{dest_port}"
    if in_interface:
        rule = f'iifname "{in_interface}" ' + rule
    return await _run_cmd(f"nft add rule inet nat prerouting {rule}")
