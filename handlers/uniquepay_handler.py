"""
handlers/uniquepay_handler.py
فلو کامل پرداخت آنلاین UniquePay برای کاربر:
  1. کاربر محصول / پلن را انتخاب می‌کند
  2. پرداخت آنلاین انتخاب می‌شود
  3. فاکتور ساخته می‌شود — کارت و لینک تلگرام نمایش داده می‌شود
  4. Polling خودکار وضعیت تا تأیید یا تایم‌اوت
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
import time
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from uniquepay import UniquePayClient, UniquePayError

logger = logging.getLogger(__name__)
router = Router()

POLL_INTERVAL = 5    # ثانیه
POLL_TIMEOUT  = 900  # 15 دقیقه


def _btn(t, c): return InlineKeyboardButton(text=t, callback_data=c)
def _url(t, u): return InlineKeyboardButton(text=t, url=u)
def build(r): return InlineKeyboardMarkup(inline_keyboard=r)


def _make_hash(user_id: int, amount: int, ts: int) -> str:
    raw = f"{user_id}:{amount}:{ts}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def _get_client() -> UniquePayClient:
    from db_helpers import get_setting
    token = get_setting("up_token", "")
    if not token:
        raise UniquePayError("UNIQUEPAY_BUSINESS_TOKEN تنظیم نشده")
    import os
    return UniquePayClient(token=os.getenv("UNIQUEPAY_BUSINESS_TOKEN", token))


def _use_telegram_link() -> bool:
    from db_helpers import get_setting
    return get_setting("up_use_tglink", "1") == "1"


def _show_white_label() -> bool:
    from db_helpers import get_setting
    return get_setting("up_show_card", "1") == "1"


# ================================================================
# callback: کاربر انتخاب پرداخت آنلاین کرد
# ================================================================
@router.callback_query(F.data.startswith("pay:online:"))
async def cb_pay_online(cb: CallbackQuery, bot: Bot):
    """
    داده: pay:online:{order_id}:{amount}
    """
    parts = cb.data.split(":")
    order_id = parts[2]
    amount   = int(parts[3])
    user_id  = cb.from_user.id

    # بررسی فعال بودن
    from db_helpers import get_setting
    if get_setting("up_enabled", "0") != "1":
        await cb.answer("❌ پرداخت آنلاین فعلاً غیرفعال است", show_alert=True)
        return

    await cb.message.edit_text("⏳ در حال ساخت فاکتور...")

    ts = int(time.time())
    hash_id = f"cherry_{order_id}_{_make_hash(user_id, amount, ts)}"

    redirect_url = get_setting("up_redirect", "") or None

    try:
        client = _get_client()
        invoice = await client.create_invoice(
            hash_id=hash_id,
            amount=amount,
            redirect_url=redirect_url,
        )
    except UniquePayError as e:
        await cb.message.edit_text(
            f"❌ خطا در ایجاد فاکتور:\n<code>{e}</code>",
            parse_mode="HTML"
        )
        return

    ref_id     = invoice["refId"]
    pay_link   = invoice["paymentLink"]
    tg_link    = invoice["telegramPaymentLink"]
    card_num   = invoice.get("whiteLabel", {}).get("cardNumber", "")
    payable    = invoice.get("whiteLabel", {}).get("payableAmount", str(amount))

    # ذخیره hash_id در DB برای polling
    from db_helpers import set_order_payment_hash
    set_order_payment_hash(order_id, hash_id)

    # ساخت پیام
    card_formatted = " — ".join(card_num[i:i+4] for i in range(0,16,4)) if len(card_num)==16 else card_num
    text = (
        f"💳 <b>پرداخت آنلاین</b>\n\n"
        f"💰 مبلغ قابل واریز: <b>{int(payable):,} تومان</b>\n"
    )
    if _show_white_label() and card_num:
        text += f"💳 شماره کارت: <code>{card_formatted}</code>\n"
    text += (
        f"\n✅ بعد از پرداخت، خودکار تأیید می‌شود.\n"
        f"⏰ این فاکتور تا <b>15 دقیقه</b> معتبر است."
    )

    rows = []
    if _use_telegram_link():
        rows.append([_url("📲 پرداخت در تلگرام", tg_link)])
    rows.append([_url("🌐 پردادخت آنلاین", pay_link)])
    rows.append([_btn("🔄 بررسی وضعیت", f"pay:check:{hash_id}")])
    rows.append([_btn("❌ لغو", "pay:cancel")])

    await cb.message.edit_text(text, reply_markup=build(rows), parse_mode="HTML")

    # شروع polling در background
    asyncio.create_task(
        _poll_payment(bot=bot, chat_id=cb.message.chat.id,
                      message_id=cb.message.message_id,
                      hash_id=hash_id, order_id=order_id)
    )


# ================================================================
# polling خودکار
# ================================================================
async def _poll_payment(bot: Bot, chat_id: int, message_id: int,
                        hash_id: str, order_id: str):
    """
    هر 5 ثانیه check-invoice می‌زند تا پرداخت تأیید یا timeout شود.
    """
    try:
        client = _get_client()
    except Exception as e:
        logger.error("_poll_payment get_client: %s", e)
        return

    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            inv = await client.check_invoice(hash_id)
            if inv.get("isPaid") and inv.get("isVerified"):
                await _on_payment_success(bot, chat_id, message_id, hash_id, order_id, inv)
                return
        except Exception as e:
            logger.warning("poll_payment check: %s", e)

    # تایماوت
    try:
        await bot.edit_message_text(
            "❌ زمان پرداخت تمام شد.\n\n"
            "اگر پرداخت انجام دادید ولی تأیید نشد، با پشتیبانی تماس بگیرید.",
            chat_id=chat_id, message_id=message_id
        )
    except Exception:
        pass


async def _on_payment_success(bot: Bot, chat_id: int, message_id: int,
                               hash_id: str, order_id: str, inv: dict):
    """پس از تأیید پرداخت"""
    try:
        from db_helpers import confirm_order_by_id, get_order
        confirm_order_by_id(order_id)
        order = get_order(order_id)
    except Exception as e:
        logger.error("_on_payment_success db: %s", e)
        order = None

    amount = inv.get("amount", "")
    fee    = inv.get("fee", "0")

    try:
        await bot.edit_message_text(
            f"✅ <b>پرداخت موفق تأیید شد!</b>\n\n"
            f"💰 مبلغ: <b>{int(amount):,} تومان</b>\n"
            f"🏷 کد پیگیری: <code>{hash_id}</code>\n\n"
            "🚀 سرویس شما در حال آماده‌سازی است...",
            chat_id=chat_id, message_id=message_id,
            parse_mode="HTML"
        )
    except Exception:
        pass

    # ارسال به کانال لاگ
    try:
        from db_helpers import get_setting
        log_ch = get_setting("order_log_channel", "")
        if log_ch:
            await bot.send_message(
                chat_id=int(log_ch),
                text=(
                    f"💳 <b>پرداخت آنلاین تأیید شد</b>\n"
                    f"👤 کاربر: {chat_id}\n"
                    f"💰 مبلغ: {int(amount):,} ت\n"
                    f"🏷 hash: <code>{hash_id}</code>"
                ),
                parse_mode="HTML"
            )
    except Exception:
        pass


# ================================================================
# بررسی دستی
# ================================================================
@router.callback_query(F.data.startswith("pay:check:"))
async def cb_pay_check(cb: CallbackQuery):
    hash_id = cb.data.replace("pay:check:", "")
    await cb.answer("⏳ در حال بررسی...")
    try:
        client = _get_client()
        inv = await client.check_invoice(hash_id)
        if inv.get("isPaid"):
            await cb.message.edit_text(
                "✅ <b>پرداتخ تأیید شد!</b>\nسرویس در حال آماده‌سازی...",
                parse_mode="HTML"
            )
        else:
            status = inv.get("status", "pending")
            await cb.answer(f"⚠️ وضعیت: {status} — هنوز تأیید نشده.", show_alert=True)
    except UniquePayError as e:
        await cb.answer(f"❌ {e}", show_alert=True)


@router.callback_query(F.data == "pay:cancel")
async def cb_pay_cancel(cb: CallbackQuery):
    await cb.message.edit_text("❌ پرداخت لغو شد.")
