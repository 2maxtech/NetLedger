import asyncio
import logging

logger = logging.getLogger(__name__)

DNS_HOSTS_FILE = "/etc/dnsmasq.d/netbill-dns.conf"


async def _run_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}\n{stderr.decode()}")
    return stdout.decode()


async def get_dns_config() -> str:
    """Get DNS configuration."""
    try:
        with open(DNS_HOSTS_FILE, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return ""


async def apply_dns_config(config: str) -> str:
    """Write DNS config and reload dnsmasq."""
    with open(DNS_HOSTS_FILE, 'w') as f:
        f.write(config)
    return await _run_cmd("systemctl reload dnsmasq 2>/dev/null || systemctl restart dnsmasq")


async def add_dns_entry(domain: str, ip: str) -> str:
    """Add a DNS A record."""
    entry = f"address=/{domain}/{ip}\n"
    with open(DNS_HOSTS_FILE, 'a') as f:
        f.write(entry)
    return await _run_cmd("systemctl reload dnsmasq 2>/dev/null || systemctl restart dnsmasq")


async def get_upstream_dns() -> list:
    """Get upstream DNS servers from resolv.conf."""
    try:
        with open("/etc/resolv.conf", 'r') as f:
            servers = []
            for line in f:
                if line.strip().startswith("nameserver"):
                    servers.append(line.strip().split()[1])
            return servers
    except FileNotFoundError:
        return []
