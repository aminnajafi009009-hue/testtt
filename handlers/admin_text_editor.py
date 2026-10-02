"""
handlers/admin_text_editor.py
ویرایشگر متن‌ها و دکمه‌ها — الهام از میرزابات
هر متنی که در ربات نمایش داده می‌شود قابل سفارشی‌سازی است.
"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)
router = Router()


class TextEditorStates(StatesGroup):
    wait_new_text = State()  # ادمین متن جدید را وارد می‌کند


def _btn(text, cb): return InlineKeyboardButton(text=text, callback_data=cb)
def build(rows): return InlineKeyboardMarkup(inline_keyboard=rows)


# لیست کامل متن‌ها با نام فارسی
TEXT_ITEMS = [
    ("btn_buy",          "🛒 دکمه: خرید اشتراک"),
    ("btn_myservices",   "📦 دکمه: سرویس‌های من"),
    ("btn_renew",        "🔄 دکمه: تمدید سرویس"),
    ("btn_test",         "🔑 دکمه: سرویس تست"),
    ("btn_wallet",       "💰 دکمه: کیف پول"),
    ("btn_support",      "☎️ دکمه: پشتیبانی"),
    ("btn_affiliates",   "🤝 دکمه: زیرمجموعه‌گیری"),
    ("btn_discount",     "🎁 دکمه: کد هدیه"),
    ("btn_tariff",       "📊 دکمه: تعرفه‌ها"),
    ("btn_help",         "📚 دکمه: آموزش"),
    ("text_start",       "👋 پیام خوشآمدگویی"),
    ("text_wallet",      "💳 پیام کیف پول"),
    ("text_after_pay",   "✅ پیام بعد از پرداخت"),
    ("text_after_test",  "🔑 پیام سرویس تست"),
    ("text_test_expired","❌ پیام اتمام تست"),
    ("text_tariff",      "📊 متن تعرفه‌ها"),
    ("text_faq",         "❓ سوالات متداول"),
    ("text_rules",       "📌 قوانین"),
    ("text_support",     "📧 متن پشتیبانی"),
    ("text_help",        "📚 متن آموزش"),
]

PAGE_SIZE = 8


# ================================================================
# صفحه اصلی: لیست متن‌ها
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:texts(:\d+)?$"))
async def cb_texts_list(cb: CallbackQuery):
    import re
    m = re.search(r":(\d+)$", cb.data)
    page = int(m.group(1)) if m else 0
    from db_helpers import get_setting

    items = TEXT_ITEMS[page*PAGE_SIZE:(page+1)*PAGE_SIZE]
    rows = []
    for key, label in items:
        custom = get_setting(f"text:{key}")
        indicator = " 🟢" if custom else ""  # سبز = سفارشی شده
        rows.append([_btn(f"{label}{indicator}", f"adm:text:edit:{key}")])

    nav = []
    if page > 0:
        nav.append(_btn("⬅️ قبل", f"adm:texts:{page-1}"))
    if (page+1)*PAGE_SIZE < len(TEXT_ITEMS):
        nav.append(_btn("➡️ بعد", f"adm:texts:{page+1}"))
    if nav: rows.append(nav)
    rows.append([_btn("⬅️ برگشت", "adm:settings")])

    await cb.message.edit_text(
        "📝 <b>ویرایشگر متن‌ها و دکمه‌ها</b>\n"
        "🟢 = سفارشی شده | بدون نشانه = پیش‌فرض\n\nمتن مورد نظر را انتخاب کنید:",
        reply_markup=build(rows), parse_mode="HTML")


# ================================================================
# صفحه ویرایش یک متن
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:text:edit:(\w+)$"))
async def cb_text_edit(cb: CallbackQuery, state: FSMContext):
    import re
    key = re.match(r"adm:text:edit:(\w+)", cb.data).group(1)
    from db_helpers import get_text, get_setting

    # لیبل فارسی
    label = next((l for k, l in TEXT_ITEMS if k == key), key)
    current_custom = get_setting(f"text:{key}")
    current_text   = get_text(key)

    await state.update_data(edit_key=key, edit_page=0)
    await state.set_state(TextEditorStates.wait_new_text)

    text = (
        f"✏️ <b>{label}</b>\n\n"
        f"📌 متن فعلی:\n<code>{current_text}</code>\n\n"
        + ("🟢 (<i>سفارشی‌سازی‌شده</i>)\n" if current_custom else "🔵 (<i>پیش‌فرض</i>)\n")
        + "\n⬇️ متن جدید را بفرستید\n"
        "💡 ارسال <b>0</b> = بازگشت به پیش‌فرض\n\n"
        "📌 متغیرهای دینامیک: <code>{name}</code> <code>{balance}</code> <code>{config}</code>"
    )
    await cb.message.edit_text(
        text,
        reply_markup=build([
            [_btn("♻️ بازگشت به پیش‌فرض", f"adm:text:reset:{key}")],
            [_btn("❌ لغو",                      "adm:texts")],
        ]),
        parse_mode="HTML")


@router.message(TextEditorStates.wait_new_text)
async def fsm_text_save(msg: Message, state: FSMContext):
    d = await state.get_data()
    key = d.get("edit_key")
    new_text = msg.text or msg.caption or ""
    await state.clear()

    if not key:
        return await msg.answer("❌ خطای داخلی. دوباره از منو انتخاب کنید.")

    if new_text.strip() == "0":
        from db_helpers import reset_text
        reset_text(key)
        await msg.answer(f"♻️ متن <b>{key}</b> به پیش‌فرض بازگشت داده شد.", parse_mode="HTML")
    elif not new_text.strip():
        await msg.answer("❌ متن خالی است. دوباره امتحان کنید.")
    else:
        from db_helpers import set_text
        set_text(key, new_text.strip())
        label = next((l for k, l in TEXT_ITEMS if k == key), key)
        await msg.answer(
            f"✅ <b>{label}</b> ذخیره شد:\n\n<code>{new_text[:200]}</code>",
            parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:text:reset:(\w+)$"))
async def cb_text_reset(cb: CallbackQuery, state: FSMContext):
    import re
    key = re.match(r"adm:text:reset:(\w+)", cb.data).group(1)
    from db_helpers import reset_text, get_text
    reset_text(key)
    await state.clear()
    default_val = get_text(key)
    label = next((l for k, l in TEXT_ITEMS if k == key), key)
    await cb.answer(f"♻️ {label} به پیش‌فرض بازگشت داده شد.", show_alert=True)


# ================================================================
# مدیریت قابلیت‌ها (مثل میرزابات: وضعیت قابلیت‌ها)
# ================================================================
FEATURES = [
    ("test_service",   "🔑 سرویس تست"),
    ("referral",       "🤝 سیستم رفرال"),
    ("gift_codes",     "🎁 کد هدیه"),
    ("show_tariff",    "📊 نمایش تعرفه"),
    ("vip_only_buy",   "⭐ فقط VIP خرید کند"),
    ("maintenance",    "🛠️ حالت تعمیرات"),
    ("force_join",     "🔔 جوین اجباری"),
    ("notify_expire",  "⏰ اعلان انقضا"),
]


@router.callback_query(F.data == "adm:features")
async def cb_features(cb: CallbackQuery):
    from db_helpers import get_setting
    rows = []
    for key, label in FEATURES:
        is_on = bool(get_setting(f"feat:{key}", True))
        status = "✅ روشن" if is_on else "❌ خاموش"
        rows.append([
            _btn(label,  f"adm:feat:noop:{key}"),
            _btn(status, f"adm:feat:toggle:{key}"),
        ])
    rows.append([_btn("⬅️ برگشت", "adm:settings")])
    await cb.message.edit_text(
        "⚙️ <b>وضعیت قابلیت‌ها</b>\nهر قابلیت را می‌توانید روشن/خاموش کنید:",
        reply_markup=build(rows), parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:feat:toggle:(\w+)$"))
async def cb_feat_toggle(cb: CallbackQuery):
    import re
    key = re.match(r"adm:feat:toggle:(\w+)", cb.data).group(1)
    from db_helpers import toggle_setting
    new_val = toggle_setting(f"feat:{key}", default=True)
    label = next((l for k, l in FEATURES if k == key), key)
    status = "✅ روشن شد" if new_val else "❌ خاموش شد"
    await cb.answer(f"{label}: {status}")
    # رفرش، منو را آپدیت کن
    # trigger same callback to refresh
    from aiogram.types import CallbackQuery as CQ
    from db_helpers import get_setting
    rows = []
    for k2, label2 in FEATURES:
        is_on = bool(get_setting(f"feat:{k2}", True))
        status2 = "✅ روشن" if is_on else "❌ خاموش"
        rows.append([
            _btn(label2,  f"adm:feat:noop:{k2}"),
            _btn(status2, f"adm:feat:toggle:{k2}"),
        ])
    rows.append([_btn("⬅️ برگشت", "adm:settings")])
    await cb.message.edit_reply_markup(reply_markup=build(rows))


@router.callback_query(F.data.startswith("adm:feat:noop:"))
async def cb_feat_noop(cb: CallbackQuery):
    await cb.answer()


# ================================================================
# مدیریت کانال اجباری
# ================================================================
class ForceJoinStates(StatesGroup):
    add_channel = State()


@router.callback_query(F.data == "adm:forcejoin")
async def cb_forcejoin(cb: CallbackQuery):
    from db_helpers import get_force_join_channels
    channels = get_force_join_channels()
    text = "🔔 <b>کانال اجباری</b>\n\n"
    rows = []
    if channels:
        for ch in channels:
            text += f"• <code>{ch}</code>\n"
            rows.append([_btn(f"❌ حذف {ch}", f"adm:fj:del:{ch}")])
    else:
        text += "ℹ️ کانالی تنظیم نشده."
    rows.append([_btn("➕ افزودن کانال", "adm:fj:add"),
                 _btn("⬅️ برگشت",         "adm:settings")])
    await cb.message.edit_text(text, reply_markup=build(rows), parse_mode="HTML")


@router.callback_query(F.data == "adm:fj:add")
async def cb_fj_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ForceJoinStates.add_channel)
    await cb.message.edit_text(
        "🔔 آیدی کانال را بفرست\n"
        "<code>-1001234567890</code> یا <code>@username</code>",
        reply_markup=build([[_btn("❌ لغو", "adm:forcejoin")]]),
        parse_mode="HTML")


@router.message(ForceJoinStates.add_channel)
async def fsm_fj_add(msg: Message, state: FSMContext):
    channel = msg.text.strip()
    from db_helpers import get_force_join_channels, set_force_join_channels
    channels = get_force_join_channels()
    if channel not in channels:
        channels.append(channel)
        set_force_join_channels(channels)
    await state.clear()
    await msg.answer(f"✅ کانال <code>{channel}</code> اضافه شد.", parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:fj:del:(.+)$"))
async def cb_fj_del(cb: CallbackQuery):
    import re
    ch = re.match(r"adm:fj:del:(.+)", cb.data).group(1)
    from db_helpers import get_force_join_channels, set_force_join_channels
    channels = [c for c in get_force_join_channels() if c != ch]
    set_force_join_channels(channels)
    await cb.answer(f"✅ حذف شد: {ch}")
