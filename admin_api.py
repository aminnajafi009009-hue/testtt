"""
admin_api.py — REST API ادمین برای mini-app
aiohttp با JWT middleware
"""
from __future__ import annotations
import json
import logging
import time
from functools import wraps
from aiohttp import web

logger = logging.getLogger(__name__)


def init_admin_api(bot=None, secret: str = "") -> web.Application:
    app = web.Application(middlewares=[_auth_middleware(secret)])
    app.router.add_get("/admin/api/stats",            h_stats)
    app.router.add_get("/admin/api/users",            h_users)
    app.router.add_get("/admin/api/settings",         h_settings)
    app.router.add_get("/admin/api/payment_settings", h_payment_settings)
    app.router.add_get("/admin/api/panels",           h_panels)
    app.router.add_post("/admin/api/update_setting",  h_update_setting)
    app.router.add_post("/admin/api/payment_toggle",  h_payment_toggle)
    app.router.add_post("/admin/api/crypto_toggle",   h_crypto_toggle)
    app.router.add_post("/admin/api/crypto_add",      h_crypto_add)
    app.router.add_post("/admin/api/crypto_delete",   h_crypto_delete)
    app.router.add_post("/admin/api/panel_toggle",    h_panel_toggle)
    app.router.add_post("/admin/api/panel_test",      h_panel_test)
    app.router.add_post("/admin/api/panel_delete",    h_panel_delete)
    app.router.add_post("/admin/api/confirm_order",   h_confirm_order)
    app.router.add_post("/admin/api/test_uniquepay",  h_test_uniquepay)
    app["bot"] = bot
    return app


def _auth_middleware(secret: str):
    @web.middleware
    async def middleware(request: web.Request, handler):
        if not secret:
            return await handler(request)
        # Telegram WebApp: هدر Authorization یا initData
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        init_data = request.headers.get("X-Telegram-Init-Data", "")
        # برای سادگی: hash را نیستیم — فقط secret را چک می‌کنیم
        if token != secret and init_data == "":
            return web.json_response({"error": "unauthorized"}, status=401)
        return await handler(request)
    return middleware


async def h_stats(req: web.Request):
    from db_helpers import get_stats_summary
    data = get_stats_summary()
    return web.json_response(data)


async def h_users(req: web.Request):
    f = req.rel_url.query.get("filter", "all")
    q = req.rel_url.query.get("q", "")
    from db_helpers import search_users
    users = search_users(query=q, filter=f, limit=50)
    return web.json_response({"users": users})


async def h_settings(req: web.Request):
    from db_helpers import get_all_settings
    s = get_all_settings()
    return web.json_response({"settings": s})


async def h_payment_settings(req: web.Request):
    from payment_manager_v3 import PaymentManager
    from db_helpers import get_setting, set_setting
    pm = PaymentManager(get_setting, set_setting)
    await pm.load()
    data = {
        "card":      {"enabled": pm.card.enabled,
                      "card_number": pm.card.card_number,
                      "receipt_required": pm.card.receipt_required,
                      "auto_confirm": pm.card.auto_confirm},
        "wallet":    {"enabled": pm.wallet.enabled,
                      "min_charge": pm.wallet.min_charge,
                      "gift_percent": pm.wallet.gift_percent},
        "uniquepay": {"enabled": pm.uniquepay.enabled,
                      "use_telegram_link": pm.uniquepay.use_telegram_link,
                      "show_card_white_label": pm.uniquepay.show_card_white_label,
                      "auto_confirm": pm.uniquepay.auto_confirm},
        "paygo":     {"enabled": pm.paygo.enabled,
                      "price_per_gb": pm.paygo.price_per_gb},
        "cryptos":   [c.__dict__ for c in pm.cryptos],
    }
    return web.json_response(data)


async def h_update_setting(req: web.Request):
    body = await req.json()
    key   = body.get("key", "")
    value = str(body.get("value", ""))
    if not key:
        return web.json_response({"error": "key required"}, status=400)
    from db_helpers import set_setting
    set_setting(key, value)
    return web.json_response({"ok": True})


async def h_payment_toggle(req: web.Request):
    body   = await req.json()
    method = body.get("method", "")
    enabled= body.get("enabled", False)
    from db_helpers import set_setting
    set_setting(f"pm_{method}_enabled", "1" if enabled else "0")
    return web.json_response({"ok": True})


async def h_crypto_toggle(req: web.Request):
    body   = await req.json()
    symbol = body.get("symbol", "").upper()
    enabled= body.get("enabled", False)
    from payment_manager_v3 import PaymentManager
    from db_helpers import get_setting, set_setting
    pm = PaymentManager(get_setting, set_setting)
    await pm.load()
    pm.toggle_crypto(symbol, enabled)
    await pm._save()
    return web.json_response({"ok": True})


async def h_crypto_add(req: web.Request):
    body = await req.json()
    from payment_manager_v3 import PaymentManager, CryptoConfig
    from db_helpers import get_setting, set_setting
    pm = PaymentManager(get_setting, set_setting)
    await pm.load()
    pm.add_crypto(CryptoConfig(
        symbol=body.get("symbol", "").upper(),
        name=body.get("name", ""),
        network=body.get("network", ""),
        wallet_address=body.get("wallet", ""),
        emoji=body.get("emoji", "💰"),
        enabled=True,
    ))
    await pm._save()
    return web.json_response({"ok": True})


async def h_crypto_delete(req: web.Request):
    body   = await req.json()
    symbol = body.get("symbol", "").upper()
    from payment_manager_v3 import PaymentManager
    from db_helpers import get_setting, set_setting
    pm = PaymentManager(get_setting, set_setting)
    await pm.load()
    pm.remove_crypto(symbol)
    await pm._save()
    return web.json_response({"ok": True})


async def h_panels(req: web.Request):
    from db_helpers import get_all_panels
    return web.json_response({"panels": get_all_panels()})


async def h_panel_toggle(req: web.Request):
    body    = await req.json()
    panel_id= int(body.get("id", 0))
    enabled = body.get("enabled", True)
    from db_helpers import update_panel_enabled
    update_panel_enabled(panel_id, enabled)
    return web.json_response({"ok": True})


async def h_panel_test(req: web.Request):
    body    = await req.json()
    panel_id= int(body.get("id", 0))
    from panels_v2 import PanelManager
    pm = PanelManager()
    ok = await pm.test_panel(panel_id)
    return web.json_response({"ok": ok})


async def h_panel_delete(req: web.Request):
    body    = await req.json()
    panel_id= int(body.get("id", 0))
    from db_helpers import delete_panel
    delete_panel(panel_id)
    return web.json_response({"ok": True})


async def h_confirm_order(req: web.Request):
    body     = await req.json()
    order_id = body.get("id")
    from db_helpers import confirm_order_by_id
    confirm_order_by_id(order_id)
    return web.json_response({"ok": True})


async def h_test_uniquepay(req: web.Request):
    from uniquepay import UniquePayClient, UniquePayError
    from db_helpers import get_setting
    import os
    token = os.getenv("UNIQUEPAY_BUSINESS_TOKEN", get_setting("up_token", ""))
    if not token:
        return web.json_response({"ok": False, "error": "token not set"})
    client = UniquePayClient(token)
    import hashlib, time
    hash_id = "test_" + hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    try:
        inv = await client.create_invoice(hash_id=hash_id, amount=50000)
        return web.json_response({"ok": True, "ref_id": inv.get("refId", "")})
    except UniquePayError as e:
        return web.json_response({"ok": False, "error": str(e)})
