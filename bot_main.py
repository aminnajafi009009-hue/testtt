"""
bot_main.py — Cherry VPN Bot v3 — بهبودیافته
تمام روتر‌های جدید register شدند:
  - admin_users_handler
  - admin_text_editor (ویرایشگر متن‌ها + قابلیت‌ها)
  - admin_discount_handler (تخفیف + هدیه)
  - scheduler (وظایف پس‌زمینه)
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ——— متغیرهای محیطی ———
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_ID       = int(os.getenv("ADMIN_ID", "0"))
WEBAPP_URL     = os.getenv("WEBAPP_URL", "")
ADMIN_SECRET   = os.getenv("ADMIN_API_SECRET", "cherry_secret_change_me")


def is_admin(user_id: int) -> bool:
    from db_helpers import get_admin_ids
    return user_id in get_admin_ids()


async def on_startup(bot: Bot):
    from db_helpers import init_db
    await asyncio.to_thread(init_db)
    me = await bot.get_me()
    logger.info("✅ Bot started: @%s", me.username)
    for aid in [ADMIN_ID]:
        if aid:
            try:
                await bot.send_message(
                    aid,
                    "✅ <b>Cherry VPN Bot v3</b> با موفقیت راه‌اندازی شد.\n"
                    "🌸 تمام بهبودها از میرزابات اعمال شد.",
                    parse_mode="HTML")
            except Exception: pass
    # شروع اسکجولر در بکگراوند
    asyncio.create_task(_start_scheduler(bot))


async def _start_scheduler(bot: Bot):
    from scheduler import run_all
    logger.info("⏰ Scheduler شروع شد")
    await run_all(bot)


async def on_shutdown(bot: Bot):
    logger.info("🔴 Bot shutting down...")


def make_bot() -> Bot:
    return Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def make_dp() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    return dp


def register_all_routers(dp: Dispatcher):
    # ——— Handler های ادمین ———
    from handlers.admin_hub              import router as admin_router
    from handlers.admin_payments_hub     import router as payments_router
    from handlers.admin_settings_hub     import router as settings_router
    from handlers.broadcast_handler      import router as broadcast_router  # FIXED: single entry
    from handlers.test_service_handler   import router as test_router
    from handlers.uniquepay_handler      import router as uniquepay_router
    from handlers.admin_users_handler    import router as users_router    # NEW: مدیریت کاربران
    from handlers.admin_text_editor      import router as text_editor_router  # NEW: ویرایشگر
    from handlers.admin_discount_handler import router as discount_router   # NEW: تخفیف‌ها

    dp.include_router(broadcast_router)   # اول: adm:broadcast را اینجا هندل کن
    dp.include_router(admin_router)
    dp.include_router(payments_router)
    dp.include_router(settings_router)
    dp.include_router(test_router)
    dp.include_router(uniquepay_router)
    dp.include_router(users_router)
    dp.include_router(text_editor_router)
    dp.include_router(discount_router)

    logger.info("✅ تمام روتر‌ها register شدند")


# ——— روتر رویتین /start, /admin ———
start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(msg: Message):
    from db_helpers import get_or_create_user, get_text, get_setting, get_force_join_channels
    import re

    # بررسی رفرال
    referrer_id = None
    match = re.match(r"^/start ref(\d+)", msg.text or "")
    if match:
        referrer_id = int(match.group(1))
        if referrer_id == msg.from_user.id:
            referrer_id = None

    user = get_or_create_user(
        user_id=msg.from_user.id,
        username=msg.from_user.username or "",
        full_name=msg.from_user.full_name or "",
        referrer_id=referrer_id,
    )

    # تعمیرات
    if get_setting("feat:maintenance", False) and not is_admin(msg.from_user.id):
        await msg.answer(
            get_text("maintenance",
                     name=msg.from_user.first_name or "")
            or "🛠️ ربات در حال تعمیرات است. لطفاً بعداً تلاش کنید.")
        return

    # جوین اجباری
    channels = get_force_join_channels()
    if channels and get_setting("feat:force_join", True) and not is_admin(msg.from_user.id):
        not_joined = []
        for ch in channels:
            try:
                member = await msg.bot.get_chat_member(ch, msg.from_user.id)
                if member.status in ("left", "kicked"):
                    not_joined.append(ch)
            except Exception:
                pass
        if not_joined:
            rows = [[InlineKeyboardButton(text=f"🔔 عضویت در کانال {ch}",
                                         url=f"https://t.me/{ch.lstrip('@')}")]
                    for ch in not_joined]
            rows.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_join")])
            await msg.answer(
                "🔔 <b>برای استفاده ابتدا در کانال‌های زیر عضو شوید:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
                parse_mode="HTML")
            return

    welcome = get_text("text_start", name=msg.from_user.first_name or "دوست")
    # ساخت منوی اصلی
    from db_helpers import get_setting as gs
    btn_buy     = get_text("btn_buy")
    btn_test    = get_text("btn_test") if gs("feat:test_service", True) else None
    btn_wallet  = get_text("btn_wallet")
    btn_svc     = get_text("btn_myservices")
    btn_support = get_text("btn_support")
    btn_help    = get_text("btn_help")
    btn_ref     = get_text("btn_affiliates") if gs("feat:referral", True) else None
    btn_disc    = get_text("btn_discount") if gs("feat:gift_codes", True) else None

    rows = [
        [InlineKeyboardButton(text=btn_buy,    callback_data="user:buy"),
         *([] if not btn_test else [InlineKeyboardButton(text=btn_test, callback_data="test:menu")])],
        [InlineKeyboardButton(text=btn_wallet, callback_data="user:wallet"),
         InlineKeyboardButton(text=btn_svc,    callback_data="user:services")],
        [InlineKeyboardButton(text=btn_support,callback_data="user:support"),
         InlineKeyboardButton(text=btn_help,   callback_data="user:guide")],
    ]
    if btn_ref:
        rows.append([InlineKeyboardButton(text=btn_ref, callback_data="user:referral")])
    if btn_disc:
        rows.append([InlineKeyboardButton(text=btn_disc, callback_data="user:gift")])
    if is_admin(msg.from_user.id):
        rows.append([InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="adm:main")])

    await msg.answer(welcome, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@start_router.callback_query(lambda cb: cb.data == "check_join")
async def cb_check_join(cb):
    from db_helpers import get_force_join_channels, get_setting
    channels = get_force_join_channels()
    if not channels or not get_setting("feat:force_join", True):
        await cb.message.delete()
        return
    not_joined = []
    for ch in channels:
        try:
            member = await cb.bot.get_chat_member(ch, cb.from_user.id)
            if member.status in ("left", "kicked"): not_joined.append(ch)
        except Exception: pass
    if not_joined:
        await cb.answer("❌ هنوز عضو نشدید!", show_alert=True)
    else:
        await cb.message.delete()
        await cb.message.answer(
            "✅ ممنون! اکنون می‌توانید استفاده کنی.\n"
            "دستور /start را ارسال کنید.")


@start_router.message(Command("id"))
async def cmd_id(msg: Message):
    await msg.answer(f"Your ID: <code>{msg.from_user.id}</code>")


@start_router.message(Command("admin"))
async def cmd_admin_shortcut(msg: Message):
    if not is_admin(msg.from_user.id): return
    from handlers.admin_hub import admin_main_kb
    await msg.answer("⚙️ <b>پنل مدیریت</b>", reply_markup=admin_main_kb())


# ——— main ———
async def main():
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN تنظیم نشده")
        sys.exit(1)

    bot = make_bot()
    dp  = make_dp()
    dp.include_router(start_router)
    register_all_routers(dp)

    # Admin API (مینی‌اپ)
    try:
        from admin_api import init_admin_api
        from aiohttp import web
        admin_app = init_admin_api(bot=bot, secret=ADMIN_SECRET)
        port = int(os.getenv("ADMIN_API_PORT", "8080"))
        runner = web.AppRunner(admin_app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
        logger.info("✅ Admin API روی پورت %s", port)
    except ImportError:
        logger.warning("⚠️ aiohttp یافت نشد — Admin API غیرفعال")
    except Exception as e:
        logger.warning("⚠️ Admin API error: %s", e)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
