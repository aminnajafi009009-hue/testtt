"""
handlers/broadcast_handler.py — FIXED
باگ‌های اصلاح‌شده:
  1. تنها یک نقطه ورود (adm:broadcast اینجا هندل میشه)
  2. پشتیبانی کامل ایموجی پریمیوم و rich text
     - اگر پیام فوروارد باشد → forward_message (ایموجی پریمیوم حفظ میشه)
     - اگر خود ادمین تایپ کند → copy_message
  3. دکمه‌ساز درون پیام‌های تایپ‌شده (URL buttons)
  4. مخاطب‌بندی دقیق: همه، VIP، رایگان، فعال، غیرفعال، کیف پول مثبت
  5. پیشنمایش + آمار ارسال
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional, List
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

logger = logging.getLogger(__name__)
router = Router()


# ================================================================
# States
# ================================================================
class BroadcastStates(StatesGroup):
    compose      = State()  # ادمین پیام می‌فرستد
    add_buttons  = State()  # اضافه دکمه
    preview      = State()  # تایید نهایی


# ================================================================
# هلپرها
# ================================================================
def _btn(text, cb): return InlineKeyboardButton(text=text, callback_data=cb)
def _url(text, url): return InlineKeyboardButton(text=text, url=url)
def build(rows): return InlineKeyboardMarkup(inline_keyboard=rows)

TARGETS = {
    "all":      "👥 همه کاربران",
    "vip":      "⭐ کاربران VIP",
    "free":     "👤 کاربران رایگان",
    "active":   "✅ سرویس فعال",
    "inactive": "❌ سرویس ندارند",
    "wallet":   "💰 کیف‌پول مثبت",
}


def broadcast_menu_kb() -> InlineKeyboardMarkup:
    return build([
        [_btn("👥 همه کاربران",  "bc:target:all"),
         _btn("⭐ VIP",              "bc:target:vip")],
        [_btn("👤 رایگان",           "bc:target:free"),
         _btn("✅ سرویس فعال",    "bc:target:active")],
        [_btn("❌ سرویس ندارند", "bc:target:inactive"),
         _btn("💰 کیف‌پول مثبت", "bc:target:wallet")],
        [_btn("⬅️ برگشت",             "adm:main")],
    ])


# ================================================================
# نقطه ورود یکتا — adm:broadcast اینجا هندل میشه
# ================================================================
@router.callback_query(F.data == "adm:broadcast")
async def cb_broadcast_entry(cb: CallbackQuery, state: FSMContext):
    """تنها نقطه ورود به سیستم همگانی"""
    await state.clear()  # زدودن هر state قبلی
    await cb.message.edit_text(
        "📣 <b>پیام همگانی</b>\n\nمخاطب را انتخاب کنید:",
        reply_markup=broadcast_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("bc:target:"))
async def cb_bc_target(cb: CallbackQuery, state: FSMContext):
    target = cb.data.replace("bc:target:", "")
    if target not in TARGETS:
        return await cb.answer("نامعتبر")
    await state.update_data(bc_target=target)
    await state.set_state(BroadcastStates.compose)
    name = TARGETS[target]
    await cb.message.edit_text(
        f"📣 <b>مخاطب: {name}</b>\n\n"
        "⬇️ پیام خود را ارسال یا <b>فوروارد</b> کنید:\n\n"
        "📌 نکته: اگر پیام را <b>فوروارد</b> کنید، ایموجی پریمیوم حفظ می‌شود.\n"
        "📌 اگر خودتایپ کنید، می‌توانید دکمه هم اضافه کنید.",
        reply_markup=build([[_btn("❌ لغو", "adm:broadcast")]]),
        parse_mode="HTML")


@router.message(BroadcastStates.compose)
async def fsm_bc_compose(msg: Message, state: FSMContext):
    """
    پیام را دریافت کن
    تشخیص: فوروارد هست یا نه
    """
    # تشخیص forward: اگر توسط ادمین فوروارد شده
    is_forward = (msg.forward_origin is not None or
                  msg.forward_from is not None or
                  msg.forward_from_chat is not None)

    await state.update_data(
        bc_from_chat=msg.chat.id,
        bc_message_id=msg.message_id,
        bc_is_forward=is_forward,
        bc_extra_buttons=[],
    )
    await state.set_state(BroadcastStates.add_buttons)

    if is_forward:
        # برای پیام‌های فورواردشده: دکمه نمی‌توانیم اضافه کنیم (اجبار forward)
        await msg.answer(
            "✅ <b>پیام فورواردشده دریافت شد.</b>\n"
            "📌 ایموجی پریمیوم حفظ می‌شود.\n"
            "⚠️ برای پیام‌های فوروارد نمی‌توان دکمه اضافه کرد.",
            reply_markup=build([
                [_btn("⏩ پیشنمایش بده", "bc:skip_buttons")],
                [_btn("❌ لغو",           "adm:broadcast")],
            ]),
            parse_mode="HTML")
    else:
        # پیام خود ادمین: می‌توان دکمه اضافه کرد
        await msg.answer(
            "✅ <b>پیام دریافت شد.</b>\n\n"
            "🔘 حالا می‌توانید <b>دکمه اضافه کنید</b> یا مستقیم پیشنمایش:\n"
            "📌 فرمت دکمه: <code>متن | https://link.com</code>\n"
            "📌 برای چندین دکمه → هر دکمه روی خط جدید",
            reply_markup=build([
                [_btn("⏩ بدون دکمه پیشنمایش", "bc:skip_buttons")],
                [_btn("❌ لغو",              "adm:broadcast")],
            ]),
            parse_mode="HTML")


@router.message(BroadcastStates.add_buttons)
async def fsm_bc_add_buttons(msg: Message, state: FSMContext):
    """پارس دکمه‌ها"""
    buttons = []
    for line in (msg.text or "").strip().split("\n"):
        if "|" in line:
            parts = line.split("|", 1)
            t, u = parts[0].strip(), parts[1].strip()
            if t and u:
                buttons.append({"text": t, "url": u})
    await state.update_data(bc_extra_buttons=buttons)
    await state.set_state(BroadcastStates.preview)
    await _show_preview(msg, state)


@router.callback_query(F.data == "bc:skip_buttons")
async def cb_bc_skip(cb: CallbackQuery, state: FSMContext):
    await state.update_data(bc_extra_buttons=[])
    await state.set_state(BroadcastStates.preview)
    await _show_preview(cb.message, state, edit=True)


async def _show_preview(msg: Message, state: FSMContext, edit=False):
    from db_helpers import (
        get_all_user_ids, get_vip_user_ids, get_free_user_ids,
        get_active_user_ids, get_inactive_user_ids, get_wallet_positive_user_ids
    )
    d = await state.get_data()
    target     = d.get("bc_target", "all")
    buttons    = d.get("bc_extra_buttons", [])
    is_forward = d.get("bc_is_forward", False)
    fn_map = {
        "all":      get_all_user_ids,
        "vip":      get_vip_user_ids,
        "free":     get_free_user_ids,
        "active":   get_active_user_ids,
        "inactive": get_inactive_user_ids,
        "wallet":   get_wallet_positive_user_ids,
    }
    user_rows = fn_map.get(target, get_all_user_ids)()
    count = len(user_rows)
    name  = TARGETS.get(target, target)
    text = (
        f"⏩ <b>پیشنمایش ارسال</b>\n\n"
        f"🎯 مخاطب: <b>{name}</b>\n"
        f"👥 تعداد گیرندگان: <b>{count:,}</b>\n"
        f"🔘 دکمه: {len(buttons)} عدد\n"
        f"🔄 روش: {'forward (ایموجی پریمیوم حفظ)' if is_forward else 'copy'}\n\n"
        "✅ ارسال شود?"
    )
    kb = build([
        [_btn("🚀 ارسال کن",  "bc:send"),
         _btn("✏️ دکمه تغییر", "bc:edit_buttons")],
        [_btn("❌ لغو",           "adm:broadcast")],
    ])
    if edit:
        try:
            await msg.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await msg.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "bc:edit_buttons", BroadcastStates.preview)
async def cb_bc_edit_buttons(cb: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastStates.add_buttons)
    await cb.message.edit_text(
        "✏️ دکمه‌های جدید را بفرستید:\n"
        "<code>متن دکمه | https://link.com</code>",
        reply_markup=build([[_btn("⏩ بدون دکمه", "bc:skip_buttons"),
                             _btn("❌ لغو",      "adm:broadcast")]]),
        parse_mode="HTML")


@router.callback_query(F.data == "bc:send", BroadcastStates.preview)
async def cb_bc_send(cb: CallbackQuery, state: FSMContext, bot: Bot):
    from db_helpers import (
        get_all_user_ids, get_vip_user_ids, get_free_user_ids,
        get_active_user_ids, get_inactive_user_ids, get_wallet_positive_user_ids
    )
    d = await state.get_data()
    target     = d.get("bc_target", "all")
    from_chat  = d.get("bc_from_chat")
    message_id = d.get("bc_message_id")
    buttons    = d.get("bc_extra_buttons", [])
    is_forward = d.get("bc_is_forward", False)
    await state.clear()

    fn_map = {
        "all":      get_all_user_ids,
        "vip":      get_vip_user_ids,
        "free":     get_free_user_ids,
        "active":   get_active_user_ids,
        "inactive": get_inactive_user_ids,
        "wallet":   get_wallet_positive_user_ids,
    }
    user_rows = fn_map.get(target, get_all_user_ids)()
    user_ids  = [r[0] if isinstance(r, (list, tuple)) else r for r in user_rows]

    # ساخت کیبورد URL برای پیام‌های copy
    extra_kb: Optional[InlineKeyboardMarkup] = None
    if buttons and not is_forward:
        rows = [[InlineKeyboardButton(text=b["text"], url=b["url"])] for b in buttons]
        extra_kb = InlineKeyboardMarkup(inline_keyboard=rows)

    status_msg = await cb.message.edit_text(
        f"⏳ در حال ارسال به {len(user_ids):,} کاربر..."
    )

    sent = failed = blocked = 0
    for i, uid in enumerate(user_ids):
        try:
            if is_forward:
                # ✅ forward: ایموجی پریمیوم 100% حفظ می‌شه
                await bot.forward_message(
                    chat_id=uid,
                    from_chat_id=from_chat,
                    message_id=message_id,
                )
            else:
                # copy: rich text حفظ می‌شه + می‌توان دکمه اضافه کرد
                await bot.copy_message(
                    chat_id=uid,
                    from_chat_id=from_chat,
                    message_id=message_id,
                    reply_markup=extra_kb,
                )
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                await bot.forward_message(uid, from_chat, message_id) if is_forward else \
                    await bot.copy_message(uid, from_chat, message_id, reply_markup=extra_kb)
                sent += 1
            except Exception:
                failed += 1
        except TelegramBadRequest as e:
            logger.warning("bc bad_request uid=%s: %s", uid, e)
            failed += 1
        except Exception as e:
            logger.warning("bc error uid=%s: %s", uid, e)
            failed += 1

        if (i + 1) % 30 == 0:
            await asyncio.sleep(1.2)  # flood control
        if (i + 1) % 200 == 0:
            try:
                await status_msg.edit_text(
                    f"⏳ پیشرفت: {i+1}/{len(user_ids)} | ارسال: {sent:,} | بلاک: {blocked:,}"
                )
            except Exception:
                pass

    await cb.message.answer(
        f"✅ <b>ارسال همگانی تمام شد</b>\n\n"
        f"✔️ ارسال شد: <b>{sent:,}</b>\n"
        f"🚫 بلاک کرده‌اند: <b>{blocked:,}</b>\n"
        f"❌ خطا: <b>{failed:,}</b>",
        parse_mode="HTML")
