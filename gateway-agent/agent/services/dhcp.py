import asyncio
import logging

logger = logging.getLogger(__name__)

DNSMASQ_CONF = "/etc/dnsmasq.d/netbill.conf"
DNSMASQ_LEASES = "/var/lib/misc/dnsmasq.leases"


async def _run_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{stderr.decode()}")
    return stdout.decode()


async def get_config() -> str:
    """Get current dnsmasq config."""
    try:
        with open(DNSMASQ_CONF, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return ""


async def apply_config(config: str) -> str:
    """Write dnsmasq config and reload."""
    with open(DNSMASQ_CONF, 'w') as f:
        f.write(config)
    return await _run_cmd("systemctl reload dnsmasq 2>/dev/null || systemctl restart dnsmasq")


async def get_leases() -> list:
    """Get current DHCP leases."""
    try:
        with open(DNSMASQ_LEASES, 'r') as f:
            leases = []
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 4:
                    leases.append({
                        "expires": parts[0],
                        "mac": parts[1],
                        "ip": parts[2],
                        "hostname": parts[3] if len(parts) > 3 else "",
                    })
            return leases
    except FileNotFoundError:
        return []


async def add_static_lease(mac: str, ip: str, hostname: str = "") -> str:
    """Add a static DHCP lease."""
    entry = f"dhcp-host={mac},{ip}"
    if hostname:
        entry += f",{hostname}"
    entry += "\n"

    with open(DNSMASQ_CONF, 'a') as f:
        f.write(entry)
    return await _run_cmd("systemctl reload dnsmasq 2>/dev/null || systemctl restart dnsmasq")
