"""
panels_v2.py — مدیریت یکپارچه همه پنل‌ها (v2)
اضافه شده:
 - 3X-UI / X-UI
 - WireGuard Dashboard / wg-easy
 - Hiddify (v2 + v1)
 - Marzban
 - Marzneshin
 - Outline
 - پشتیبانی از panel_type دینامیک
"""
from __future__ import annotations
import asyncio
import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

PANEL_TYPES = [
    "hiddify",
    "marzban",
    "marzneshin",
    "outline",
    "3x_ui",
    "x_ui",
    "wireguard_dashboard",
    "wg_easy",
]


def make_panel_client(panel_type: str, base_url: str,
                      api_key: str = "", username: str = "",
                      password: str = "", **kwargs):
    """
    Factory: بر اساس panel_type کلاینت مناسب می‌سازد.
    """
    t = panel_type.lower()
    if t == "hiddify":
        from hiddify_panel import HiddifyPanel
        return HiddifyPanel(base_url=base_url, api_key=api_key)
    elif t == "marzban":
        from marzban_panel import MarzbanPanel
        return MarzbanPanel(base_url=base_url, username=username, password=password)
    elif t == "marzneshin":
        from marzneshin_panel import MarzneshinPanel
        return MarzneshinPanel(base_url=base_url, username=username, password=password)
    elif t == "outline":
        from outline_panel import OutlinePanel
        return OutlinePanel(base_url=base_url, api_key=api_key)
    elif t in ("3x_ui", "x_ui", "3xui", "xui"):
        from x3ui_panel import X3UIPanel
        return X3UIPanel(base_url=base_url, username=username, password=password,
                         secret_path=kwargs.get("secret_path", ""))
    elif t == "wireguard_dashboard":
        from wireguard_panel import WireGuardDashboardPanel
        return WireGuardDashboardPanel(base_url=base_url, api_key=api_key,
                                       username=username, password=password)
    elif t == "wg_easy":
        from wireguard_panel import WgEasyPanel
        return WgEasyPanel(base_url=base_url, password=password, api_key=api_key)
    else:
        raise ValueError(f"Unknown panel_type: {panel_type}")


class PanelManager:
    """
    مدیریت یکپارچه تمام پنل‌های تعریف‌شده در DB.
    """
    def __init__(self):
        self._clients: dict[int, object] = {}

    def _load_panel(self, panel_id: int):
        if panel_id in self._clients:
            return self._clients[panel_id]
        from db_helpers import get_panel
        row = get_panel(panel_id)
        if not row:
            raise ValueError(f"Panel {panel_id} not found")
        client = make_panel_client(
            panel_type=row["panel_type"],
            base_url=row["base_url"],
            api_key=row.get("api_key", ""),
            username=row.get("username", ""),
            password=row.get("password", ""),
        )
        self._clients[panel_id] = client
        return client

    def _get_enabled_panels(self) -> list[dict]:
        from db_helpers import get_all_panels
        return [p for p in get_all_panels() if p.get("enabled", 1)]

    async def test_panel(self, panel_id: int) -> bool:
        try:
            client = self._load_panel(panel_id)
            return await client.test_connection()
        except Exception as e:
            logger.error("test_panel %s: %s", panel_id, e)
            return False

    async def create_user_on_panel(
        self, panel_id: int, username: str,
        data_gb: float = 0, expire_days: int = 30,
        expire_hours: int = 0
    ) -> dict:
        if expire_hours:
            expire_days = max(1, expire_hours // 24 + (1 if expire_hours % 24 else 0))
        client = self._load_panel(panel_id)
        result = await client.create_user(
            username=username,
            data_limit_gb=data_gb,
            expire_days=expire_days,
        )
        return result or {}

    async def create_user_on_any_panel(
        self, username: str, data_gb: float = 0,
        expire_days: int = 30, expire_hours: int = 0
    ) -> dict:
        panels = self._get_enabled_panels()
        if not panels:
            raise RuntimeError("هیچ پنل فعالی تعریف نشده")
        random.shuffle(panels)
        for p in panels:
            try:
                return await self.create_user_on_panel(
                    panel_id=p["id"], username=username,
                    data_gb=data_gb, expire_days=expire_days,
                    expire_hours=expire_hours
                )
            except Exception as e:
                logger.warning("Panel %s failed: %s", p["id"], e)
        raise RuntimeError("تمام پنل‌ها خطا دادند")

    async def get_user_info(self, panel_id: int, username: str) -> Optional[dict]:
        try:
            client = self._load_panel(panel_id)
            return await client.get_user_info(username)
        except Exception as e:
            logger.error("get_user_info panel=%s user=%s: %s", panel_id, username, e)
            return None

    async def health_check_all(self) -> dict[int, bool]:
        panels = self._get_enabled_panels()
        tasks = {p["id"]: self.test_panel(p["id"]) for p in panels}
        results = {}
        for pid, coro in tasks.items():
            results[pid] = await coro
        return results
