"""
handlers/admin_payments_hub.py
مدیریت کامل روش‌های پرداخت — فیکسشده:
 - ImportError: AdminStates از admin_hub برطرف شد
 - _pm() دیگر از bot اشتباه import نمی‌کند — اكنون singleton درست
 - FSM handler‌های PayGo اضافه شد
 - f-string backslash‌ها فیکس شده
"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from handlers.admin_hub import AdminStates, build, _btn

logger = logging.getLogger(__name__)
router = Router()

BACK_PAYMENTS = "adm:payments"


# ================================================================
# سینگلتون PaymentManager — فیکس اصلی
# قبلاً: from bot import pm  → خطا (bot.py وجود ندارد)
# اکنون: lazy singleton با db_helpers
# ================================================================
_pm_instance = None

def _pm():
    global _pm_instance
    if _pm_instance is None:
        from payment_manager_v3 import PaymentManager
        from db_helpers import get_setting, set_setting
        _pm_instance = PaymentManager(
            db_get_fn=get_setting,
            db_set_fn=set_setting,
        )
        _pm_instance.load()
    return _pm_instance


# ================================================================
# استرینگ خلاصه
# ================================================================
def payments_summary_text() -> str:
    return f"💳 <b>روش\u200cهای پرداخت</b>\n\n{_pm().summary()}"


# ================================================================
# کیبورد اصلی
# ================================================================
def payments_main_kb() -> InlineKeyboardMarkup:
    pm = _pm()
    e = lambda b: "✅" if b else "❌"
    return build([
        [_btn(f"{e(pm.card.enabled)} 💳 کارت\u200cبه\u200cکارت دستی",  "adm:pm:card")],
        [_btn(f"{e(pm.wallet.enabled)} 💰 کیف پول",              "adm:pm:wallet")],
        [_btn(f"{e(pm.uniquepay.enabled)} 🌐 پرداخت آنلاین (UniquePay)", "adm:pm:uniquepay")],
        [_btn(f"📊 ارز دیجیتال ({len(pm.enabled_cryptos)} فعال)", "adm:pm:crypto")],
        [_btn(f"{e(pm.paygo.enabled)} 🔄 پرداخت به ازای مصرف",  "adm:pm:paygo")],
        [_btn("⬅️ برگشت", "adm:main")],
    ])


@router.callback_query(F.data == "adm:payments")
async def cb_payments_main(cb: CallbackQuery):
    await cb.message.edit_text(payments_summary_text(),
        reply_markup=payments_main_kb(), parse_mode="HTML")


# ================================================================
# کارت\u200cبه\u200cکارت دستی
# ================================================================
def card_kb() -> InlineKeyboardMarkup:
    pm = _pm()
    e = lambda b: "✅" if b else "❌"
    return build([
        [_btn(f"{e(pm.card.enabled)} فعال/غیرفعال", "adm:pm:card:toggle")],
        [_btn("💳 شماره کارت",  "adm:pm:card:number"),  _btn("👤 نام صاحب",   "adm:pm:card:owner")],
        [_btn("🏦 نام بانک",   "adm:pm:card:bank"),    _btn(f"{e(pm.card.receipt_required)} رسید اجباری","adm:pm:card:receipt")],
        [_btn(f"{e(pm.card.auto_confirm)} تأیید خودکار","adm:pm:card:autoconfirm")],
        [_btn("⬅️ برگشت", BACK_PAYMENTS)],
    ])

@router.callback_query(F.data == "adm:pm:card")
async def cb_card(cb: CallbackQuery):
    pm = _pm()
    c = pm.card
    enabled_text = "✅ فعال" if c.enabled else "❌ غیرفعال"
    receipt_text = "✅" if c.receipt_required else "❌"
    autoconfirm_text = "✅" if c.auto_confirm else "❌ نیاز تأیید ادمین"
    text = (
        "💳 <b>تنظیمات کارت\u200cبه\u200cکارت دستی</b>\n\n"
        f"وضعیت: {enabled_text}\n"
        f"شماره کارت: <code>{c.card_number or 'تنظیم نشده'}</code>\n"
        f"صاحب: {c.owner_name or 'تنظیم نشده'}\n"
        f"بانک: {c.bank_name or 'تنظیم نشده'}\n"
        f"رسید اجباری: {receipt_text}\n"
        f"تأیید خودکار: {autoconfirm_text}"
    )
    await cb.message.edit_text(text, reply_markup=card_kb(), parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:card:toggle")
async def cb_card_toggle(cb: CallbackQuery):
    _pm().update_card(enabled=not _pm().card.enabled)
    await cb_card(cb)

@router.callback_query(F.data == "adm:pm:card:receipt")
async def cb_card_receipt(cb: CallbackQuery):
    _pm().update_card(receipt_required=not _pm().card.receipt_required)
    await cb_card(cb)

@router.callback_query(F.data == "adm:pm:card:autoconfirm")
async def cb_card_autoconfirm(cb: CallbackQuery):
    _pm().update_card(auto_confirm=not _pm().card.auto_confirm)
    await cb_card(cb)

@router.callback_query(F.data == "adm:pm:card:number")
async def cb_card_number(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_card_number)
    await cb.message.answer("💳 شماره کارت جدید را وارد کنید:")

@router.message(AdminStates.pm_card_number)
async def fsm_card_number(msg: Message, state: FSMContext):
    _pm().update_card(card_number=msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ شماره کارت تنظیم شد: <code>{msg.text.strip()}</code>", parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:card:owner")
async def cb_card_owner(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_card_owner)
    await cb.message.answer("👤 نام صاحب کارت را وارد کنید:")

@router.message(AdminStates.pm_card_owner)
async def fsm_card_owner(msg: Message, state: FSMContext):
    _pm().update_card(owner_name=msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ نام صاحب کارت: <b>{msg.text.strip()}</b>", parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:card:bank")
async def cb_card_bank(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_card_bank)
    await cb.message.answer("🏦 نام بانک را وارد کنید:")

@router.message(AdminStates.pm_card_bank)
async def fsm_card_bank(msg: Message, state: FSMContext):
    _pm().update_card(bank_name=msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ نام بانک: <b>{msg.text.strip()}</b>", parse_mode="HTML")


# ================================================================
# UniquePay
# ================================================================
def uniquepay_kb() -> InlineKeyboardMarkup:
    pm = _pm()
    u = pm.uniquepay
    e = lambda b: "✅" if b else "❌"
    return build([
        [_btn(f"{e(u.enabled)} فعال/غیرفعال",        "adm:pm:up:toggle")],
        [_btn("🔑 Business Token",              "adm:pm:up:token")],
        [_btn("🔗 Redirect URL",                "adm:pm:up:redir")],
        [_btn(f"{e(u.use_telegram_link)} لینک تلگرام","adm:pm:up:tglink"),
         _btn(f"{e(u.show_card_white_label)} نمایش کارت","adm:pm:up:wl")],
        [_btn(f"{e(u.auto_confirm)} تأیید خودکار",  "adm:pm:up:auto"),
         _btn(f"{e(u.use_ddbot_compat)} DDBot سازگار","adm:pm:up:ddbot")],
        [_btn("🧪 تست اتصال",                "adm:pm:up:test")],
        [_btn("⬅️ برگشت", BACK_PAYMENTS)],
    ])

def uniquepay_text() -> str:
    u = _pm().uniquepay
    token_display = ('*'*8 + u.business_token[-4:]) if u.business_token else 'تنظیم نشده'
    enabled_text = "✅ فعال" if u.enabled else "❌ غیرفعال"
    return (
        "🌐 <b>تنظیمات UniquePay</b>\n\n"
        f"وضعیت: {enabled_text}\n"
        f"Token: <code>{token_display}</code>\n"
        f"Redirect: {u.redirect_url or 'تنظیم نشده'}\n"
        f"Callback: {u.callback_url or 'تنظیم نشده'}\n"
        f"حداقل مبلغ: {u.min_amount:,} تومان"
    )

@router.callback_query(F.data == "adm:pm:uniquepay")
async def cb_uniquepay(cb: CallbackQuery):
    await cb.message.edit_text(uniquepay_text(), reply_markup=uniquepay_kb(), parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:up:toggle")
async def cb_up_toggle(cb: CallbackQuery):
    _pm().update_uniquepay(enabled=not _pm().uniquepay.enabled)
    await cb.message.edit_text(uniquepay_text(), reply_markup=uniquepay_kb(), parse_mode="HTML")

@router.callback_query(F.data.in_({"adm:pm:up:tglink","adm:pm:up:wl","adm:pm:up:auto","adm:pm:up:ddbot"}))
async def cb_up_bools(cb: CallbackQuery):
    field_map = {
        "adm:pm:up:tglink": "use_telegram_link",
        "adm:pm:up:wl":     "show_card_white_label",
        "adm:pm:up:auto":   "auto_confirm",
        "adm:pm:up:ddbot":  "use_ddbot_compat",
    }
    f = field_map[cb.data]
    _pm().update_uniquepay(**{f: not getattr(_pm().uniquepay, f)})
    await cb.message.edit_text(uniquepay_text(), reply_markup=uniquepay_kb(), parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:up:token")
async def cb_up_token(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_uniquepay_token)
    await cb.message.answer("🔑 Business Token جدید را وارد کنید:\n⚠️ فقط در سرور نگه\u200cدارید!")

@router.message(AdminStates.pm_uniquepay_token)
async def fsm_up_token(msg: Message, state: FSMContext):
    _pm().update_uniquepay(business_token=msg.text.strip())
    await state.clear()
    await msg.answer("✅ Business Token ذخیره شد.")
    try: await msg.delete()
    except Exception: pass

@router.callback_query(F.data == "adm:pm:up:redir")
async def cb_up_redir(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_uniquepay_redir)
    await cb.message.answer("🔗 Redirect URL را وارد کنید:\nمثال: https://t.me/YourBot")

@router.message(AdminStates.pm_uniquepay_redir)
async def fsm_up_redir(msg: Message, state: FSMContext):
    _pm().update_uniquepay(redirect_url=msg.text.strip())
    await state.clear()
    await msg.answer(f"✅ Redirect URL: {msg.text.strip()}")

@router.callback_query(F.data == "adm:pm:up:test")
async def cb_up_test(cb: CallbackQuery):
    client = _pm().get_uniquepay_client()
    if not client:
        await cb.answer("❌ UniquePay فعال نیست یا توکن تنظیم نشده.", show_alert=True)
        return
    await cb.answer("⏳ در حال تست...")
    from uniquepay import make_hash_id, UniquePayError
    try:
        inv = await client.create_invoice(
            hash_id=make_hash_id(0),
            amount=50001,
            redirect_url=_pm().uniquepay.redirect_url or "https://t.me/",
        )
        await cb.message.answer(
            f"✅ <b>اتصال برقرار شد!</b>\n"
            f"refId: <code>{inv['ref_id']}</code>\n"
            f"<a href='{inv['payment_link']}'>🔗 لینک پرداخت</a>",
            parse_mode="HTML"
        )
    except UniquePayError as e:
        await cb.message.answer(f"❌ خطا: [{e.code}] {e.message}", parse_mode="HTML")
    except Exception as ex:
        await cb.message.answer(f"❌ {ex}")


# ================================================================
# ارز دیجیتال
# ================================================================
def crypto_list_kb() -> InlineKeyboardMarkup:
    pm = _pm()
    rows = []
    for c in pm.cryptos:
        e = "✅" if c.enabled else "❌"
        rows.append([_btn(f"{e} {c.emoji} {c.symbol} ({c.network})", f"adm:pm:cry:detail:{c.symbol}")])
    rows.append([_btn("➕ افزودن ارز جدید", "adm:pm:cry:add")])
    rows.append([_btn("⬅️ برگشت", BACK_PAYMENTS)])
    return build(rows)

@router.callback_query(F.data == "adm:pm:crypto")
async def cb_crypto(cb: CallbackQuery):
    pm = _pm()
    enabled = len(pm.enabled_cryptos)
    text = f"📊 <b>ارزهای دیجیتال</b>\n{enabled} ارز فعال / {len(pm.cryptos)} کل"
    await cb.message.edit_text(text, reply_markup=crypto_list_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm:pm:cry:detail:"))
async def cb_crypto_detail(cb: CallbackQuery):
    sym = cb.data.split(":")[-1]
    pm = _pm()
    c = pm.get_crypto(sym)
    if not c:
        await cb.answer("❌ ارز یافت نشد")
        return
    enabled_text = "✅ فعال" if c.enabled else "❌ غیرفعال"
    text = (
        f"{c.emoji} <b>{c.name} ({c.symbol})</b>\n\n"
        f"شبکه: {c.network}\n"
        f"وضعیت: {enabled_text}\n"
        f"آدرس کیف پول: <code>{c.wallet or 'تنظیم نشده'}</code>\n"
        f"مارجین: {c.margin_percent}%"
    )
    kb = build([
        [_btn("✅/❌ فعال/غیرفعال", f"adm:pm:cry:toggle:{sym}"),
         _btn("💳 آدرس کیف پول", f"adm:pm:cry:wallet:{sym}")],
        [_btn("💹 مارجین", f"adm:pm:cry:margin:{sym}"),
         _btn("🗑️ حذف", f"adm:pm:cry:del:{sym}")],
        [_btn("⬅️ برگشت", "adm:pm:crypto")],
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("adm:pm:cry:toggle:"))
async def cb_crypto_toggle(cb: CallbackQuery):
    sym = cb.data.split(":")[-1]
    result = _pm().toggle_crypto(sym)
    status = "فعال" if result else "غیرفعال"
    await cb.answer(f"✅ {sym}: {status}")
    await cb_crypto_detail(cb)

@router.callback_query(F.data.startswith("adm:pm:cry:del:"))
async def cb_crypto_del(cb: CallbackQuery):
    sym = cb.data.split(":")[-1]
    _pm().remove_crypto(sym)
    await cb.answer(f"❌ {sym} حذف شد")
    await cb_crypto(cb)

@router.callback_query(F.data.startswith("adm:pm:cry:wallet:"))
async def cb_crypto_wallet(cb: CallbackQuery, state: FSMContext):
    sym = cb.data.split(":")[-1]
    await state.update_data(crypto_sym=sym)
    await state.set_state(AdminStates.pm_crypto_wallet)
    await cb.message.answer(f"💳 آدرس کیف پول {sym} را وارد کنید:")

@router.message(AdminStates.pm_crypto_wallet)
async def fsm_crypto_wallet(msg: Message, state: FSMContext):
    d = await state.get_data()
    sym = d.get("crypto_sym", "")
    if sym and not d.get("sym"):  # ویرایش کیف پول ارز موجود
        _pm().update_crypto(sym, wallet=msg.text.strip())
        await state.clear()
        await msg.answer("✅ آدرس ذخیره شد.")
        return
    # اضافه کردن ارز جدید
    sym = d.get("sym") or d.get("crypto_sym", "")
    wallet = "" if msg.text.strip() == "." else msg.text.strip()
    _pm().add_crypto(
        symbol=sym,
        name=d.get("name", sym),
        network=d.get("network", ""),
        emoji=d.get("emoji", "💰"),
        wallet=wallet,
    )
    await state.clear()
    await msg.answer(f"✅ ارز <b>{sym}</b> اضافه شد!", parse_mode="HTML")


# --- اضافه کردن ارز جدید ---
@router.callback_query(F.data == "adm:pm:cry:add")
async def cb_crypto_add_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_crypto_symbol)
    await cb.message.answer(
        "➕ اضافه ارز جدید\n\n"
        "ابتدا سیمبول ارز را وارد کنید:\n"
        "مثال: USDT یا BTC"
    )

@router.message(AdminStates.pm_crypto_symbol)
async def fsm_crypto_symbol(msg: Message, state: FSMContext):
    await state.update_data(sym=msg.text.strip().upper())
    await state.set_state(AdminStates.pm_crypto_name)
    await msg.answer("نام کامل ارز را وارد کنید:\nمثال: Tether")

@router.message(AdminStates.pm_crypto_name)
async def fsm_crypto_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await state.set_state(AdminStates.pm_crypto_network)
    await msg.answer("شبکه را وارد کنید:\nمثال: TRC20 / ERC20 / BSC")

@router.message(AdminStates.pm_crypto_network)
async def fsm_crypto_network(msg: Message, state: FSMContext):
    await state.update_data(network=msg.text.strip())
    await state.set_state(AdminStates.pm_crypto_emoji)
    await msg.answer("ایموجی مناسب انتخاب کنید:\nمثال: 🟢")

@router.message(AdminStates.pm_crypto_emoji)
async def fsm_crypto_emoji(msg: Message, state: FSMContext):
    d = await state.get_data()
    await state.update_data(emoji=msg.text.strip())
    await state.update_data(crypto_sym=d.get("sym", ""))
    await state.set_state(AdminStates.pm_crypto_wallet)
    await msg.answer("آدرس کیف پول را وارد کنید:\n(برای فعلاً خالی بگذارید: . بفرستید)")


# ================================================================
# Pay As You Go — کامل با FSM handler‌ها
# ================================================================
def paygo_kb() -> InlineKeyboardMarkup:
    pm = _pm()
    p = pm.paygo
    e = lambda b: "✅" if b else "❌"
    return build([
        [_btn(f"{e(p.enabled)} فعال/غیرفعال",         "adm:pm:pg:toggle")],
        [_btn(f"💰 قیمت هر GB: {p.price_per_gb:,}",   "adm:pm:pg:gb"),
         _btn(f"💰 قیمت هر روز: {p.price_per_day:,}","adm:pm:pg:day")],
        [_btn(f"⚠️ حداقل موجودی: {p.min_balance:,}","adm:pm:pg:min")],
        [_btn(f"🔕 توقف زیر: {p.auto_suspend_below:,}","adm:pm:pg:suspend")],
        [_btn("⬅️ برگشت", BACK_PAYMENTS)],
    ])

def paygo_text() -> str:
    p = _pm().paygo
    enabled_text = "✅ فعال" if p.enabled else "❌ غیرفعال"
    return (
        "🔄 <b>Pay As You Go</b>\n\n"
        f"وضعیت: {enabled_text}\n"
        f"قیمت هر GB: {p.price_per_gb:,} تومان\n"
        f"قیمت هر روز: {p.price_per_day:,} تومان\n"
        f"حداقل موجودی: {p.min_balance:,} تومان\n"
        f"توقف زیر: {p.auto_suspend_below:,} تومان"
    )

@router.callback_query(F.data == "adm:pm:paygo")
async def cb_paygo(cb: CallbackQuery):
    await cb.message.edit_text(paygo_text(), reply_markup=paygo_kb(), parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:pg:toggle")
async def cb_pg_toggle(cb: CallbackQuery):
    _pm().update_paygo(enabled=not _pm().paygo.enabled)
    await cb.message.edit_text(paygo_text(), reply_markup=paygo_kb(), parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:pg:gb")
async def cb_pg_gb(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_paygo_gb)
    p = _pm().paygo
    await cb.message.answer(
        f"💰 <b>قیمت هر GB</b>\nفعلی: <b>{p.price_per_gb:,} تومان</b>\n\nعدد جدید وارد کنید:",
        parse_mode="HTML"
    )

@router.message(AdminStates.pm_paygo_gb)
async def fsm_pg_gb(msg: Message, state: FSMContext):
    try:
        val = int(msg.text.strip().replace(",", ""))
        if val < 0: raise ValueError
    except Exception:
        return await msg.answer("❌ عدد نامعتبر")
    _pm().update_paygo(price_per_gb=val)
    await state.clear()
    await msg.answer(f"✅ قیمت هر GB: <b>{val:,} تومان</b>", parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:pg:day")
async def cb_pg_day(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_paygo_day)
    p = _pm().paygo
    await cb.message.answer(
        f"💰 <b>قیمت هر روز</b>\nفعلی: <b>{p.price_per_day:,} تومان</b>\n(0 = غیرفعال)\n\nعدد جدید:",
        parse_mode="HTML"
    )

@router.message(AdminStates.pm_paygo_day)
async def fsm_pg_day(msg: Message, state: FSMContext):
    try:
        val = int(msg.text.strip().replace(",", ""))
        if val < 0: raise ValueError
    except Exception:
        return await msg.answer("❌ عدد نامعتبر")
    _pm().update_paygo(price_per_day=val)
    await state.clear()
    await msg.answer(f"✅ قیمدت هر روز: <b>{val:,} تومان</b>", parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:pg:min")
async def cb_pg_min(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_paygo_min)
    p = _pm().paygo
    await cb.message.answer(
        f"⚠️ <b>حداقل موجودی</b>\nفعلی: <b>{p.min_balance:,} تومان</b>\n\nمبلغ جدید:",
        parse_mode="HTML"
    )

@router.message(AdminStates.pm_paygo_min)
async def fsm_pg_min(msg: Message, state: FSMContext):
    try:
        val = int(msg.text.strip().replace(",", ""))
        if val < 0: raise ValueError
    except Exception:
        return await msg.answer("❌ عدد نامعتبر")
    _pm().update_paygo(min_balance=val)
    await state.clear()
    await msg.answer(f"✅ حداقل موجودی: <b>{val:,} تومان</b>", parse_mode="HTML")

@router.callback_query(F.data == "adm:pm:pg:suspend")
async def cb_pg_suspend(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.pm_paygo_suspend)
    p = _pm().paygo
    await cb.message.answer(
        f"🔕 <b>توقف زیر</b>\nفعلی: <b>{p.auto_suspend_below:,} تومان</b>\n\nمبلغ جدید:",
        parse_mode="HTML"
    )

@router.message(AdminStates.pm_paygo_suspend)
async def fsm_pg_suspend(msg: Message, state: FSMContext):
    try:
        val = int(msg.text.strip().replace(",", ""))
        if val < 0: raise ValueError
    except Exception:
        return await msg.answer("❌ عدد نامعتبر")
    _pm().update_paygo(auto_suspend_below=val)
    await state.clear()
    await msg.answer(f"✅ توقف زیر: <b>{val:,} تومان</b>", parse_mode="HTML")
