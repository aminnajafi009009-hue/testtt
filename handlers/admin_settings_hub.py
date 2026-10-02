"""
handlers/admin_settings_hub.py — بهبودیافته
تمام تنظیمات ربات — الهام از میرزابات
"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)
router = Router()


class SettingsStates(StatesGroup):
    set_support_username = State()
    set_min_deposit     = State()
    set_referral_reward = State()
    set_welcome_msg     = State()
    set_order_channel   = State()
    set_maintenance_msg = State()


def _btn(text, cb): return InlineKeyboardButton(text=text, callback_data=cb)
def _url(text, url): return InlineKeyboardButton(text=text, url=url)
def build(rows): return InlineKeyboardMarkup(inline_keyboard=rows)


# ================================================================
# منوی اصلی تنظیمات
# ================================================================
def settings_main_kb() -> InlineKeyboardMarkup:
    return build([
        [
            _btn("📝 ویرایشگر متن‌ها",   "adm:texts"),
            _btn("⚙️ وضعیت قابلیت‌ها", "adm:features"),
        ],
        [
            _btn("🔔 كانال اجباری",      "adm:forcejoin"),
            _btn("💰 حداقل واریز",        "adm:set:min_deposit"),
        ],
        [
            _btn("☎️ نام پشتیبانی",     "adm:set:support"),
            _btn("📢 کانال سفارش",        "adm:set:order_channel"),
        ],
        [
            _btn("🤝 پاداش رفرال",        "adm:set:referral"),
            _btn("🛠️ تعمیرات",              "adm:set:maintenance"),
        ],
        [
            _btn("👨‍💼 مدیریت ادمین‌ها","adm:usr:admins"),
            _btn("🎁 تخفیف‌ها و هدیه",  "adm:discounts"),
        ],
        [_btn("⬅️ برگشت", "adm:main")],
    ])


@router.callback_query(F.data == "adm:settings")
async def cb_settings_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    from db_helpers import get_setting
    maintenance = get_setting("feat:maintenance", False)
    referral    = get_setting("feat:referral", True)
    status_line = f"🛠️ حالت تعمیرات: {'✅ فعال' if maintenance else '❌ غیرفعال'} | 🤝 رفرال: {'✅' if referral else '❌'}"
    await cb.message.edit_text(
        f"⚙️ <b>تنظیمات ربات</b>\n\n{status_line}",
        reply_markup=settings_main_kb(), parse_mode="HTML")


# ================================================================
# نام کاربری پشتیبانی
# ================================================================
@router.callback_query(F.data == "adm:set:support")
async def cb_set_support(cb: CallbackQuery, state: FSMContext):
    from db_helpers import get_setting
    current = get_setting("support_username", "-")
    await state.set_state(SettingsStates.set_support_username)
    await cb.message.edit_text(
        f"☎️ <b>نام کاربری پشتیبانی</b>\n\u0641علی: <code>{current}</code>\n\nنام کاربری جدید بدون @ وارد کنید:",
        reply_markup=build([[_btn("❌ لغو", "adm:settings")]]),
        parse_mode="HTML")


@router.message(SettingsStates.set_support_username)
async def fsm_set_support(msg: Message, state: FSMContext):
    from db_helpers import set_setting
    uname = msg.text.strip().lstrip("@")
    set_setting("support_username", uname)
    await state.clear()
    await msg.answer(f"✅ نام پشتیبانی به <b>@{uname}</b> تنظیم شد.", parse_mode="HTML")


# ================================================================
# حداقل واریز
# ================================================================
@router.callback_query(F.data == "adm:set:min_deposit")
async def cb_set_min_dep(cb: CallbackQuery, state: FSMContext):
    from db_helpers import get_setting
    current = get_setting("min_deposit", 10000)
    await state.set_state(SettingsStates.set_min_deposit)
    await cb.message.edit_text(
        f"💰 <b>حداقل واریز</b>\nفعلی: <b>{current:,} تومان</b>\n\nمبلغ جدید وارد کنید:",
        reply_markup=build([[_btn("❌ لغو", "adm:settings")]]),
        parse_mode="HTML")


@router.message(SettingsStates.set_min_deposit)
async def fsm_set_min_dep(msg: Message, state: FSMContext):
    try:
        val = int(msg.text.strip().replace(",", ""))
        if val < 0: raise ValueError
    except Exception:
        return await msg.answer("❌ عدد نامعتبر")
    from db_helpers import set_setting
    set_setting("min_deposit", val)
    await state.clear()
    await msg.answer(f"✅ حداقل واریز به <b>{val:,} تومان</b> تنظیم شد.", parse_mode="HTML")


# ================================================================
# پاداش رفرال
# ================================================================
@router.callback_query(F.data == "adm:set:referral")
async def cb_set_referral(cb: CallbackQuery, state: FSMContext):
    from db_helpers import get_setting
    current = get_setting("referral_reward", 0)
    enabled = get_setting("feat:referral", True)
    await state.set_state(SettingsStates.set_referral_reward)
    await cb.message.edit_text(
        f"🤝 <b>پاداش رفرال</b>\nفعال: {'✅' if enabled else '❌'} | مبلغ: <b>{current:,} ت</b>\n\nمبلغ پاداش (تومان) وارد کنید (0=غیرفعال):",
        reply_markup=build([[_btn("❌ لغو", "adm:settings")]]),
        parse_mode="HTML")


@router.message(SettingsStates.set_referral_reward)
async def fsm_set_referral(msg: Message, state: FSMContext):
    try: val = int(msg.text.strip().replace(",", ""))
    except Exception: return await msg.answer("❌ عدد نامعتبر")
    from db_helpers import set_setting
    set_setting("referral_reward", val)
    set_setting("feat:referral", val > 0)
    await state.clear()
    if val > 0:
        await msg.answer(f"✅ پاداش رفرال: <b>{val:,} تومان</b>", parse_mode="HTML")
    else:
        await msg.answer("❌ سیستم رفرال غیرفعال شد.")


# ================================================================
# کانال سفارش
# ================================================================
@router.callback_query(F.data == "adm:set:order_channel")
async def cb_set_order_channel(cb: CallbackQuery, state: FSMContext):
    from db_helpers import get_setting
    current = get_setting("order_log_channel", "-")
    await state.set_state(SettingsStates.set_order_channel)
    await cb.message.edit_text(
        f"📢 <b>کانال سفارش</b>\nفعلی: <code>{current}</code>\n\n"
        "آیدی کانال را وارد کنید:\n"
        "<code>-1001234567890</code> یا <code>@username</code>",
        reply_markup=build([[_btn("❌ لغو", "adm:settings")]]),
        parse_mode="HTML")


@router.message(SettingsStates.set_order_channel)
async def fsm_set_order_channel(msg: Message, state: FSMContext):
    from db_helpers import set_setting
    ch = msg.text.strip()
    set_setting("order_log_channel", ch)
    await state.clear()
    await msg.answer(f"✅ کانال سفارش به <code>{ch}</code> تنظیم شد.", parse_mode="HTML")


# ================================================================
# تعمیرات
# ================================================================
@router.callback_query(F.data == "adm:set:maintenance")
async def cb_set_maintenance(cb: CallbackQuery):
    from db_helpers import toggle_setting
    new_val = toggle_setting("feat:maintenance", False)
    status = "✅ فعال" if new_val else "❌ غیرفعال"
    await cb.answer(f"🛠️ حالت تعمیرات: {status}", show_alert=True)
