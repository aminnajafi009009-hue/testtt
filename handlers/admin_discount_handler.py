"""
handlers/admin_discount_handler.py
مدیریت تخفیف‌ها و کد‌هدیه — الهام از میرزابات
"""
from __future__ import annotations
import logging, random, string
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)
router = Router()


class DiscountStates(StatesGroup):
    code      = State()
    percent   = State()
    amount    = State()
    uses      = State()
    days_valid = State()
    # کد هدیه
    gift_code  = State()
    gift_value = State()
    gift_type  = State()


def _btn(text, cb): return InlineKeyboardButton(text=text, callback_data=cb)
def build(rows): return InlineKeyboardMarkup(inline_keyboard=rows)
def rand_code(n=8): return "".join(random.choices(string.ascii_uppercase+string.digits, k=n))


@router.callback_query(F.data == "adm:discounts")
async def cb_discounts_menu(cb: CallbackQuery):
    from db_helpers import list_discounts
    disc = list_discounts()
    text = "🎁 <b>تخفیف‌ها و کد هدیه</b>\n\n"
    if disc:
        for d in disc[:8]:
            pct  = f"{d['percent']}%" if d.get('percent') else ""
            amt  = f"{d.get('amount',0):,}ت" if d.get('amount') else ""
            uses = d.get('uses_left', '•')
            text += f"• <code>{d['code']}</code> → {pct}{amt} | باقی: {uses}\n"
    else:
        text += "ℹ️ تخفیفی وجود ندارد."
    await cb.message.edit_text(text, reply_markup=build([
        [_btn("➕ تخفیف جدید",  "adm:disc:new"),
         _btn("🎁 کد هدیه",     "adm:gift:new")],
        [_btn("🗑️ حذف تخفیف",  "adm:disc:del_menu"),
         _btn("🗑️ حذف کد هدیه","adm:gift:del_menu")],
        [_btn("⬅️ برگشت",            "adm:main")],
    ]), parse_mode="HTML")


# ================================================================
# ساخت تخفیف
# ================================================================
@router.callback_query(F.data == "adm:disc:new")
async def cb_disc_new(cb: CallbackQuery, state: FSMContext):
    suggested = rand_code()
    await state.update_data(disc_code=suggested)
    await state.set_state(DiscountStates.code)
    await cb.message.edit_text(
        f"🎁 <b>تخفیف جدید</b>\n\nکد تخفیف را وارد کنید یا با دکمه زیر کد تصادفی استفاده کنید:\n"
        f"💡 پیشنهاد: <code>{suggested}</code>",
        reply_markup=build([
            [_btn(f"✅ استفاده از '{suggested}'", f"adm:disc:usecode:{suggested}")],
            [_btn("❌ لغو", "adm:discounts")],
        ]), parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:disc:usecode:(.+)$"))
async def cb_disc_usecode(cb: CallbackQuery, state: FSMContext):
    import re
    code = re.match(r"adm:disc:usecode:(.+)", cb.data).group(1)
    await state.update_data(disc_code=code)
    await state.set_state(DiscountStates.percent)
    await cb.message.edit_text(
        f"کد: <b>{code}</b>\n\n🔢 درصد تخفیف را وارد کنید (0-100):\n<i>برای مبلغ ثابت عدد 0 وارد کنید</i>",
        reply_markup=build([[_btn("❌ لغو", "adm:discounts")]]),
        parse_mode="HTML")


@router.message(DiscountStates.code)
async def fsm_disc_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper().replace(" ", "")
    if not code:
        return await msg.answer("❌ کد نامعتبر")
    await state.update_data(disc_code=code)
    await state.set_state(DiscountStates.percent)
    await msg.answer(
        f"کد: <b>{code}</b>\n\n🔢 درصد تخفیف (0-100) یا 0 برای مبلغ ثابت:",
        parse_mode="HTML")


@router.message(DiscountStates.percent)
async def fsm_disc_percent(msg: Message, state: FSMContext):
    try:
        pct = int(msg.text.strip())
        if pct < 0 or pct > 100: raise ValueError
    except Exception:
        return await msg.answer("❌ عدد بین 0 تا 100 وارد کنید")
    await state.update_data(disc_percent=pct)
    await state.set_state(DiscountStates.amount)
    await msg.answer(
        f"درصد: <b>{pct}%</b>\n\nتومان ثابت تخفیف (0 = بدون تخفیف مبلغی):",
        parse_mode="HTML")


@router.message(DiscountStates.amount)
async def fsm_disc_amount(msg: Message, state: FSMContext):
    try:
        amt = int(msg.text.strip().replace(",", ""))
        if amt < 0: raise ValueError
    except Exception:
        return await msg.answer("❌ عدد نامعتبر")
    await state.update_data(disc_amount=amt)
    await state.set_state(DiscountStates.uses)
    await msg.answer("🔢 تعداد دفعات استفاده (0 = نامحدود):")


@router.message(DiscountStates.uses)
async def fsm_disc_uses(msg: Message, state: FSMContext):
    try: uses = int(msg.text.strip()) or None
    except Exception: return await msg.answer("❌ عدد نامعتبر")
    await state.update_data(disc_uses=uses)
    await state.set_state(DiscountStates.days_valid)
    await msg.answer("📅 تعداد روز اعتبار (0 = بدون تاریخ انقضا):")


@router.message(DiscountStates.days_valid)
async def fsm_disc_days(msg: Message, state: FSMContext):
    try: days = int(msg.text.strip()) or None
    except Exception: return await msg.answer("❌ عدد نامعتبر")
    d = await state.get_data()
    from db_helpers import create_discount
    cid = create_discount(
        code=d["disc_code"],
        percent=d.get("disc_percent", 0),
        amount=d.get("disc_amount", 0),
        uses=d.get("disc_uses"),
        days_valid=days,
    )
    await state.clear()
    if cid:
        pct_txt = f"{d.get('disc_percent',0)}%" if d.get('disc_percent') else ""
        amt_txt = f"{d.get('disc_amount',0):,}ت" if d.get('disc_amount') else ""
        await msg.answer(
            f"✅ <b>تخفیف ساخته شد</b>\n\n"
            f"🎟️ کد: <code>{d['disc_code']}</code>\n"
            f"🔥 تخفیف: {pct_txt} {amt_txt}\n"
            f"🔢 دفعات: {d.get('disc_uses') or 'نامحدود'}\n"
            f"📅 اعتبار: {days or 'بدون انقضا'}",
            parse_mode="HTML")
    else:
        await msg.answer("❌ خطا در ساخت. شاید کد تکراری باشد.")


# ================================================================
# ساخت کد هدیه
# ================================================================
@router.callback_query(F.data == "adm:gift:new")
async def cb_gift_new(cb: CallbackQuery, state: FSMContext):
    suggested = rand_code(6)
    await state.update_data(gift_code=suggested)
    await state.set_state(DiscountStates.gift_code)
    await cb.message.edit_text(
        f"🎁 <b>کد هدیه جدید</b>\n💡 پیشنهاد: <code>{suggested}</code>\nکد را وارد کنید یا دکمه زیر:",
        reply_markup=build([
            [_btn(f"✅ {suggested}", f"adm:gift:usecode:{suggested}")],
            [_btn("❌ لغو", "adm:discounts")],
        ]), parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:gift:usecode:(.+)$"))
async def cb_gift_usecode(cb: CallbackQuery, state: FSMContext):
    import re
    code = re.match(r"adm:gift:usecode:(.+)", cb.data).group(1)
    await state.update_data(gift_code=code)
    await state.set_state(DiscountStates.gift_value)
    await cb.message.edit_text(
        f"🎁 کد: <b>{code}</b>\nمبلغ هدیه (تومان) را وارد کنید:",
        reply_markup=build([[_btn("❌ لغو", "adm:discounts")]]),
        parse_mode="HTML")


@router.message(DiscountStates.gift_code)
async def fsm_gift_code(msg: Message, state: FSMContext):
    code = msg.text.strip().upper()
    await state.update_data(gift_code=code)
    await state.set_state(DiscountStates.gift_value)
    await msg.answer(f"🎁 کد: <b>{code}</b>\nمبلغ هدیه (تومان):")


@router.message(DiscountStates.gift_value)
async def fsm_gift_value(msg: Message, state: FSMContext):
    try:
        val = int(msg.text.strip().replace(",", ""))
        if val <= 0: raise ValueError
    except Exception:
        return await msg.answer("❌ مبلغ نامعتبر")
    d = await state.get_data()
    from db_helpers import create_gift_code
    cid = create_gift_code(d["gift_code"], val, "balance")
    await state.clear()
    if cid:
        await msg.answer(
            f"✅ <b>کد هدیه ساخته شد</b>\n\n"
            f"🎟️ کد: <code>{d['gift_code']}</code>\n"
            f"💰 مبلغ: <b>{val:,} تومان</b>",
            parse_mode="HTML")
    else:
        await msg.answer("❌ خطا. شاید کد تکراری باشد.")
