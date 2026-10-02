-- Cherry VPN Bot v3 — جداول اضافه‌شده از تحلیل میرزابات
-- این فایل رو بعد از db_migrations_v3.sql اجرا کن

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================
-- تنظیمات (جایگزین config.php)
-- ============================
CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL DEFAULT '',
    updated_at INTEGER DEFAULT (strftime('%s','now'))
);

-- مقادیر پیش‌فرض
INSERT OR IGNORE INTO settings (key, value) VALUES
  ('support_username',    ''),
  ('min_deposit',         '10000'),
  ('referral_reward',     '0'),
  ('notify_days_before',  '2'),
  ('order_log_channel',   ''),
  ('feat:test_service',   '1'),
  ('feat:referral',       '0'),
  ('feat:gift_codes',     '1'),
  ('feat:show_tariff',    '1'),
  ('feat:vip_only_buy',   '0'),
  ('feat:maintenance',    '0'),
  ('feat:force_join',     '0'),
  ('feat:notify_expire',  '1');

-- ============================
-- کدهای تخفیف
-- ============================
CREATE TABLE IF NOT EXISTS discounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    UNIQUE NOT NULL,
    percent     INTEGER DEFAULT 0,
    amount      INTEGER DEFAULT 0,
    uses_left   INTEGER DEFAULT NULL,   -- NULL = نامحدود
    expires_at  INTEGER DEFAULT NULL,   -- NULL = بدون انقضا
    created_at  INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- کدهای هدیه (gift codes)
-- ============================
CREATE TABLE IF NOT EXISTS gift_codes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    UNIQUE NOT NULL,
    value       INTEGER NOT NULL,       -- مبلغ تومان
    type        TEXT    DEFAULT 'balance',
    used        INTEGER DEFAULT 0,
    used_by     INTEGER DEFAULT NULL,
    used_at     INTEGER DEFAULT NULL,
    created_at  INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- تیکت‌ها (پشتیبانی)
-- ============================
CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    subject     TEXT    DEFAULT '',
    message     TEXT    NOT NULL,
    reply       TEXT    DEFAULT NULL,
    status      TEXT    DEFAULT 'open',  -- open/closed
    admin_id    INTEGER DEFAULT NULL,
    created_at  INTEGER DEFAULT (strftime('%s','now')),
    updated_at  INTEGER DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_tickets_status   ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_user_id  ON tickets(user_id);

-- ============================
-- لاگ فعالیت ادمین‌ها
-- ============================
CREATE TABLE IF NOT EXISTS admin_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id    INTEGER NOT NULL,
    action      TEXT    NOT NULL,
    extra       TEXT    DEFAULT '',
    ts          INTEGER DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_ts ON admin_logs(ts);

-- ============================
-- کانال‌های اجباری (force join)
-- ============================
CREATE TABLE IF NOT EXISTS force_join_channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id  TEXT UNIQUE NOT NULL,
    added_at    INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- لینک‌های تبلیغاتی
-- ============================
CREATE TABLE IF NOT EXISTS ad_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    clicks      INTEGER DEFAULT 0,
    is_active   INTEGER DEFAULT 1,
    created_at  INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- فاکتورهای UniquePay (اگه جدول قبلاً نیست)
-- ============================
CREATE TABLE IF NOT EXISTS uniquepay_invoices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    order_id    INTEGER DEFAULT NULL,
    ref_id      TEXT    NOT NULL,
    amount      INTEGER NOT NULL,
    status      TEXT    DEFAULT 'pending',  -- pending/paid/expired
    payment_link TEXT   DEFAULT '',
    tg_link     TEXT    DEFAULT '',
    created_at  INTEGER DEFAULT (strftime('%s','now')),
    paid_at     INTEGER DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_invoices_status  ON uniquepay_invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_user    ON uniquepay_invoices(user_id);

-- ============================
-- ستون notif_sent به جدول orders (در صورت نبود)
-- ============================
-- SQLite: ALTER TABLE فقط ADD COLUMN پشتیبانی می‌کند
-- اگر قبلاً هست خطا می‌ده ولی IGNORE می‌کنیم
PRAGMA ignore_check_constraints = ON;
ALTER TABLE orders ADD COLUMN notif_sent INTEGER DEFAULT 0;
-- ↑ اگه ستون از قبل وجود داره این خطا میده — ایمن است
