"""
handlers/admin_users_handler.py
مدیریت پیشرفته کاربران — الهام از میرزابات:
  • جستجو با ID / یوزرنیم (دستور /user [id])
  • اطلاعات کامل کاربر (موجودی، سرویس‌ها، تاریخ عضویت، ...)
  • افزودن/کسر کیف پول
  • بلاک/آنبلاک
  • VIP/غیرVIP
  • لیست سفارش‌های کاربر
  • ارسال پیام مستقیم به کاربر
  • لیست کاربران با فیلتر
"""
from __future__ import annotations
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)
router = Router()


class UserMgmtStates(StatesGroup):
    search_input     = State()  # ادمین ID یا یوزرنیم می‌دهد
    wallet_add_amount = State()
    wallet_sub_amount = State()
    send_message_text = State()
    view_user_id      = State()  # ID کاربری که الان دریختیم


def _btn(text, cb): return InlineKeyboardButton(text=text, callback_data=cb)
def build(rows): return InlineKeyboardMarkup(inline_keyboard=rows)

PAGE_SIZE = 12


# ================================================================
# دستور /user [id] — مثل میرزابات
# ================================================================
@router.message(Command("user"))
async def cmd_user(msg: Message, state: FSMContext, bot: Bot):
    from db_helpers import get_admin_ids
    if msg.from_user.id not in get_admin_ids(): return
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("🔍 شناسه کاربر را بفرست: /user 123456789")
        return
    target = parts[1].strip()
    await _show_user_info(msg, state, target, bot)


# ================================================================
# منوی کاربران
# ================================================================
@router.callback_query(F.data == "adm:users")
async def cb_users_menu(cb: CallbackQuery):
    from db_helpers import count_users, count_vip_users
    total = count_users()
    vip   = count_vip_users()
    await cb.message.edit_text(
        f"👥 <b>مدیریت کاربران</b>\n\n"
        f"مجموع: <b>{total:,}</b> | VIP: <b>{vip:,}</b>",
        reply_markup=build([
            [_btn("🔍 جستجو کاربر",       "adm:usr:search"),
             _btn("📜 لیست همه",          "adm:usr:list:all:0")],
            [_btn("⭐ VIP‌ها",               "adm:usr:list:vip:0"),
             _btn("🔴 بلاک‌شده‌ها",         "adm:usr:list:blocked:0")],
            [_btn("✅ سرویس فعال",          "adm:usr:list:active:0"),
             _btn("❌ سرویس ندارند",      "adm:usr:list:inactive:0")],
            [_btn("💰 کیف پول مثبت",        "adm:usr:list:wallet:0"),
             _btn("👨‍💼 مدیریت ادمین‌ها", "adm:usr:admins")],
            [_btn("⬅️ برگشت",                  "adm:main")],
        ]), parse_mode="HTML")


@router.callback_query(F.data == "adm:usr:search")
async def cb_usr_search(cb: CallbackQuery, state: FSMContext):
    await state.set_state(UserMgmtStates.search_input)
    await cb.message.edit_text(
        "🔍 شناسه عددی، یوزرنیم (@user) یا بخشی از نام را بفرست:",
        reply_markup=build([[_btn("❌ لغو", "adm:users")]]), parse_mode="HTML")


@router.message(UserMgmtStates.search_input)
async def fsm_usr_search_input(msg: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await _show_user_info(msg, state, msg.text.strip(), bot)


async def _show_user_info(msg: Message, state: FSMContext, target: str, bot: Bot):
    from db_helpers import get_user, get_user_by_username, get_user_orders, get_referral_count
    # جستجو
    user = None
    if target.lstrip("@").lstrip("-").isdigit():
        user = get_user(int(target.lstrip("@")))
    if not user:
        user = get_user_by_username(target)
    if not user:
        await msg.answer(f"❌ کاربر <code>{target}</code> یافت نشد.", parse_mode="HTML")
        return

    uid  = user.get("id") or user.get("user_id")
    name = user.get("full_name") or user.get("name") or "-"
    uname= user.get("username") or "-"
    bal  = user.get("wallet", 0) or 0
    vip  = "⭐ بله" if user.get("is_vip") else "❌ خیر"
    blk  = "🔴 بله" if user.get("is_blocked") else "✅ فعال"
    orders = get_user_orders(uid)
    active_cnt = sum(1 for o in orders if (o[7] if isinstance(o, tuple) else o.get("status")) == "active")
    refs = get_referral_count(uid)
    created = user.get("created_at", "-")

    text = (
        f"👤 <b>اطلاعات کاربر</b>\n\n"
        f"🆔 شناسه: <code>{uid}</code>\n"
        f"🏷 نام: <b>{name}</b>\n"
        f"👤 یوزرنیم: @{uname}\n"
        f"💰 کیف پول: <b>{bal:,} تومان</b>\n"
        f"⭐ VIP: {vip}\n"
        f"🔒 وضعیت: {blk}\n"
        f"📦 سفارش‌های فعال: <b>{active_cnt}</b>\n"
        f"👥 زیرمجموعه: <b>{refs}</b>\n"
        f"📅 عضویت: <b>{created}</b>"
    )

    toggle_block_cb = f"adm:usr:unblock:{uid}" if user.get("is_blocked") else f"adm:usr:block:{uid}"
    toggle_block_text = "✅ آنبلاک" if user.get("is_blocked") else "🔴 بلاک"
    toggle_vip_cb   = f"adm:usr:unvip:{uid}" if user.get("is_vip") else f"adm:usr:setvip:{uid}"
    toggle_vip_text = "❌ رفع VIP" if user.get("is_vip") else "⭐ VIP"

    await msg.answer(text, reply_markup=build([
        [_btn("💰 افزودن کیفپول",  f"adm:usr:addbal:{uid}"),
         _btn("💸 کسر کیفپول",     f"adm:usr:subbal:{uid}")],
        [_btn(toggle_vip_text,          toggle_vip_cb),
         _btn(toggle_block_text,        toggle_block_cb)],
        [_btn("📦 سفارش‌های کاربر",  f"adm:usr:orders:{uid}"),
         _btn("📨 ارسال پیام",          f"adm:usr:msg:{uid}")],
        [_btn("⬅️ برگشت",                   "adm:users")],
    ]), parse_mode="HTML")


# ================================================================
# لیست کاربران با صفحه‌بندی
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:usr:list:(\w+):(\d+)$"))
async def cb_usr_list(cb: CallbackQuery):
    import re
    m = re.match(r"adm:usr:list:(\w+):(\d+)", cb.data)
    filter_type = m.group(1)
    page = int(m.group(2))
    from db_helpers import get_users_paginated, count_users_filtered
    users = get_users_paginated(filter_type=filter_type, limit=PAGE_SIZE, offset=page*PAGE_SIZE)
    total = count_users_filtered(filter_type=filter_type)
    FILTER_NAMES = {
        "all":"همه", "vip":"VIP", "blocked":"بلاک",
        "active":"فعال", "inactive":"غیرفعال", "wallet":"کیفپول مثبت"
    }
    name = FILTER_NAMES.get(filter_type, filter_type)
    text = f"👥 <b>کاربران — {name}</b> ({total:,} نفر)\nصفحه {page+1}\n"
    if not users:
        text += "\nهیچ کاربری یافت نشد."
        rows = [[_btn("⬅️ برگشت", "adm:users")]]
    else:
        rows = []
        for u in users:
            uid   = u.get("id") or u.get("user_id")
            uname = u.get("username") or "-"
            label = f"👤 {uid} @{uname}"
            rows.append([_btn(label, f"adm:usr:view:{uid}")])
        nav = []
        if page > 0:
            nav.append(_btn("⬅️ قبل", f"adm:usr:list:{filter_type}:{page-1}"))
        if (page+1)*PAGE_SIZE < total:
            nav.append(_btn("➡️ بعد", f"adm:usr:list:{filter_type}:{page+1}"))
        if nav: rows.append(nav)
        rows.append([_btn("⬅️ برگشت", "adm:users")])
    await cb.message.edit_text(text, reply_markup=build(rows), parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:usr:view:(\d+)$"))
async def cb_usr_view(cb: CallbackQuery, state: FSMContext, bot: Bot):
    import re
    uid = int(re.match(r"adm:usr:view:(\d+)", cb.data).group(1))
    await _show_user_info(cb.message, state, str(uid), bot)


# ================================================================
# والت — افزودن
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:usr:addbal:(\d+)$"))
async def cb_usr_addbal(cb: CallbackQuery, state: FSMContext):
    import re
    uid = int(re.match(r"adm:usr:addbal:(\d+)", cb.data).group(1))
    await state.update_data(target_user_id=uid, op="add")
    await state.set_state(UserMgmtStates.wallet_add_amount)
    await cb.message.edit_text(
        f"💰 <b>افزودن کیف پول کاربر {uid}</b>\n\nمبلغ را به تومان وارد کنید:",
        reply_markup=build([[_btn("❌ لغو", f"adm:usr:view:{uid}")]]),
        parse_mode="HTML")


@router.message(UserMgmtStates.wallet_add_amount)
async def fsm_wallet_add(msg: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    uid = d.get("target_user_id")
    try:
        amount = int(msg.text.strip().replace(",", "").replace(".", ""))
        if amount <= 0: raise ValueError
    except Exception:
        return await msg.answer("❌ مبلغ نامعتبر است. عدد صحیح وارد کنید.")
    from db_helpers import add_wallet_balance, log_admin_action
    add_wallet_balance(uid, amount)
    log_admin_action(msg.from_user.id, "add_wallet", f"uid={uid} amount={amount}")
    await state.clear()
    await msg.answer(
        f"✅ <b>{amount:,} تومان</b> به کیف پول کاربر <code>{uid}</code> اضافه شد.",
        parse_mode="HTML")
    try:
        await bot.send_message(uid,
            f"💰 مبلغ <b>{amount:,} تومان</b> توسط ادمین به کیف پول شما اضافه شد.",
            parse_mode="HTML")
    except Exception: pass


# ================================================================
# والت — کسر
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:usr:subbal:(\d+)$"))
async def cb_usr_subbal(cb: CallbackQuery, state: FSMContext):
    import re
    uid = int(re.match(r"adm:usr:subbal:(\d+)", cb.data).group(1))
    await state.update_data(target_user_id=uid, op="sub")
    await state.set_state(UserMgmtStates.wallet_sub_amount)
    await cb.message.edit_text(
        f"💸 <b>کسر کیف پول کاربر {uid}</b>\n\nمبلغ را وارد کنید:",
        reply_markup=build([[_btn("❌ لغو", f"adm:usr:view:{uid}")]]),
        parse_mode="HTML")


@router.message(UserMgmtStates.wallet_sub_amount)
async def fsm_wallet_sub(msg: Message, state: FSMContext):
    d = await state.get_data()
    uid = d.get("target_user_id")
    try:
        amount = int(msg.text.strip().replace(",", "").replace(".", ""))
        if amount <= 0: raise ValueError
    except Exception:
        return await msg.answer("❌ مبلغ نامعتبر")
    from db_helpers import reduce_wallet_balance, log_admin_action
    ok = reduce_wallet_balance(uid, amount)
    log_admin_action(msg.from_user.id, "sub_wallet", f"uid={uid} amount={amount}")
    await state.clear()
    if ok:
        await msg.answer(f"✅ <b>{amount:,} تومان</b> از کیف پول کاربر <code>{uid}</code> کسر شد.", parse_mode="HTML")
    else:
        await msg.answer("❌ موجودی کافی نیست.")


# ================================================================
# بلاک / آنبلاک
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:usr:(block|unblock):(\d+)$"))
async def cb_usr_block(cb: CallbackQuery, bot: Bot):
    import re
    m = re.match(r"adm:usr:(block|unblock):(\d+)", cb.data)
    action, uid = m.group(1), int(m.group(2))
    from db_helpers import set_user_blocked, log_admin_action
    blocked = (action == "block")
    set_user_blocked(uid, blocked)
    log_admin_action(cb.from_user.id, action, f"uid={uid}")
    txt = f"🔴 کاربر <code>{uid}</code> بلاک شد." if blocked else f"✅ کاربر <code>{uid}</code> آنبلاک شد."
    await cb.answer(txt, show_alert=True)
    if blocked:
        try:
            await bot.send_message(uid, "🚫 دسترسی شما به ربات محدود شده است.")
        except Exception: pass
    else:
        try:
            await bot.send_message(uid, "✅ دسترسی شما به ربات بازگشایی شد.")
        except Exception: pass


# ================================================================
# VIP
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:usr:(setvip|unvip):(\d+)$"))
async def cb_usr_vip(cb: CallbackQuery, bot: Bot):
    import re
    m = re.match(r"adm:usr:(setvip|unvip):(\d+)", cb.data)
    action, uid = m.group(1), int(m.group(2))
    from db_helpers import set_vip, log_admin_action
    is_vip = (action == "setvip")
    set_vip(uid, is_vip)
    log_admin_action(cb.from_user.id, action, f"uid={uid}")
    txt = f"⭐ کاربر <code>{uid}</code> VIP شد." if is_vip else f"❌ VIP کاربر <code>{uid}</code> لغو شد."
    await cb.answer(txt, show_alert=True)
    msg_txt = "⭐ اشتراک VIP شما فعال شد!" if is_vip else "❌ اشتراک VIP شما لغو شد."
    try:
        await bot.send_message(uid, msg_txt)
    except Exception: pass


# ================================================================
# سفارش‌های کاربر
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:usr:orders:(\d+)$"))
async def cb_usr_orders(cb: CallbackQuery):
    import re
    uid = int(re.match(r"adm:usr:orders:(\d+)", cb.data).group(1))
    from db_helpers import get_user_orders
    orders = get_user_orders(uid)
    if not orders:
        await cb.answer("سفارشی یافت نشد.", show_alert=True)
        return
    text = f"📦 <b>سفارش‌های کاربر {uid}</b>\n"
    for o in orders[:10]:
        if isinstance(o, (list, tuple)):
            text += f"\n• #{o[0]} | {o[7]} | {o[3]:,} ت"
        elif isinstance(o, dict):
            text += f"\n• #{o.get('id')} | {o.get('status')} | {(o.get('amount') or 0):,} ت"
    await cb.message.edit_text(text,
        reply_markup=build([[_btn("⬅️ برگشت", f"adm:usr:view:{uid}")]]),
        parse_mode="HTML")


# ================================================================
# ارسال پیام مستقیم
# ================================================================
@router.callback_query(F.data.regexp(r"^adm:usr:msg:(\d+)$"))
async def cb_usr_send_msg(cb: CallbackQuery, state: FSMContext):
    import re
    uid = int(re.match(r"adm:usr:msg:(\d+)", cb.data).group(1))
    await state.update_data(target_user_id=uid)
    await state.set_state(UserMgmtStates.send_message_text)
    await cb.message.edit_text(
        f"📨 <b>پیام به کاربر {uid}</b>\n\nمتن پیام را بفرستید:",
        reply_markup=build([[_btn("❌ لغو", f"adm:usr:view:{uid}")]]),
        parse_mode="HTML")


@router.message(UserMgmtStates.send_message_text)
async def fsm_send_msg(msg: Message, state: FSMContext, bot: Bot):
    d = await state.get_data()
    uid = d.get("target_user_id")
    await state.clear()
    try:
        await bot.copy_message(chat_id=uid, from_chat_id=msg.chat.id, message_id=msg.message_id)
        await msg.answer(f"✅ پیام به کاربر <code>{uid}</code> ارسال شد.", parse_mode="HTML")
    except Exception as e:
        await msg.answer(f"❌ خطا: {e}")


# ================================================================
# مدیریت ادمین‌ها (مثل میرزابات)
# ================================================================
@router.callback_query(F.data == "adm:usr:admins")
async def cb_admins(cb: CallbackQuery):
    from db_helpers import get_admin_ids
    ids = get_admin_ids()
    text = "👨‍💼 <b>مدیریت ادمین‌ها</b>\n\n"
    rows = []
    for aid in ids:
        text += f"• <code>{aid}</code>\n"
        rows.append([_btn(f"❌ حذف {aid}", f"adm:usr:rmadmin:{aid}")])
    rows.append([_btn("➕ افزودن ادمین", "adm:usr:addadmin"),
                 _btn("⬅️ برگشت",         "adm:users")])
    await cb.message.edit_text(text, reply_markup=build(rows), parse_mode="HTML")


@router.callback_query(F.data == "adm:usr:addadmin")
async def cb_addadmin(cb: CallbackQuery, state: FSMContext):
    from aiogram.fsm.state import State, StatesGroup
    class _S(StatesGroup):
        wait = State()
    await state.set_state("UserMgmtStates:search_input")
    await state.update_data(admin_add_mode=True)
    await cb.message.edit_text(
        "👨‍💼 شناسه عددی ادمین جدید را بفرست:",
        reply_markup=build([[_btn("❌ لغو", "adm:usr:admins")]]))


@router.callback_query(F.data.regexp(r"^adm:usr:rmadmin:(\d+)$"))
async def cb_rmadmin(cb: CallbackQuery):
    import re
    aid = int(re.match(r"adm:usr:rmadmin:(\d+)", cb.data).group(1))
    main_id = int(__import__("os").getenv("ADMIN_ID", "0"))
    if aid == main_id:
        return await cb.answer("❌ ادمین اصلی را نمی‌توان حذف کرد.", show_alert=True)
    from db_helpers import remove_admin_id
    remove_admin_id(aid)
    await cb.answer(f"✅ ادمین {aid} حذف شد.")
