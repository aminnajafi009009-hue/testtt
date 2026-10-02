# Cherry VPN Bot v3 — راهنمای نصب

## پیش‌نیازها

```bash
python3.11+
pip install -r requirements.txt
```

## requirements.txt

```
aiogram==3.x
aiohttp
libsql-client   # یا libsql-experimental
python-dotenv
aiofiles
```

---

## ۱. فایل .env

```env
TELEGRAM_TOKEN=123456:ABC-DEF
ADMIN_ID=123456789
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your_turso_token
ORDER_LOG_CHANNEL_ID=-1003904350377
WEBAPP_URL=https://your-domain.com
UNIQUEPAY_BUSINESS_TOKEN=your_token_here
ADMIN_API_SECRET=change_me_to_random_secret
ADMIN_API_PORT=8080
```

---

## ۲. ساخت جداول

```bash
# با Turso CLI:
turso db shell your-db < db_migrations_v3.sql

# یا با libsql در Python:
python3 -c "from db_helpers import init_db; import asyncio; asyncio.run(asyncio.to_thread(init_db))"
```

---

## ۳. اجرا

```bash
python3 bot_main.py
```

---

## ۴. ساختار فایل‌ها

```
CherryV3/
├── bot_main.py                   ← نقطه ورود اصلی
├── db_helpers.py                 ← توابع دیتابیس
├── db_migrations_v3.sql          ← ساختار DB
├── uniquepay.py                  ← کلاینت UniquePay
├── payment_manager_v3.py         ← مدیریت روش‌های پرداخت
├── panels_v2.py                  ← router یکپارچه پنل‌ها
├── hiddify_panel.py              ← پنل Hiddify
├── marzban_panel.py              ← پنل Marzban
├── marzneshin_panel.py           ← پنل Marzneshin
├── outline_panel.py              ← پنل Outline
├── x3ui_panel.py                 ← پنل 3X-UI / X-UI
├── wireguard_panel.py            ← WireGuard Dashboard + wg-easy
├── admin_api.py                  ← REST API برای mini-app
├── admin_miniapp/
│   └── index.html                ← Mini-App ادمین (آینده‌نگر)
├── handlers/
│   ├── admin_hub.py              ← مرکز فرمان ادمین
│   ├── admin_payments_hub.py     ← مدیریت پرداخت‌ها
│   ├── admin_settings_hub.py     ← تنظیمات کامل
│   ├── broadcast_handler.py      ← پیام همگانی (rich text + دکمه)
│   ├── test_service_handler.py   ← سرویس تست پیشرفته
│   └── uniquepay_handler.py      ← فلو پرداخت آنلاین
└── INSTALL_V3.md
```

---

## ۵. تنظیمات UniquePay

1. وارد `ادمین ربات → پرداخت → UniquePay` شوید
2. Business Token را وارد کنید
3. روی دکمه «تست اتصال» کلیک کنید
4. اگر ✅ نشان داد، فعال کنید

---

## ۶. اضافه کردن پنل

از طریق ربات: `/admin → پنل‌ها → افزودن پنل`

```
نوع پنل: hiddify / marzban / marzneshin / outline / 3x_ui / wireguard_dashboard / wg_easy
آدرس: https://panel.example.com
API Key یا Username/Password
```

---

## ۷. سرویس تست

`/admin → تنظیمات → سرویس تست → افزودن پلن تست`

- حجم، مدت، پنل منبع را تنظیم کنید
- می‌توانید چند پلن از چند پنل مختلف اضافه کنید

---

## ۸. Mini-App ادمین

1. فایل `admin_miniapp/index.html` را روی دامنه خود سرو کنید
2. در BotFather یک Menu Button بسازید با URL:
   `https://your-domain.com/admin_miniapp/index.html`
3. Admin API در پورت 8080 اجرا می‌شود

---

## ۹. Pay As You Go

`ادمین → پرداخت → Pay As You Go → فعال + قیمت هر GB`

---

## ۱۰. پیام همگانی با rich text

- پیام را **فوروارد** کنید (ایموجی پریمیوم حفظ می‌شود)
- یا متن تایپ کنید با فرمت‌بندی تلگرام
- سپس دکمه اضافه کنید: `متن دکمه | https://link.com`

---

## نکات مهم

- Business Token را **فقط در `.env` یا DB** نگه دارید
- هر سفارش یک `hashId` **یکتا** دریافت می‌کند
- polling هر 5 ثانیه، timeout 15 دقیقه
- برای production از supervisor یا systemd استفاده کنید
