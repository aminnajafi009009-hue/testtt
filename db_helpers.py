"""
db_helpers.py — Cherry VPN Bot v3
تمام توابع پایگاه داده (Turso libSQL)
الهام از میرزابات + فاکسیما
"""
from __future__ import annotations
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import libsql_experimental as libsql
    _USE_LIBSQL = True
except ImportError:
    import sqlite3 as libsql
    _USE_LIBSQL = False

_DB_URL  = os.getenv("TURSO_DATABASE_URL", "")
_DB_AUTH = os.getenv("TURSO_AUTH_TOKEN", "")
_conn = None


def get_conn():
    global _conn
    if _conn is None:
        if _USE_LIBSQL and _DB_URL:
            _conn = libsql.connect(_DB_URL, auth_token=_DB_AUTH)
        elif _USE_LIBSQL:
            _conn = libsql.connect(":memory:")
        else:
            _conn = libsql.connect("cherry.db")
            _conn.row_factory = libsql.Row
    return _conn


def execute(sql: str, params=(), fetchone=False, fetchall=False):
    try:
        cur = get_conn().execute(sql, params)
        get_conn().commit()
        if fetchone:  return cur.fetchone()
        if fetchall: return cur.fetchall()
        return cur
    except Exception as e:
        logger.error("DB error | %s | sql=%s", e, sql[:120])
        return None


def init_db():
    """اجرای مهاجرت‌های پایگاه داده"""
    try:
        with open("db_migrations_v3.sql", "r", encoding="utf-8") as f:
            script = f.read()
        conn = get_conn()
        for stmt in script.split(";"):
            s = stmt.strip()
            if s:
                try: conn.execute(s)
                except Exception: pass
        conn.commit()
        logger.info("✅ DB initialized")
    except Exception as e:
        logger.error("init_db error: %s", e)


# ================================================================
# آمار کلی
# ================================================================
def count_users() -> int:
    r = execute("SELECT COUNT(*) FROM users", fetchone=True)
    return r[0] if r else 0

def count_active_users() -> int:
    r = execute("SELECT COUNT(*) FROM users WHERE is_blocked=0", fetchone=True)
    return r[0] if r else 0

def count_vip_users() -> int:
    r = execute("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)
    return r[0] if r else 0

def count_active_services() -> int:
    r = execute("SELECT COUNT(*) FROM orders WHERE status='active'", fetchone=True)
    return r[0] if r else 0

def count_pending_orders() -> int:
    r = execute("SELECT COUNT(*) FROM orders WHERE status='pending'", fetchone=True)
    return r[0] if r else 0

def count_orders() -> int:
    r = execute("SELECT COUNT(*) FROM orders", fetchone=True)
    return r[0] if r else 0

def count_orders_today() -> int:
    r = execute("SELECT COUNT(*) FROM orders WHERE date(created_at,'unixepoch')=date('now')", fetchone=True)
    return r[0] if r else 0

def count_new_users_today() -> int:
    r = execute("SELECT COUNT(*) FROM users WHERE date(created_at,'unixepoch')=date('now')", fetchone=True)
    return r[0] if r else 0

def get_revenue_today() -> int:
    r = execute(
        "SELECT COALESCE(SUM(amount),0) FROM orders WHERE status IN ('confirmed','active') AND date(created_at,'unixepoch')=date('now')",
        fetchone=True)
    return int(r[0]) if r else 0

def get_revenue_total() -> int:
    r = execute("SELECT COALESCE(SUM(amount),0) FROM orders WHERE status IN ('confirmed','active')", fetchone=True)
    return int(r[0]) if r else 0


# ================================================================
# لیست کاربران برای broadcast
# ================================================================
def get_all_user_ids() -> list:
    return execute("SELECT id FROM users WHERE is_blocked=0", fetchall=True) or []

def get_vip_user_ids() -> list:
    return execute("SELECT id FROM users WHERE is_vip=1 AND is_blocked=0", fetchall=True) or []

def get_free_user_ids() -> list:
    return execute("SELECT id FROM users WHERE (is_vip=0 OR is_vip IS NULL) AND is_blocked=0", fetchall=True) or []

def get_active_user_ids() -> list:
    try:
        return execute("SELECT DISTINCT user_id FROM orders WHERE status='active'", fetchall=True) or []
    except Exception: return get_all_user_ids()

def get_inactive_user_ids() -> list:
    try:
        return execute(
            "SELECT id FROM users WHERE id NOT IN (SELECT DISTINCT user_id FROM orders WHERE status='active') AND is_blocked=0",
            fetchall=True) or []
    except Exception: return []

def get_wallet_positive_user_ids() -> list:
    try:
        return execute("SELECT id FROM users WHERE wallet>0", fetchall=True) or []
    except Exception: return []


# ================================================================
# کاربر
# ================================================================
def _row_to_user(row) -> Optional[dict]:
    if not row: return None
    keys = ["id","username","full_name","wallet","is_vip","is_blocked","is_reseller","referrer_id","total_spent","created_at","last_seen"]
    try:
        if hasattr(row, 'keys'):  # sqlite3.Row
            return dict(row)
        return dict(zip(keys, row))
    except Exception:
        return None

def get_user(user_id: int) -> Optional[dict]:
    return _row_to_user(execute("SELECT * FROM users WHERE id=?", (user_id,), fetchone=True))

def get_user_by_username(username: str) -> Optional[dict]:
    return _row_to_user(execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username.lstrip("@"),), fetchone=True))

def get_or_create_user(user_id: int, username: str = "", full_name: str = "", referrer_id: int = None) -> dict:
    existing = get_user(user_id)
    if existing:
        execute("UPDATE users SET username=?,full_name=?,last_seen=strftime('%s','now') WHERE id=?",
                (username or "", full_name or "", user_id))
        existing["username"] = username or ""
        existing["full_name"] = full_name or ""
        return existing
    execute(
        "INSERT OR IGNORE INTO users (id,username,full_name,wallet,is_vip,is_blocked,is_reseller,referrer_id,total_spent,created_at,last_seen) "
        "VALUES (?,?,?,0,0,0,0,?,0,strftime('%s','now'),strftime('%s','now'))",
        (user_id, username or "", full_name or "", referrer_id)
    )
    # ثبت رفرال
    if referrer_id and referrer_id != user_id:
        reward = get_setting("referral_reward", 0)
        if reward:
            add_wallet_balance(referrer_id, int(reward))
    return get_user(user_id) or {}

def set_user_blocked(user_id: int, blocked: bool):
    execute("UPDATE users SET is_blocked=? WHERE id=?", (1 if blocked else 0, user_id))

def toggle_user_block(user_id: int) -> bool:
    row = execute("SELECT is_blocked FROM users WHERE id=?", (user_id,), fetchone=True)
    current = bool(row[0]) if row else False
    execute("UPDATE users SET is_blocked=? WHERE id=?", (0 if current else 1, user_id))
    return not current

def add_wallet_balance(user_id: int, amount: int):
    execute("UPDATE users SET wallet=COALESCE(wallet,0)+? WHERE id=?", (amount, user_id))

def reduce_wallet_balance(user_id: int, amount: int) -> bool:
    row = execute("SELECT wallet FROM users WHERE id=?", (user_id,), fetchone=True)
    if not row or (row[0] or 0) < amount: return False
    execute("UPDATE users SET wallet=wallet-? WHERE id=?", (amount, user_id))
    return True

def set_vip(user_id: int, vip: bool):
    execute("UPDATE users SET is_vip=? WHERE id=?", (1 if vip else 0, user_id))

def get_users_paginated(filter_type: str = "all", q: str = "", limit: int = 15, offset: int = 0) -> list:
    where, params = "1=1", []
    if filter_type == "vip":      where += " AND is_vip=1"
    elif filter_type == "free":   where += " AND (is_vip=0 OR is_vip IS NULL)"
    elif filter_type == "blocked":where += " AND is_blocked=1"
    elif filter_type == "active": where += " AND id IN (SELECT DISTINCT user_id FROM orders WHERE status='active')"
    elif filter_type == "wallet": where += " AND wallet>0"
    if q:
        like = f"%{q}%"
        where += " AND (full_name LIKE ? OR username LIKE ? OR CAST(id AS TEXT) LIKE ?)"
        params += [like, like, like]
    params += [limit, offset]
    rows = execute(f"SELECT * FROM users WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?", params, fetchall=True)
    return [_row_to_user(r) for r in (rows or []) if r]

def count_users_filtered(filter_type: str = "all", q: str = "") -> int:
    where, params = "1=1", []
    if filter_type == "vip":      where += " AND is_vip=1"
    elif filter_type == "free":   where += " AND (is_vip=0 OR is_vip IS NULL)"
    elif filter_type == "blocked":where += " AND is_blocked=1"
    elif filter_type == "active": where += " AND id IN (SELECT DISTINCT user_id FROM orders WHERE status='active')"
    elif filter_type == "wallet": where += " AND wallet>0"
    if q:
        like = f"%{q}%"
        where += " AND (full_name LIKE ? OR username LIKE ? OR CAST(id AS TEXT) LIKE ?)"
        params += [like, like, like]
    r = execute(f"SELECT COUNT(*) FROM users WHERE {where}", params, fetchone=True)
    return r[0] if r else 0


# ================================================================
# سفارش‌ها
# ================================================================
def get_user_orders(user_id: int) -> list:
    try:
        rows = execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user_id,), fetchall=True)
        return rows or []
    except Exception: return []

def get_active_orders_expiring_soon(days: int = 3) -> list:
    try:
        rows = execute(
            "SELECT o.*,u.id as uid FROM orders o JOIN users u ON o.user_id=u.id "
            "WHERE o.status='active' AND o.expire_date IS NOT NULL "
            "AND (CAST(o.expire_date AS INTEGER)-strftime('%s','now'))/86400 <= ? "
            "AND o.notif_sent=0 ORDER BY o.expire_date ASC LIMIT 50",
            (days,), fetchall=True)
        return rows or []
    except Exception: return []


# ================================================================
# پنل‌ها
# ================================================================
def get_all_panels() -> list:
    rows = execute("SELECT * FROM panels ORDER BY id", fetchall=True)
    if not rows: return []
    keys = ["id","name","panel_type","base_url","api_key","username","password","is_active","is_test","test_traffic_gb","test_duration_days","test_limit_per_user","created_at"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def get_enabled_panels() -> list:
    rows = execute("SELECT * FROM panels WHERE is_active=1 ORDER BY id", fetchall=True)
    if not rows: return []
    keys = ["id","name","panel_type","base_url","api_key","username","password","is_active","is_test","test_traffic_gb","test_duration_days","test_limit_per_user","created_at"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def get_test_panels() -> list:
    rows = execute("SELECT * FROM panels WHERE is_active=1 AND is_test=1 ORDER BY id", fetchall=True)
    if not rows: return []
    keys = ["id","name","panel_type","base_url","api_key","username","password","is_active","is_test","test_traffic_gb","test_duration_days","test_limit_per_user","created_at"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def get_panel_by_id(panel_id: int) -> Optional[dict]:
    row = execute("SELECT * FROM panels WHERE id=?", (panel_id,), fetchone=True)
    if not row: return None
    keys = ["id","name","panel_type","base_url","api_key","username","password","is_active","is_test","test_traffic_gb","test_duration_days","test_limit_per_user","created_at"]
    return dict(zip(keys, row)) if not hasattr(row,'keys') else dict(row)

def add_panel(name, panel_type, base_url, api_key="", username="", password="") -> int:
    cur = execute(
        "INSERT INTO panels (name,panel_type,base_url,api_key,username,password,is_active,is_test,test_traffic_gb,test_duration_days,test_limit_per_user) VALUES (?,?,?,?,?,?,1,0,1,1,1)",
        (name, panel_type, base_url, api_key, username, password))
    return cur.lastrowid if cur else 0

def toggle_panel_active(panel_id: int) -> bool:
    row = execute("SELECT is_active FROM panels WHERE id=?", (panel_id,), fetchone=True)
    current = bool(row[0]) if row else False
    execute("UPDATE panels SET is_active=? WHERE id=?", (0 if current else 1, panel_id))
    return not current

def delete_panel(panel_id: int):
    execute("DELETE FROM panels WHERE id=?", (panel_id,))

def update_panel_test_settings(panel_id: int, is_test: bool, traffic_gb: float, days: int, limit: int):
    execute("UPDATE panels SET is_test=?,test_traffic_gb=?,test_duration_days=?,test_limit_per_user=? WHERE id=?",
            (1 if is_test else 0, traffic_gb, days, limit, panel_id))


# ================================================================
# پلن‌ها
# ================================================================
def get_all_plans(active_only=True) -> list:
    q = "SELECT * FROM plans WHERE 1=1"
    if active_only: q += " AND is_active=1"
    q += " ORDER BY sort_order,id"
    rows = execute(q, fetchall=True)
    if not rows: return []
    keys = ["id","name","description","traffic_gb","duration_days","price","panel_id","is_active","is_test","sort_order","created_at"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def get_test_plans() -> list:
    rows = execute("SELECT * FROM plans WHERE is_test=1 AND is_active=1 ORDER BY sort_order,id", fetchall=True)
    if not rows: return []
    keys = ["id","name","description","traffic_gb","duration_days","price","panel_id","is_active","is_test","sort_order","created_at"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def get_plan_by_id(plan_id: int) -> Optional[dict]:
    row = execute("SELECT * FROM plans WHERE id=?", (plan_id,), fetchone=True)
    if not row: return None
    keys = ["id","name","description","traffic_gb","duration_days","price","panel_id","is_active","is_test","sort_order","created_at"]
    return dict(zip(keys, row)) if not hasattr(row,'keys') else dict(row)

def add_plan(name, traffic_gb, duration_days, price, panel_id=None, is_test=0) -> int:
    cur = execute(
        "INSERT INTO plans (name,traffic_gb,duration_days,price,panel_id,is_active,is_test,sort_order,created_at) VALUES (?,?,?,?,?,1,?,0,strftime('%s','now'))",
        (name, traffic_gb, duration_days, price, panel_id, is_test))
    return cur.lastrowid if cur else 0

def delete_plan(plan_id: int):
    execute("DELETE FROM plans WHERE id=?", (plan_id,))


# ================================================================
# تنظیمات
# ================================================================
def get_setting(key: str, default: Any = None) -> Any:
    row = execute("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    if not row: return default
    try: return json.loads(row[0])
    except Exception: return row[0]

def set_setting(key: str, value: Any):
    v = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, v))

def get_all_settings() -> dict:
    rows = execute("SELECT key,value FROM settings", fetchall=True) or []
    result = {}
    for row in rows:
        try: result[row[0]] = json.loads(row[1])
        except Exception: result[row[0]] = row[1]
    return result

def toggle_setting(key: str, default: bool = False) -> bool:
    current = get_setting(key, default)
    new_val = not bool(current)
    set_setting(key, new_val)
    return new_val


# ================================================================
# متن‌های سفارشی (مثل میرزابات)
# ================================================================
_DEFAULT_TEXTS = {
    "btn_buy":           "\U0001f6d2 خرید اشتراک",
    "btn_myservices":    "\U0001f4e6 سرویس‌های من",
    "btn_renew":         "\U0001f504 تمدید سرویس",
    "btn_test":          "\U0001f511 سرویس تست",
    "btn_wallet":        "\U0001f4b0 کیف پول",
    "btn_support":       "\u260e\ufe0f پشتیبانی",
    "btn_affiliates":    "\U0001f91d زیرمجموعه‌گیری",
    "btn_discount":      "\U0001f381 کد هدیه",
    "btn_tariff":        "\U0001f4ca تعرفه‌ها",
    "btn_help":          "\U0001f4da آموزش",
    "text_start":        "\U0001f44b خوش آمدید به <b>{name}</b>!\n\nبرای خرید VPN یکی از گزینه‌ها را انتخاب کنید.",
    "text_wallet":       "\U0001f4b3 <b>کیف پول</b>\n\nموجودی: <b>{balance} تومان</b>",
    "text_after_pay":    "\u2705 <b>پرداخت موفق!</b>\n\nسرویس شما فعال شد.",
    "text_after_test":   "\U0001f511 <b>سرویس تست فعال شد</b>\n\nکانفیگ:\n<code>{config}</code>",
    "text_test_expired": "\u274c سرویس تست شما منقضی شد.\nبرای خرید سرویس رسمی اقدام کنید.",
    "text_tariff":       "\U0001f4ca <b>تعرفه‌های ما</b>\n\nپلن‌های متنوع با بهترین کیفیت.",
    "text_faq":          "\u2753 <b>سوالات متداول</b>\n\n[متن خود را اینجا بنویسید]",
    "text_rules":        "\U0001f4cc <b>قوانین استفاده</b>\n\n[قوانین خود را اینجا بنویسید]",
    "text_support":      "\U0001f4e7 برای پشتیبانی با ما در تماس باشید.",
    "text_help":         "\U0001f4da <b>راهنمای اتصال</b>\n\n[آموزش‌های خود را اینجا بنویسید]",
}

def get_text(key: str, **kwargs) -> str:
    custom = get_setting(f"text:{key}")
    text = custom if custom else _DEFAULT_TEXTS.get(key, key)
    try: return text.format(**kwargs)
    except Exception: return text

def set_text(key: str, value: str):
    set_setting(f"text:{key}", value)

def reset_text(key: str):
    execute("DELETE FROM settings WHERE key=?", (f"text:{key}",))

def get_all_text_keys() -> dict:
    return _DEFAULT_TEXTS


# ================================================================
# تیکت‌ها
# ================================================================
def get_tickets(status: str = "open") -> list:
    rows = execute(
        "SELECT * FROM tickets WHERE status=? ORDER BY created_at DESC LIMIT 30",
        (status,), fetchall=True) or []
    keys = ["id","user_id","subject","message","reply","status","admin_id","created_at","updated_at"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def get_ticket(ticket_id: int) -> Optional[dict]:
    row = execute("SELECT * FROM tickets WHERE id=?", (ticket_id,), fetchone=True)
    if not row: return None
    keys = ["id","user_id","subject","message","reply","status","admin_id","created_at","updated_at"]
    return dict(zip(keys, row)) if not hasattr(row,'keys') else dict(row)

def create_ticket(user_id: int, subject: str, message: str) -> int:
    cur = execute(
        "INSERT INTO tickets (user_id,subject,message,status,created_at) VALUES (?,?,?,'open',strftime('%s','now'))",
        (user_id, subject, message))
    return cur.lastrowid if cur else 0

def reply_ticket(ticket_id: int, reply: str, admin_id: int):
    execute(
        "UPDATE tickets SET reply=?,status='answered',admin_id=?,updated_at=strftime('%s','now') WHERE id=?",
        (reply, admin_id, ticket_id))

def close_ticket(ticket_id: int):
    execute("UPDATE tickets SET status='closed',updated_at=strftime('%s','now') WHERE id=?", (ticket_id,))


# ================================================================
# تخفیف‌ها
# ================================================================
def get_discount(code: str) -> Optional[dict]:
    row = execute(
        "SELECT * FROM discounts WHERE code=? COLLATE NOCASE AND (uses_left IS NULL OR uses_left>0) AND (expires_at IS NULL OR expires_at>strftime('%s','now'))",
        (code,), fetchone=True)
    if not row: return None
    keys = ["id","code","percent","amount","uses_left","created_at","expires_at"]
    return dict(zip(keys, row)) if not hasattr(row,'keys') else dict(row)

def use_discount(discount_id: int):
    execute("UPDATE discounts SET uses_left=uses_left-1 WHERE id=? AND uses_left IS NOT NULL", (discount_id,))

def create_discount(code: str, percent: int = 0, amount: int = 0, uses: int = None, days_valid: int = None) -> int:
    expires = f"(strftime('%s','now')+{days_valid*86400})" if days_valid else "NULL"
    cur = execute(
        f"INSERT INTO discounts (code,percent,amount,uses_left,created_at,expires_at) VALUES (?,?,?,?,strftime('%s','now'),{expires})",
        (code, percent, amount, uses))
    return cur.lastrowid if cur else 0

def list_discounts() -> list:
    rows = execute("SELECT * FROM discounts ORDER BY id DESC LIMIT 50", fetchall=True) or []
    keys = ["id","code","percent","amount","uses_left","created_at","expires_at"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def delete_discount(discount_id: int):
    execute("DELETE FROM discounts WHERE id=?", (discount_id,))


# ================================================================
# کد هدیه
# ================================================================
def get_gift_code(code: str) -> Optional[dict]:
    row = execute("SELECT * FROM gift_codes WHERE code=? COLLATE NOCASE AND used=0", (code,), fetchone=True)
    if not row: return None
    keys = ["id","code","value","type","used","used_by","used_at","created_at"]
    return dict(zip(keys, row)) if not hasattr(row,'keys') else dict(row)

def use_gift_code(code_id: int, user_id: int):
    execute("UPDATE gift_codes SET used=1,used_by=?,used_at=strftime('%s','now') WHERE id=?", (user_id, code_id))

def create_gift_code(code: str, value: int, gift_type: str = "balance") -> int:
    cur = execute(
        "INSERT INTO gift_codes (code,value,type,used,created_at) VALUES (?,?,?,0,strftime('%s','now'))",
        (code, value, gift_type))
    return cur.lastrowid if cur else 0


# ================================================================
# لاگ ادمین
# ================================================================
def log_admin_action(admin_id: int, action: str, extra: str = ""):
    execute("INSERT INTO admin_logs (admin_id,action,extra,ts) VALUES (?,?,?,strftime('%s','now'))",
            (admin_id, action, extra))

def get_admin_activity_log(limit: int = 20) -> list:
    rows = execute("SELECT admin_id,action,extra,ts FROM admin_logs ORDER BY ts DESC LIMIT ?", (limit,), fetchall=True) or []
    return [{"admin_id": r[0], "action": r[1], "extra": r[2], "ts": r[3]} for r in rows]


# ================================================================
# مدیریت ادمین‌ها
# ================================================================
def get_admin_ids() -> list:
    main_id = int(os.getenv("ADMIN_ID", "0"))
    extra = get_setting("extra_admin_ids", [])
    ids = [main_id] + (extra if isinstance(extra, list) else [])
    return [i for i in ids if i]

def add_admin_id(admin_id: int):
    extra = get_setting("extra_admin_ids", [])
    if not isinstance(extra, list): extra = []
    if admin_id not in extra:
        extra.append(admin_id)
        set_setting("extra_admin_ids", extra)

def remove_admin_id(admin_id: int):
    extra = get_setting("extra_admin_ids", [])
    if not isinstance(extra, list): extra = []
    set_setting("extra_admin_ids", [i for i in extra if i != admin_id])


# ================================================================
# کانال اجباری
# ================================================================
def get_force_join_channels() -> list:
    v = get_setting("force_join_channels", [])
    return v if isinstance(v, list) else []

def set_force_join_channels(channels: list):
    set_setting("force_join_channels", channels)


# ================================================================
# رفرال
# ================================================================
def get_referral_count(user_id: int) -> int:
    r = execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (user_id,), fetchone=True)
    return r[0] if r else 0


# ================================================================
# لینک‌های تبلیغاتی
# ================================================================
def get_active_ad_links() -> list:
    rows = execute("SELECT * FROM ad_links WHERE active=1", fetchall=True) or []
    keys = ["id","title","url","hits","active"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]

def get_all_ad_links() -> list:
    rows = execute("SELECT * FROM ad_links ORDER BY id DESC", fetchall=True) or []
    keys = ["id","title","url","hits","active"]
    return [dict(zip(keys, r)) if not hasattr(r,'keys') else dict(r) for r in rows]
