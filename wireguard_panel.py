"""
wireguard_panel.py — WireGuard Dashboard panel client
Supports: wg-easy, wg-dashboard, wireguard-ui
"""
from __future__ import annotations
import logging, asyncio, time
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class WireGuardDashboardPanel:
    """
    Client for WireGuard Dashboard (donaldzou/WGDashboard).
    Endpoints: /api/addPeer, /api/deletePeer, /api/getPeerConf, /api/getPeerSettings
    """
    panel_type = "wireguard_dashboard"

    def __init__(self, base_url: str, api_key: str = "", username: str = "", password: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.username = username
        self.password = password
        self._session: Optional[aiohttp.ClientSession] = None
        self._token: Optional[str] = None
        self._token_ts: float = 0

    async def _session_(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _auth(self) -> str:
        if self.api_key:
            return self.api_key
        if self._token and time.time() - self._token_ts < 3600:
            return self._token
        session = await self._session_()
        async with session.post(
            f"{self.base_url}/api/authenticate",
            json={"username": self.username, "password": self.password},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            data = await r.json(content_type=None)
            self._token = data.get("data", "")
            self._token_ts = time.time()
            return self._token

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def _get(self, path: str, params: dict = None) -> dict:
        token = await self._auth()
        session = await self._session_()
        async with session.get(
            f"{self.base_url}{path}", params=params, headers=self._headers(token),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            return await r.json(content_type=None)

    async def _post(self, path: str, data: dict) -> dict:
        token = await self._auth()
        session = await self._session_()
        async with session.post(
            f"{self.base_url}{path}", json=data, headers=self._headers(token),
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            return await r.json(content_type=None)

    # ---- API ----
    async def list_interfaces(self) -> list:
        r = await self._get("/api/getAllPeersIpUsage")
        return r.get("data", [])

    async def get_peers(self, interface: str = "wg0") -> list:
        r = await self._get(f"/api/{interface}/getPeerList")
        return r.get("data", [])

    async def create_peer(self, interface: str = "wg0", name: str = "",
                          expiry_days: int = 30, data_gb: float = 10.0) -> dict:
        r = await self._post(f"/api/{interface}/addPeers", {
            "peers": [{"name": name or f"user_{int(time.time())}",
                       "allowed_ip": "", "DNS": "1.1.1.1",
                       "endpoint_allowed_ip": "0.0.0.0/0",
                       "keepalive": 21, "mtu": 1420}]
        })
        return r

    async def delete_peer(self, interface: str, public_key: str) -> bool:
        r = await self._post(f"/api/{interface}/deletePeer", {"peers": [public_key]})
        return r.get("status", False)

    async def get_peer_conf(self, interface: str, public_key: str) -> str:
        r = await self._get(f"/api/{interface}/downloadPeer", {"id": public_key})
        return r.get("data", "")

    async def test_connection(self) -> bool:
        try:
            await self._auth()
            return True
        except Exception:
            return False

    async def create_user(
        self, username: str, data_limit_gb: float = 0, expire_days: int = 30,
        interface: str = "wg0"
    ) -> dict:
        """ایجاد یوزر سازگار با سایر پنل‌ها"""
        return await self.create_peer(interface, name=username, expiry_days=expire_days,
                                      data_gb=data_limit_gb or 100)

    async def get_user_info(self, username: str, interface: str = "wg0") -> Optional[dict]:
        peers = await self.get_peers(interface)
        for p in peers:
            if p.get("name") == username:
                return p
        return None


class WgEasyPanel:
    """
    Client for wg-easy (weejewel/wg-easy).
    REST API: /api/session, /api/wireguard/client
    """
    panel_type = "wg_easy"

    def __init__(self, base_url: str, password: str = "", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.password = password
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookie: Optional[str] = None

    async def _session_(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def _login(self):
        session = await self._session_()
        async with session.post(
            f"{self.base_url}/api/session",
            json={"password": self.password},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status not in (200, 204):
                raise Exception(f"wg-easy login failed: {r.status}")

    async def list_clients(self) -> list:
        session = await self._session_()
        try:
            async with session.get(f"{self.base_url}/api/wireguard/client",
                                    timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 401:
                    await self._login()
                    async with session.get(f"{self.base_url}/api/wireguard/client",
                                            timeout=aiohttp.ClientTimeout(total=10)) as r2:
                        return await r2.json(content_type=None)
                return await r.json(content_type=None)
        except Exception as e:
            logger.error("wg-easy list_clients: %s", e)
            return []

    async def create_client(self, name: str) -> dict:
        session = await self._session_()
        async with session.post(
            f"{self.base_url}/api/wireguard/client",
            json={"name": name},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            return await r.json(content_type=None)

    async def delete_client(self, client_id: str) -> bool:
        session = await self._session_()
        async with session.delete(
            f"{self.base_url}/api/wireguard/client/{client_id}",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            return r.status in (200, 204)

    async def get_client_config(self, client_id: str) -> str:
        session = await self._session_()
        async with session.get(
            f"{self.base_url}/api/wireguard/client/{client_id}/configuration",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            return await r.text()

    async def test_connection(self) -> bool:
        try:
            await self._login()
            return True
        except Exception:
            return False

    async def create_user(self, username: str, **kwargs) -> dict:
        return await self.create_client(username)

    async def get_user_info(self, username: str) -> Optional[dict]:
        clients = await self.list_clients()
        for c in clients:
            if c.get("name") == username:
                return c
        return None
