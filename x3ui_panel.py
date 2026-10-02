"""
x3ui_panel.py — 3X-UI / X-UI panel client (most popular panel)
Supports both x-ui (alireza0) and 3x-ui (MHSanaei)
"""
from __future__ import annotations
import asyncio, logging, time, json
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class X3UIPanel:
    """
    Full async client for 3X-UI and X-UI panels.
    API: /login, /panel/api/inbounds (GET/POST), /panel/api/inbounds/addClient
    """
    panel_type = "3x_ui"

    def __init__(self, base_url: str, username: str, password: str,
                 secret_path: str = ""):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.secret_path = secret_path.strip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._logged_in = False

    def _url(self, path: str) -> str:
        if self.secret_path:
            return f"{self.base_url}/{self.secret_path}{path}"
        return f"{self.base_url}{path}"

    async def _session_(self) -> aiohttp.ClientSession:
        if not self._session or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def login(self) -> bool:
        session = await self._session_()
        try:
            async with session.post(
                self._url("/login"),
                json={"username": self.username, "password": self.password},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                data = await r.json(content_type=None)
                self._logged_in = data.get("success", False)
                return self._logged_in
        except Exception as e:
            logger.error("3x-ui login error: %s", e)
            return False

    async def _ensure_login(self):
        if not self._logged_in:
            await self.login()

    async def _get(self, path: str) -> dict:
        await self._ensure_login()
        session = await self._session_()
        async with session.get(self._url(path), timeout=aiohttp.ClientTimeout(total=15)) as r:
            return await r.json(content_type=None)

    async def _post(self, path: str, data: dict = None, form: dict = None) -> dict:
        await self._ensure_login()
        session = await self._session_()
        if form:
            async with session.post(self._url(path), data=form,
                                     timeout=aiohttp.ClientTimeout(total=15)) as r:
                return await r.json(content_type=None)
        async with session.post(self._url(path), json=data or {},
                                 timeout=aiohttp.ClientTimeout(total=15)) as r:
            return await r.json(content_type=None)

    # ---- Inbounds ----
    async def list_inbounds(self) -> list:
        r = await self._get("/panel/api/inbounds/list")
        return r.get("obj", [])

    async def get_inbound(self, inbound_id: int) -> Optional[dict]:
        r = await self._get(f"/panel/api/inbounds/get/{inbound_id}")
        return r.get("obj")

    # ---- Clients ----
    async def add_client(self, inbound_id: int, client: dict) -> bool:
        """
        client = {
            "id": "uuid", "flow": "", "email": "user@email",
            "limitIp": 0, "totalGB": 10737418240,
            "expiryTime": 1700000000000,
            "enable": True, "tgId": "", "subId": ""
        }
        """
        r = await self._post("/panel/api/inbounds/addClient", {
            "id": inbound_id, "settings": json.dumps({"clients": [client]})
        })
        return r.get("success", False)

    async def delete_client(self, inbound_id: int, client_uuid: str) -> bool:
        r = await self._post(f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}")
        return r.get("success", False)

    async def update_client(self, inbound_id: int, client_uuid: str, client: dict) -> bool:
        r = await self._post(
            f"/panel/api/inbounds/updateClient/{client_uuid}",
            {"id": inbound_id, "settings": json.dumps({"clients": [client]})}
        )
        return r.get("success", False)

    async def get_client_stats(self, email: str) -> Optional[dict]:
        r = await self._get(f"/panel/api/inbounds/getClientTraffics/{email}")
        return r.get("obj")

    async def reset_client_traffic(self, inbound_id: int, email: str) -> bool:
        r = await self._post(f"/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}")
        return r.get("success", False)

    # ---- ابزار سطح بالاتر — سازگار با سیستم Cherry ----

    async def create_user(
        self, username: str, data_limit_gb: float = 0,
        expire_days: int = 30, inbound_id: int = 1
    ) -> dict:
        import uuid
        uid = str(uuid.uuid4())
        expire_ms = int((time.time() + expire_days * 86400) * 1000) if expire_days else 0
        total_bytes = int(data_limit_gb * 1024 ** 3) if data_limit_gb else 0
        client = {
            "id": uid, "flow": "",
            "email": username, "limitIp": 0,
            "totalGB": total_bytes, "expiryTime": expire_ms,
            "enable": True, "tgId": "", "subId": uid[:8],
        }
        ok = await self.add_client(inbound_id, client)
        if ok:
            return {"uuid": uid, "email": username, "sub_id": uid[:8]}
        raise Exception("3x-ui add_client failed")

    async def get_user_info(self, username: str) -> Optional[dict]:
        return await self.get_client_stats(username)

    async def disable_user(self, inbound_id: int, email: str) -> bool:
        stats = await self.get_client_stats(email)
        if not stats:
            return False
        stats["enable"] = False
        return await self.update_client(inbound_id, stats["id"], stats)

    async def enable_user(self, inbound_id: int, email: str) -> bool:
        stats = await self.get_client_stats(email)
        if not stats:
            return False
        stats["enable"] = True
        return await self.update_client(inbound_id, stats["id"], stats)

    async def get_subscription_link(self, sub_id: str) -> str:
        return f"{self.base_url}/sub/{sub_id}"

    async def test_connection(self) -> bool:
        return await self.login()

    async def get_server_status(self) -> dict:
        try:
            r = await self._post("/server/status")
            return r.get("obj", {})
        except Exception:
            return {}
