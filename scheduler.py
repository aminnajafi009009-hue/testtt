"""
scheduler.py — Cherry VPN Bot v3
وظایف پس‌زمینه — الهام از میرزابات:
  - اعلان انقضای سرویس (حجم / زمان)
  - انقضای فاکتورهای پرداخت‌نشده
  - گزارش روزانه آمار (cron daily)
  - پایش وضعیت پنل‌ها
"""
from __future__ import annotations
import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)

ORDER_LOG_CHANNEL = os.getenv("ORDER_LOG_CHANNEL_ID", "")


# ================================================================
# هسته اصلی است
# ================================================================
async def run_all(bot: "Bot"):
    """تمام وظایف را در یک loop اجرا کن"""
    while True:
        try:
            await asyncio.gather(
                check_expiring_services(bot),
                expire_unpaid_invoices(bot),
                return_exceptions=True
            )
        except Exception as e:
            logger.error("scheduler.run_all error: %s", e)

        # گزارش روزانه: ساعت 8 صبح
        now = datetime.now()
        if now.hour == 8 and now.minute < 5:
            try:
                await daily_stats_report(bot)
            except Exception as e:
                logger.error("daily_report error: %s", e)

        await asyncio.sleep(300)  # هر 5 دقیقه


# ================================================================
# اعلان انقضای سرویس
# ================================================================
async def check_expiring_services(bot: "Bot"):
    """
    سرویس‌هایی که X روز دیگر منقضی می‌شوند را به کاربر اطلاع بده.
    مثل میرزابات: NoticationsService
    """
    try:
        from db_helpers import get_setting, execute
        warn_days = int(get_setting("notify_days_before", 2))
        feat_on   = get_setting("feat:notify_expire", True)
        if not feat_on: return

        import time
        threshold = int(time.time()) + warn_days * 86400
        # سفارش‌هایی که هنوز اعلان انقضا نداده‌ایم و expire_date نزدیک
        rows = execute(
            "SELECT id,user_id,expire_date,vpn_username,amount FROM orders "
            "WHERE status='active' AND notif_sent=0 AND expire_date IS NOT NULL "
            "AND CAST(expire_date AS INTEGER) <= ? "
            "ORDER BY expire_date ASC LIMIT 50",
            (threshold,), fetchall=True) or []

        for row in rows:
            oid, uid, exp, vpn_user, amount = row[0], row[1], row[2], row[3], row[4]
            try:
                exp_ts = int(exp)
                remaining = max(0, (exp_ts - int(time.time())) // 86400)
                await bot.send_message(
                    uid,
                    f"⏰ <b>اعلان انقضای سرویس</b>\n\n"
                    f"سرویس <code>{vpn_user or oid}</code> شما\n"
                    f"📌 تا <b>{remaining} روز دیگر</b> فعال است.\n"
                    "🔄 برای تمدید یا خرید سرویس جدید از منو اقدام کنید.",
                    parse_mode="HTML")
                # علامت‌گذاری اینکه اعلان داده شد
                execute("UPDATE orders SET notif_sent=1 WHERE id=?", (oid,))
            except Exception as e:
                logger.warning("notify uid=%s order=%s: %s", uid, oid, e)
    except Exception as e:
        logger.error("check_expiring_services: %s", e)


# ================================================================
# انقضای فاکتورهای پرداخت‌نشده
# ================================================================
async def expire_unpaid_invoices(bot: "Bot"):
    """
    فاکتورهای UniquePay که بیش از 30 دقیقه پرداخت نشده‌اند را لغو کن.
    مثل میرزابات: payment_expire.php
    """
    try:
        from db_helpers import execute
        import time
        threshold = int(time.time()) - 1800  # 30 دقیقه پیش
        rows = execute(
            "SELECT id,user_id FROM uniquepay_invoices WHERE status='pending' AND created_at<=?",
            (threshold,), fetchall=True) or []
        for row in rows:
            iid, uid = row[0], row[1]
            execute("UPDATE uniquepay_invoices SET status='expired' WHERE id=?", (iid,))
            logger.info("expired unpaid invoice %s for uid %s", iid, uid)
    except Exception as e:
        logger.error("expire_unpaid_invoices: %s", e)


# ================================================================
# گزارش روزانه آمار
# ================================================================
async def daily_stats_report(bot: "Bot"):
    """
    گزارش آمار روزانه به کانال لاگ.
    مثل میرزابات: statusday.php
    """
    try:
        channel = ORDER_LOG_CHANNEL or os.getenv("ORDER_LOG_CHANNEL_ID", "")
        if not channel: return

        from db_helpers import (
            count_users, count_active_services, count_orders_today,
            count_new_users_today, get_revenue_today, get_revenue_total
        )
        now = datetime.now().strftime("%Y-%m-%d")
        text = (
            f"📊 <b>گزارش روزانه — {now}</b>\n\n"
            f"👥 کل کاربر: <b>{count_users():,}</b>\n"
            f"👤 عضو جدید امروز: <b>{count_new_users_today():,}</b>\n"
            f"✅ سرویس فعال: <b>{count_active_services():,}</b>\n"
            f"📦 سفارش امروز: <b>{count_orders_today():,}</b>\n"
            f"💰 درآمد امروز: <b>{get_revenue_today():,} ت</b>\n"
            f"💳 کل درآمد: <b>{get_revenue_total():,} ت</b>"
        )
        await bot.send_message(channel, text, parse_mode="HTML")
    except Exception as e:
        logger.error("daily_stats_report: %s", e)


# ================================================================
# پایش وضعیت پنل‌ها (مثل uptime_panel.php)
# ================================================================
async def check_panels_health(bot: "Bot"):
    """وضعیت همه پنل‌ها را بررسی کن و در صورت ایراد اطلاع بده"""
    try:
        from db_helpers import get_enabled_panels, get_admin_ids
        import aiohttp
        panels = get_enabled_panels()
        admin_ids = get_admin_ids()
        channel = ORDER_LOG_CHANNEL

        for panel in panels:
            url = panel.get("base_url", "")
            if not url: continue
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(url) as resp:
                        if resp.status >= 500:
                            msg = (
                                f"🚨 <b>پنل داون!</b>\n"
                                f"🌐 {panel.get('name')}: {url}\n"
                                f"❌ HTTP {resp.status}"
                            )
                            if channel:
                                try: await bot.send_message(channel, msg, parse_mode="HTML")
                                except Exception: pass
                            for aid in admin_ids[:2]:
                                try: await bot.send_message(aid, msg, parse_mode="HTML")
                                except Exception: pass
            except Exception as conn_err:
                msg = (
                    f"🚨 <b>پنل قابل دسترس نیست!</b>\n"
                    f"🌐 {panel.get('name')}: {url}\n"
                    f"❌ {conn_err}"
                )
                if channel:
                    try: await bot.send_message(channel, msg, parse_mode="HTML")
                    except Exception: pass
    except Exception as e:
        logger.error("check_panels_health: %s", e)


# ================================================================
# کارد به کارد — تایید خودکار (مثل croncard.php)
# ================================================================
async def auto_confirm_card_payments(bot: "Bot"):
    """
    پرداخت‌های کارت به کارت که فراتر ارسال شده‌اند
    و تایید خودکار فعال است ولی هنوز تایید نشده‌اند.
    """
    # TODO: پیاده‌سازی بر اساس نیاز پروژه
    pass
