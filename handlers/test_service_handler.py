"""
handlers/test_service_handler.py
سرویس تست پیشرفته:
 - چندین پلن تست از چندین پنل مختلف
 - کنترل دقیق تعداد تست هر کاربر
 - تست با زمان‌بندی و حجم داده
 - ادمین: مدیریت پلن‌های تست
"""
from __future__ import annotations
import json
import logging
import time
from typing import Optional
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)
router = Router()


def _btn(t, c): return InlineKeyboardButton(text=t, callback_data=c)
def build(r): return InlineKeyboardMarkup(inline_keyboard=r)


class TestStates(StatesGroup):
    add_name    = State()
    add_panel   = State()
    add_traffic = State()
    add_hours   = State()
    add_label   = State()
    confirm     = State()


# ================================================================
# Test Plan — ساختار داده
# ================================================================
# پلن‌های تست در DB/settings به صورت JSON ذخیره می‌شوند، key="test_plans"

def _get_test_plans() -> list[dict]:
    try:
        from db_helpers import get_setting
        raw = get_setting("test_plans", "[]")
        return json.loads(raw)
    except Exception:
        return []


def _save_test_plans(plans: list[dict]):
    try:
        from db_helpers import set_setting
        set_setting("test_plans", json.dumps(plans))
    except Exception as e:
        logger.error("_save_test_plans: %s", e)


def _get_user_test_count(user_id: int) -> int:
    try:
        from db_helpers import get_setting
        raw = get_setting(f"test_count_{user_id}", "0")
        return int(raw)
    except Exception:
        return 0


def _inc_user_test_count(user_id: int):
    count = _get_user_test_count(user_id)
    try:
        from db_helpers import set_setting
        set_setting(f"test_count_{user_id}", str(count + 1))
    except Exception:
        pass


def _max_test_per_user() -> int:
    try:
        from db_helpers import get_setting
        return int(get_setting("test_max_per_user", "1"))
    except Exception:
        return 1


def _test_enabled() -> bool:
    try:
        from db_helpers import get_setting
        return get_setting("test_service_enabled", "1") == "1"
    except Exception:
        return True


# ================================================================
# کیبورد ادمین
# ================================================================
def test_admin_kb() -> InlineKeyboardMarkup:
    plans = _get_test_plans()
    enabled = _test_enabled()
    e = "✅" if enabled else "❌"
    rows = [
        [_btn(f"{e} فعال/غیرفعال سرویس تست",  "test:admin:toggle")],
        [_btn(f"➕ افزودن پلن تست",  "test:admin:add")],
    ]
    for i, p in enumerate(plans):
        rows.append([
            _btn(f"🎁 {p['label']}", f"test:admin:view:{i}"),
            _btn("❌", f"test:admin:del:{i}"),
        ])
    rows.append([_btn("⬅️ برگشت", "adm:main")])
    return build(rows)


@router.callback_query(F.data == "adm:tests")
async def cb_tests_admin(cb: CallbackQuery):
    plans = _get_test_plans()
    text = (
        f"🎁 <b>مدیریت سرویس تست</b>\n\n"
        f"پلن‌ها: {len(plans)} عدد\n"
        f"حداکثر هر کاربر: {_max_test_per_user()} تست"
    )
    await cb.message.edit_text(text, reply_markup=test_admin_kb(), parse_mode="HTML")


@router.callback_query(F.data == "test:admin:toggle")
async def cb_test_toggle(cb: CallbackQuery):
    from db_helpers import get_setting, set_setting
    cur = get_setting("test_service_enabled", "1")
    set_setting("test_service_enabled", "0" if cur == "1" else "1")
    await cb.answer("✅ تغییر کرد")
    await cb.message.edit_reply_markup(reply_markup=test_admin_kb())


@router.callback_query(F.data == "test:admin:add")
async def cb_test_add(cb: CallbackQuery, state: FSMContext):
    await state.set_state(TestStates.add_label)
    await cb.message.answer("🎁 نام نمایشی پلن تست را وارد کنید:\nمثال: تست یک روزه | تست VIP")


@router.message(TestStates.add_label)
async def fsm_test_label(msg: Message, state: FSMContext):
    await state.update_data(label=msg.text.strip())
    await state.set_state(TestStates.add_traffic)
    await msg.answer("📊 حجم داده به GB وارد کنید:\nمثال: 0.5 یا 1")


@router.message(TestStates.add_traffic)
async def fsm_test_traffic(msg: Message, state: FSMContext):
    try:
        gb = float(msg.text.strip())
    except Exception:
        await msg.answer("⚠️ عدد معتبر وارد کنید")
        return
    await state.update_data(traffic_gb=gb)
    await state.set_state(TestStates.add_hours)
    await msg.answer("⏰ مدت اعتبار به ساعت وارد کنید:\nمثال: 24 یا 48")


@router.message(TestStates.add_hours)
async def fsm_test_hours(msg: Message, state: FSMContext):
    try:
        hours = int(msg.text.strip())
    except Exception:
        await msg.answer("⚠️ عدد صحیح وارد کنید")
        return
    await state.update_data(hours=hours)
    await state.set_state(TestStates.add_panel)
    # لیست پنل‌ها
    from db_helpers import get_all_panels
    panels = get_all_panels()
    if not panels:
        await msg.answer("⚠️ پنلی تعریف نشده. ابتدا پنل اضافه کنید.")
        await state.clear()
        return
    rows = [[_btn(f"🌐 {p['name']} ({p['panel_type']})", f"test:panel_sel:{p['id']}")]
            for p in panels]
    rows.append([_btn("🔀 هر پنلی (تصادفی)", "test:panel_sel:random")])
    await msg.answer("🌐 پنل منبع تست را انتخاب کنید:",
                     reply_markup=build(rows))


@router.callback_query(F.data.startswith("test:panel_sel:"), TestStates.add_panel)
async def cb_test_panel_sel(cb: CallbackQuery, state: FSMContext):
    panel_id = cb.data.replace("test:panel_sel:", "")
    await state.update_data(panel_id=panel_id)
    d = await state.get_data()
    # ذخیره پلن
    plans = _get_test_plans()
    plans.append({
        "label": d.get("label", "تست"),
        "traffic_gb": d.get("traffic_gb", 1),
        "hours": d.get("hours", 24),
        "panel_id": panel_id,
        "created_at": int(time.time()),
    })
    _save_test_plans(plans)
    await state.clear()
    await cb.message.answer(
        f"✅ پلن تست <b>{d.get('label')}</b> اضافه شد:\n"
        f"📊 حجم: {d.get('traffic_gb')} GB — ⏰ مدت: {d.get('hours')} ساعت\n"
        f"🌐 پنل: {panel_id}",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("test:admin:del:"))
async def cb_test_del(cb: CallbackQuery):
    idx = int(cb.data.split(":")[-1])
    plans = _get_test_plans()
    if 0 <= idx < len(plans):
        name = plans[idx].get("label", "")
        plans.pop(idx)
        _save_test_plans(plans)
        await cb.answer(f"❌ پلن '{name}' حذف شد")
    await cb.message.edit_reply_markup(reply_markup=test_admin_kb())


# ================================================================
# سرویس تست — سمت کاربر
# ================================================================
def test_user_kb(plans: list) -> InlineKeyboardMarkup:
    rows = []
    for i, p in enumerate(plans):
        rows.append([_btn(
            f"🎁 {p['label']} | {p['traffic_gb']}GB | {p['hours']}h",
            f"test:get:{i}"
        )])
    return build(rows)


@router.callback_query(F.data == "test:menu")
async def cb_test_menu(cb: CallbackQuery):
    if not _test_enabled():
        await cb.answer("❌ سرویس تست فعلاً غیرفعال است.", show_alert=True)
        return
    plans = _get_test_plans()
    if not plans:
        await cb.answer("⚠️ در حال حاضر پلن تستی تعریف نشده.", show_alert=True)
        return
    user_id = cb.from_user.id
    max_t = _max_test_per_user()
    cur = _get_user_test_count(user_id)
    if cur >= max_t:
        await cb.answer(f"❌ شما قبلاً از سرویس تست استفاده کرده‌اید ({cur}/{max_t}).", show_alert=True)
        return
    text = (
        f"🎁 <b>سرویس تست رایگان</b>\n\n"
        f"تعداد استفاده: {cur}/{max_t}\n\n"
        "پلن دلخواه را انتخاب کنید:"
    )
    await cb.message.edit_text(text, reply_markup=test_user_kb(plans), parse_mode="HTML")


@router.callback_query(F.data.startswith("test:get:"))
async def cb_test_get(cb: CallbackQuery):
    idx = int(cb.data.split(":")[-1])
    plans = _get_test_plans()
    if idx >= len(plans):
        await cb.answer("❌ پلن یافت نشد")
        return
    plan = plans[idx]
    user_id = cb.from_user.id
    max_t = _max_test_per_user()
    cur = _get_user_test_count(user_id)
    if cur >= max_t:
        await cb.answer("❌ سهمیه تست تمام شده", show_alert=True)
        return
    await cb.message.edit_text("⏳ در حال ساخت سرویس تست...")
    try:
        result = await _create_test_service(user_id, plan)
        _inc_user_test_count(user_id)
        await cb.message.edit_text(
            f"✅ <b>سرویس تست آماده شد!</b>\n\n"
            f"📊 حجم: {plan['traffic_gb']} GB\n"
            f"⏰ مدت: {plan['hours']} ساعت\n\n"
            f"🔗 لینک سرویس:\n<code>{result.get('subscription_url', result.get('config', 'N/A'))}</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        await cb.message.edit_text(f"❌ خطا در ساخت تست: {e}")


async def _create_test_service(user_id: int, plan: dict) -> dict:
    """
    سرویس تست روی پنل مناسب می‌سازد.
    در صورت panel_id='random'، از اولین پنل فعال استفاده میشه.
    """
    from panels import PanelManager
    pm = PanelManager()
    panel_id = plan.get("panel_id", "random")
    username = f"test_{user_id}_{int(time.time())}"
    hours = plan.get("hours", 24)
    traffic_gb = plan.get("traffic_gb", 1)
    if panel_id == "random":
        result = await pm.create_user_on_any_panel(
            username=username, data_gb=traffic_gb, expire_hours=hours
        )
    else:
        result = await pm.create_user_on_panel(
            panel_id=int(panel_id), username=username,
            data_gb=traffic_gb, expire_hours=hours
        )
    return result or {"config": "N/A"}
