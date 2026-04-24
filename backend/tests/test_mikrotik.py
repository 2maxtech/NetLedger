"""Unit tests for the MikroTik RouterOS v7 REST API client.

All network I/O is mocked via unittest.mock so no real router is needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.mikrotik import (
    MikroTikClient,
    MikroTikAuthError,
    MikroTikConnectionError,
    MikroTikError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int = 200, json_data=None) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = str(json_data)
    return resp


def _client(url="https://192.168.88.1", user="admin", password="secret"):
    """Return a MikroTikClient with explicit credentials (no settings dependency)."""
    return MikroTikClient(url=url, user=user, password=password)


# ---------------------------------------------------------------------------
# get_identity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_identity_returns_name():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, {"name": "MikroTik-HQ"})
        result = await client.get_identity()
    assert result == "MikroTik-HQ"
    mock_req.assert_awaited_once_with("GET", "system/identity")


# ---------------------------------------------------------------------------
# get_resources
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_resources_returns_dict():
    client = _client()
    payload = {"uptime": "1d00:00:00", "free-memory": 12345678}
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, payload)
        result = await client.get_resources()
    assert result == payload


# ---------------------------------------------------------------------------
# create_secret
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_secret_returns_id():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(201, {".id": "*1A"})
        result = await client.create_secret("user1", "pass1", profile="default")
    assert result == "*1A"
    mock_req.assert_awaited_once()
    call_args = mock_req.call_args
    assert call_args[0][0] == "PUT"
    assert call_args[0][1] == "ppp/secret"
    assert call_args[1]["json"]["name"] == "user1"
    assert call_args[1]["json"]["password"] == "pass1"


@pytest.mark.asyncio
async def test_create_secret_with_caller_id():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(201, {".id": "*2B"})
        result = await client.create_secret("user2", "pass2", caller_id="AA:BB:CC:DD:EE:FF")
    assert result == "*2B"
    payload = mock_req.call_args[1]["json"]
    assert payload["caller-id"] == "AA:BB:CC:DD:EE:FF"


# ---------------------------------------------------------------------------
# enable_secret / disable_secret
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enable_secret_sends_correct_patch():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, {})
        await client.enable_secret("*1A")
    mock_req.assert_awaited_once_with(
        "PATCH", "ppp/secret/*1A", json={"disabled": "no"}
    )


@pytest.mark.asyncio
async def test_disable_secret_sends_correct_patch():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, {})
        await client.disable_secret("*1A")
    mock_req.assert_awaited_once_with(
        "PATCH", "ppp/secret/*1A", json={"disabled": "yes"}
    )


# ---------------------------------------------------------------------------
# update_secret / delete_secret
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_secret_calls_patch():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, {})
        await client.update_secret("*1A", {"profile": "premium"})
    mock_req.assert_awaited_once_with(
        "PATCH", "ppp/secret/*1A", json={"profile": "premium"}
    )


@pytest.mark.asyncio
async def test_delete_secret_calls_delete():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(204, None)
        await client.delete_secret("*1A")
    mock_req.assert_awaited_once_with("DELETE", "ppp/secret/*1A")


# ---------------------------------------------------------------------------
# set_queue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_queue_returns_id():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(201, {".id": "*3C"})
        result = await client.set_queue("user1", "192.168.1.10/32", "10M/5M")
    assert result == "*3C"
    call_args = mock_req.call_args
    assert call_args[0][0] == "PUT"
    assert call_args[0][1] == "queue/simple"
    payload = call_args[1]["json"]
    assert payload["name"] == "user1"
    assert payload["target"] == "192.168.1.10/32"
    assert payload["max-limit"] == "10M/5M"


@pytest.mark.asyncio
async def test_update_queue_calls_patch():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, {})
        await client.update_queue("*3C", "20M/10M")
    mock_req.assert_awaited_once_with(
        "PATCH", "queue/simple/*3C", json={"max-limit": "20M/10M"}
    )


@pytest.mark.asyncio
async def test_remove_queue_calls_delete():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(204, None)
        await client.remove_queue("*3C")
    mock_req.assert_awaited_once_with("DELETE", "queue/simple/*3C")


# ---------------------------------------------------------------------------
# find_user_queues / disable_user_queues / enable_user_queues
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_user_queues_matches_by_name_and_interface():
    client = _client()
    queues = [
        {".id": "*10", "name": "juan", "target": "10.0.0.1/32"},
        {".id": "*11", "name": "other", "target": "<pppoe-juan>"},
        {".id": "*12", "name": "unrelated", "target": "<pppoe-pedro>"},
        {".id": "*13", "name": "combo", "target": "10.0.0.2/32,<pppoe-juan>"},
    ]
    with patch.object(client, "get_queues", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = queues
        result = await client.find_user_queues("juan")
    ids = [q[".id"] for q in result]
    assert ids == ["*10", "*11", "*13"]


@pytest.mark.asyncio
async def test_disable_user_queues_skips_already_disabled():
    client = _client()
    queues = [
        {".id": "*10", "name": "juan", "target": "10.0.0.1/32", "disabled": "false"},
        {".id": "*11", "name": "other", "target": "<pppoe-juan>", "disabled": "true"},
    ]
    with patch.object(client, "get_queues", new_callable=AsyncMock) as mock_q, \
         patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_q.return_value = queues
        mock_req.return_value = _make_response(200, {})
        count = await client.disable_user_queues("juan")
    assert count == 1
    mock_req.assert_awaited_once_with(
        "PATCH", "queue/simple/*10", json={"disabled": "yes"}
    )


@pytest.mark.asyncio
async def test_disable_user_queues_no_match_returns_zero():
    client = _client()
    with patch.object(client, "get_queues", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = [{".id": "*99", "name": "someone", "target": "1.1.1.1/32"}]
        count = await client.disable_user_queues("juan")
    assert count == 0


@pytest.mark.asyncio
async def test_enable_user_queues_only_touches_disabled():
    client = _client()
    queues = [
        {".id": "*10", "name": "juan", "target": "10.0.0.1/32", "disabled": "true"},
        {".id": "*11", "name": "other", "target": "<pppoe-juan>", "disabled": "false"},
    ]
    with patch.object(client, "get_queues", new_callable=AsyncMock) as mock_q, \
         patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_q.return_value = queues
        mock_req.return_value = _make_response(200, {})
        count = await client.enable_user_queues("juan")
    assert count == 1
    mock_req.assert_awaited_once_with(
        "PATCH", "queue/simple/*10", json={"disabled": "no"}
    )


# ---------------------------------------------------------------------------
# get_active_sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_active_sessions_returns_list():
    client = _client()
    sessions = [
        {".id": "*10", "name": "user1", "address": "10.0.0.1", "uptime": "00:05:00"},
        {".id": "*11", "name": "user2", "address": "10.0.0.2", "uptime": "01:00:00"},
    ]
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, sessions)
        result = await client.get_active_sessions()
    assert result == sessions
    mock_req.assert_awaited_once_with("GET", "ppp/active")


@pytest.mark.asyncio
async def test_get_active_sessions_empty():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, [])
        result = await client.get_active_sessions()
    assert result == []


# ---------------------------------------------------------------------------
# get_secrets / get_secret
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_secrets_returns_list():
    client = _client()
    secrets = [{".id": "*1A", "name": "user1"}, {".id": "*2B", "name": "user2"}]
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, secrets)
        result = await client.get_secrets()
    assert result == secrets


@pytest.mark.asyncio
async def test_get_secret_found():
    client = _client()
    secret = {".id": "*1A", "name": "user1"}
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = _make_response(200, secret)
        result = await client.get_secret("*1A")
    assert result == secret


@pytest.mark.asyncio
async def test_get_secret_not_found_returns_none():
    client = _client()
    with patch.object(client, "_request", new_callable=AsyncMock) as mock_req:
        mock_req.side_effect = MikroTikError("not found", status_code=404)
        result = await client.get_secret("*99")
    assert result is None


# ---------------------------------------------------------------------------
# Error handling — _request level
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_error_raises_mikrotik_auth_error():
    client = _client()
    mock_http_client = AsyncMock()
    mock_http_client.request.return_value = _make_response(401, {"detail": "Unauthorized"})

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(MikroTikAuthError) as exc_info:
            await client._request("GET", "system/identity")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_connection_error_raises_mikrotik_connection_error():
    client = _client()
    mock_http_client = AsyncMock()
    mock_http_client.request.side_effect = httpx.ConnectError("Connection refused")

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(MikroTikConnectionError):
            await client._request("GET", "system/identity")


@pytest.mark.asyncio
async def test_timeout_raises_mikrotik_connection_error():
    client = _client()
    mock_http_client = AsyncMock()
    mock_http_client.request.side_effect = httpx.TimeoutException("timed out")

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(MikroTikConnectionError):
            await client._request("GET", "system/identity")


@pytest.mark.asyncio
async def test_generic_api_error_raises_mikrotik_error():
    client = _client()
    mock_http_client = AsyncMock()
    mock_http_client.request.return_value = _make_response(
        500, {"detail": "Internal server error"}
    )

    with patch.object(client, "_get_client", return_value=mock_http_client):
        with pytest.raises(MikroTikError) as exc_info:
            await client._request("GET", "system/resource")

    assert exc_info.value.status_code == 500
    assert not isinstance(exc_info.value, MikroTikAuthError)


# ---------------------------------------------------------------------------
# Lazy client initialisation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_client_lazy_init():
    """_get_client creates the httpx.AsyncClient only once."""
    client = _client()
    assert client._client is None
    c1 = await client._get_client()
    c2 = await client._get_client()
    assert c1 is c2
    assert isinstance(c1, httpx.AsyncClient)
    await c1.aclose()


# ---------------------------------------------------------------------------
# Constructor falls back to explicit params
# ---------------------------------------------------------------------------

def test_constructor_explicit_params():
    client = MikroTikClient(url="https://10.0.0.1", user="testuser", password="testpass")
    assert client.url == "https://10.0.0.1"
    assert client.user == "testuser"
    assert client.password == "testpass"


def test_constructor_strips_trailing_slash():
    client = MikroTikClient(url="https://10.0.0.1/", user="u", password="p")
    assert not client.url.endswith("/")
