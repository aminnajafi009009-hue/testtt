"""
handlers/admin_hub.py — بهبودیافته
تغییرات نسبت به نسخه قبلی:
  - adm:broadcast حذف شد — اینجا handle نمی‌شه، در broadcast_handler.py هندل می‌شه (باگ دو مسیر حل شد)
  - اضافه: مدیریت دیسکانت‌ها، لاگ‌ها، بکاپ‌گیری
"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)
router = Router()


def _btn(text, cb): return InlineKeyboardButton(text=text, callback_data=cb)
def _url_btn(text, url): return InlineKeyboardButton(text=text, url=url)
def build(rows): return InlineKeyboardMarkup(inline_keyboard=rows)


# ================================================================
# منوی اصلی ادمین
# ================================================================
def admin_main_kb() -> InlineKeyboardMarkup:
    return build([
        [_btn("📊 آمار‌ها",      "adm:stats"),    _btn("👥 کاربران",   "adm:users")],
        [_btn("📦 سفارش‌ها",     "adm:orders"),   _btn("🎫 پلن‌ها",     "adm:plans")],
        [_btn("💳 پرداخت‌ها",   "adm:payments"), _btn("🌐 پنل‌ها",     "adm:panels")],
        [_btn("📣 همگانی",      "adm:broadcast"),_btn("🎁 تست‌ها",     "adm:tests")],
        [_btn("👮 نمایندگان",  "adm:resellers"),_btn("🏟️ تیکت‌ها",  "adm:tickets")],
        [_btn("⚙️ تنظیمات",     "adm:settings"), _btn("🎁 تخفیف و هدیه","adm:discounts")],
        [_btn("📜 لاگ‌ها",        "adm:logs"),     _btn("💾 بکاپ‌گیری",  "adm:backup")],
    ])


@router.message(Command("admin"))
async def cmd_admin(msg: Message, state: FSMContext):
    from db_helpers import get_admin_ids
    if msg.from_user.id not in get_admin_ids(): return
    await state.clear()
    await msg.answer(
        "🍒 <b>Cherry Admin Panel</b>\nبخش مورد نظر را انتخاب کنید:",
        reply_markup=admin_main_kb(), parse_mode="HTML")


@router.callback_query(F.data == "adm:main")
async def cb_main(cb: CallbackQuery, state: FSMContext):
    from db_helpers import get_admin_ids
    if cb.from_user.id not in get_admin_ids():
        return await cb.answer("⛔ دسترسی ندارید")
    await state.clear()
    await cb.message.edit_text(
        "🍒 <b>Cherry Admin Panel</b>\nبخش مورد نظر را انتخاب کنید:",
        reply_markup=admin_main_kb(), parse_mode="HTML")


# ================================================================
# آمار‌ها
# ================================================================
@router.callback_query(F.data == "adm:stats")
async def cb_stats(cb: CallbackQuery):
    from db_helpers import (
        count_users, count_active_users, count_vip_users,
        count_orders, count_orders_today, count_active_services,
        count_pending_orders, count_new_users_today, get_revenue_today, get_revenue_total,
        count_open_tickets
    )
    text = (
        "📊 <b>آمار ربات</b>\n\n"
        f"👥 کل کاربر: <b>{count_users():,}</b>\n"
        f"✅ کاربر فعال: <b>{count_active_users():,}</b>\n"
        f"⭐ VIP: <b>{count_vip_users():,}</b>\n"
        f"🆕 عضویت امروز: <b>{count_new_users_today():,}</b>\n\n"
        f"📦 کل سفارش: <b>{count_orders():,}</b>\n"
        f"📦 سفارش امروز: <b>{count_orders_today():,}</b>\n"
        f"✅ سرویس فعال: <b>{count_active_services():,}</b>\n"
        f"⏳ در انتظار: <b>{count_pending_orders():,}</b>\n"
        f"🏟️ تیکت باز: <b>{count_open_tickets():,}</b>\n\n"
        f"💰 درآمد امروز: <b>{get_revenue_today():,} تومان</b>\n"
        f"💳 کل درآمد: <b>{get_revenue_total():,} تومان</b>"
    )
    kb = build([[_btn("🔄 به‌روزرسانی", "adm:stats"), _btn("⬅️ برگشت", "adm:main")]])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ================================================================
# پلن‌ها
# ================================================================
@router.callback_query(F.data == "adm:plans")
async def cb_plans(cb: CallbackQuery):
    from db_helpers import get_all_plans
    plans = get_all_plans()
    text = "🎫 <b>مدیریت پلن‌ها</b>\n\n"
    for p in plans[:10]:
        text += f"• <b>{p.get('name')}</b> | {p.get('traffic_gb')}GB/{p.get('duration_days')}روز | {(p.get('price') or 0):,}ت\n"
    if not plans: text += "ℹ️ پلنی وجود ندارد."
    await cb.message.edit_text(text, reply_markup=build([
        [_btn("➕ پلن جدید",   "adm:plans:add"),
         _btn("🗑️ حذف پلن",   "adm:plans:del")],
        [_btn("⬅️ برگشت",           "adm:main")],
    ]), parse_mode="HTML")


# ================================================================
# پنل‌ها
# ================================================================
@router.callback_query(F.data == "adm:panels")
async def cb_panels(cb: CallbackQuery):
    from db_helpers import get_all_panels
    panels = get_all_panels()
    text = "🌐 <b>مدیریت پنل‌ها</b>\n\n"
    for p in panels:
        st = "✅" if p.get("is_active") else "❌"
        text += f"{st} <b>{p.get('name')}</b> ({p.get('panel_type')})\n"
    if not panels: text += "ℹ️ پنلی اضافه نشده."
    await cb.message.edit_text(text, reply_markup=build([
        [_btn("➕ پنل جدید",   "adm:panels:add"),
         _btn("🔧 تست اتصال", "adm:panels:test")],
        [_btn("🗑️ حذف پنل",   "adm:panels:del"),
         _btn("📊 سلامت پنل‌ها","adm:panels:health")],
        [_btn("⬅️ برگشت",           "adm:main")],
    ]), parse_mode="HTML")


# ================================================================
# سفارش‌ها
# ================================================================
@router.callback_query(F.data == "adm:orders")
async def cb_orders(cb: CallbackQuery):
    await cb.message.edit_text("📦 <b>مدیریت سفارش‌ها</b>",
        reply_markup=build([
            [_btn("⏳ در انتظار",  "adm:orders:pending"),
             _btn("✅ تأیید شده",  "adm:orders:active")],
            [_btn("❌ لغو شده",  "adm:orders:cancelled"),
             _btn("📅 امروز",       "adm:orders:today")],
            [_btn("⬅️ برگشت",        "adm:main")],
        ]), parse_mode="HTML")


# ================================================================
# تیکت‌ها
# ================================================================
@router.callback_query(F.data == "adm:tickets")
async def cb_tickets(cb: CallbackQuery):
    from db_helpers import get_tickets
    tickets = get_tickets("open")
    if not tickets:
        text = "🏟️ <b>تیکت‌ها</b>\n\n✔️ تیکت بازی وجود ندارد."
        rows = [[_btn("⬅️ برگشت", "adm:main")]]
    else:
        text = f"🏟️ <b>تیکت‌های باز ({len(tickets)} عدد)</b>\n"
        rows = []
        for t in tickets[:10]:
            uid = t.get('user_id', '?')
            subj = (t.get('subject') or t.get('message', ''))[:40]
            rows.append([_btn(f"💬 #{t.get('id')} — {uid}: {subj}",
                              f"adm:ticket:view:{t.get('id')}")])
        rows.append([_btn("⬅️ برگشت", "adm:main")])
    await cb.message.edit_text(text, reply_markup=build(rows), parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:ticket:view:(\d+)$"))
async def cb_ticket_view(cb: CallbackQuery, state: FSMContext):
    import re
    tid = int(re.match(r"adm:ticket:view:(\d+)", cb.data).group(1))
    from db_helpers import get_ticket
    t = get_ticket(tid)
    if not t:
        return await cb.answer("تیکت یافت نشد")
    text = (
        f"🏟️ <b>تیکت #{tid}</b>\n"
        f"👤 کاربر: <code>{t.get('user_id')}</code>\n"
        f"📌 وضعیت: {t.get('status')}\n"
        f"💡 موضوع: {t.get('subject', '-')}\n\n"
        f"<b>پیام:</b>\n{t.get('message', '')}\n\n"
        + (f"<b>پاسخ:</b>\n{t.get('reply')}" if t.get('reply') else "")
    )
    await state.update_data(reply_ticket_id=tid, reply_user_id=t.get("user_id"))
    await state.set_state("TicketReply")
    from aiogram.fsm.state import State, StatesGroup
    await cb.message.edit_text(text, reply_markup=build([
        [_btn("💬 پاسخ دادن",  f"adm:ticket:reply:{tid}"),
         _btn("✔️ بستن",        f"adm:ticket:close:{tid}")],
        [_btn("⬅️ برگشت",           "adm:tickets")],
    ]), parse_mode="HTML")


@router.callback_query(F.data.regexp(r"^adm:ticket:close:(\d+)$"))
async def cb_ticket_close(cb: CallbackQuery):
    import re
    tid = int(re.match(r"adm:ticket:close:(\d+)", cb.data).group(1))
    from db_helpers import close_ticket
    close_ticket(tid)
    await cb.answer(f"✔️ تیکت #{tid} بسته شد.")


# ================================================================
# نمایندگان
# ================================================================
@router.callback_query(F.data == "adm:resellers")
async def cb_resellers(cb: CallbackQuery):
    await cb.message.edit_text("👮 <b>مدیریت نمایندگان</b>",
        reply_markup=build([
            [_btn("➕ افزودن نماینده", "adm:res:add"),
             _btn("📝 لیست",             "adm:res:list")],
            [_btn("⬅️ برگشت",               "adm:main")],
        ]), parse_mode="HTML")


# ================================================================
# لاگ‌ها
# ================================================================
@router.callback_query(F.data == "adm:logs")
async def cb_logs(cb: CallbackQuery):
    from db_helpers import get_admin_activity_log
    logs = get_admin_activity_log(15)
    text = "📜 <b>لاگ فعالیت‌های ادمین</b>\n\n"
    for log in logs:
        text += f"• <code>{log.get('admin_id')}</code> → <b>{log.get('action')}</b> | {str(log.get('extra',''))[:40]}\n"
    if not logs: text += "ℹ️ لاگی وجود ندارد."
    await cb.message.edit_text(text, reply_markup=build([[_btn("⬅️ برگشت", "adm:main")]]), parse_mode="HTML")


# ================================================================
# بکاپ‌گیری
# ================================================================
@router.callback_query(F.data == "adm:backup")
async def cb_backup(cb: CallbackQuery, bot):
    from db_helpers import get_admin_ids
    await cb.answer("⏳ در حال تهیه بکاپ...")
    try:
        import aiofiles
        db_path = "cherry.db"
        import os
        if os.path.exists(db_path):
            async with aiofiles.open(db_path, "rb") as f:
                data = await f.read()
            from io import BytesIO
            from aiogram.types import BufferedInputFile
            for aid in get_admin_ids()[:2]:
                await bot.send_document(
                    aid,
                    BufferedInputFile(data, filename="cherry_backup.db"),
                    caption="💾 بکاپ پایگاه داده")
        else:
            await cb.message.answer("ℹ️ فایل DB لوکال یافت نشد (Turso remote)."
                                    " بکاپ از داشبورد تورسو تهیه کنید.")
    except ImportError:
        await cb.message.answer("ℹ️ بکاپ یا DB لوکال موجود نیست.")
    except Exception as e:
        await cb.message.answer(f"❌ خطا: {e}")
