import asyncio
import socket
import subprocess
import time


def accel_cmd_sync(command: str, host: str = "127.0.0.1", port: int = 2001) -> str:
    """Execute a command via accel-ppp telnet CLI using raw sockets."""
    s = socket.socket()
    s.settimeout(5)
    s.connect((host, port))
    time.sleep(0.5)
    s.recv(4096)  # consume banner + prompt
    s.sendall(command.encode() + b"\r\n")
    time.sleep(0.5)
    chunks = []
    while True:
        try:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
            if b"accel-ppp# " in data:
                break
        except socket.timeout:
            break
    s.close()
    raw = b"".join(chunks).decode(errors="ignore")
    # Strip prompt at the end
    if "accel-ppp# " in raw:
        raw = raw[:raw.rfind("accel-ppp# ")]
    return raw.strip()


async def accel_cmd(command: str) -> str:
    """Execute a command via accel-ppp telnet CLI (async wrapper)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, accel_cmd_sync, command)


async def get_sessions() -> list[dict]:
    """Get all active PPPoE sessions from accel-ppp."""
    output = await accel_cmd("show sessions sid,ifname,username,calling-sid,ip,rate-limit,type,state,uptime")
    sessions = []
    lines = output.strip().split("\n")
    if len(lines) < 2:
        return sessions

    header = lines[0]
    columns = header.split("|")
    col_names = [c.strip().lower() for c in columns]

    for line in lines[1:]:
        if line.startswith("-") or not line.strip():
            continue
        values = line.split("|")
        if len(values) != len(col_names):
            continue
        row = {col_names[i]: values[i].strip() for i in range(len(col_names))}
        sessions.append(row)

    return sessions


async def find_session_by_username(username: str) -> dict | None:
    """Find an active session by PPPoE username."""
    sessions = await get_sessions()
    for s in sessions:
        if s.get("username") == username:
            return s
    return None


def send_radius_packet(packet_type: str, attributes: dict, secret: str, server: str, port: int) -> str:
    """Send a RADIUS CoA or Disconnect packet using radclient."""
    attr_lines = "\n".join(f"{k} = {v}" for k, v in attributes.items())
    result = subprocess.run(
        ["radclient", "-x", f"{server}:{port}", packet_type, secret],
        input=attr_lines,
        capture_output=True,
        text=True,
        timeout=10,
    )
    output = result.stdout + result.stderr
    # radclient returns non-zero for NAK responses — still useful info
    if result.returncode != 0 and "Error parsing" in result.stderr:
        raise RuntimeError(f"radclient failed: {result.stderr}")
    return output
