-- Cherry VPN Bot v3 — DB migrations
-- Engine: Turso (libSQL / SQLite-compatible)
-- Run once on first deploy

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================
-- Users
-- ============================
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,       -- Telegram user_id
    username      TEXT    DEFAULT '',
    full_name     TEXT    DEFAULT '',
    wallet        INTEGER DEFAULT 0,
    is_vip        INTEGER DEFAULT 0,
    is_blocked    INTEGER DEFAULT 0,
    is_reseller   INTEGER DEFAULT 0,
    referrer_id   INTEGER DEFAULT NULL,
    total_spent   INTEGER DEFAULT 0,
    created_at    INTEGER DEFAULT (strftime('%s','now')),
    last_seen     INTEGER DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

-- ============================
-- Plans (محصولات)
-- ============================
CREATE TABLE IF NOT EXISTS plans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    traffic_gb      REAL NOT NULL,
    duration_days   INTEGER NOT NULL,
    price           INTEGER NOT NULL,
    panel_id        INTEGER DEFAULT NULL,   -- NULL = هر پنلی
    is_active       INTEGER DEFAULT 1,
    is_test         INTEGER DEFAULT 0,      -- آیا پلن تست است؟
    sort_order      INTEGER DEFAULT 0,
    created_at      INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- Panels
-- ============================
CREATE TABLE IF NOT EXISTS panels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    panel_type  TEXT NOT NULL,              -- hiddify/marzban/3x_ui/wg_easy/...
    base_url    TEXT NOT NULL,
    api_key     TEXT DEFAULT '',
    username    TEXT DEFAULT '',
    password    TEXT DEFAULT '',
    inbound_id  INTEGER DEFAULT 1,          -- برای 3X-UI
    secret_path TEXT DEFAULT '',            -- برای 3X-UI با مسیر مخفی
    enabled     INTEGER DEFAULT 1,
    last_tested INTEGER DEFAULT NULL,
    test_ok     INTEGER DEFAULT NULL,
    created_at  INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- Orders (سفارش‌ها)
-- ============================
CREATE TABLE IF NOT EXISTS orders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    plan_id         INTEGER REFERENCES plans(id),
    panel_id        INTEGER REFERENCES panels(id),
    amount          INTEGER NOT NULL,
    payment_method  TEXT NOT NULL,          -- card/wallet/uniquepay/crypto/paygo
    status          TEXT DEFAULT 'pending', -- pending/paid/confirmed/failed
    payment_hash    TEXT DEFAULT '',        -- uniquepay hashId
    receipt_file_id TEXT DEFAULT '',        -- برای کارت-به-کارت
    panel_username  TEXT DEFAULT '',
    sub_link        TEXT DEFAULT '',
    config_data     TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    created_at      INTEGER DEFAULT (strftime('%s','now')),
    confirmed_at    INTEGER DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_user   ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- ============================
-- Services (سرویس‌های فعال)
-- ============================
CREATE TABLE IF NOT EXISTS services (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    order_id        INTEGER REFERENCES orders(id),
    panel_id        INTEGER REFERENCES panels(id),
    plan_id         INTEGER REFERENCES plans(id),
    panel_username  TEXT NOT NULL,
    sub_link        TEXT DEFAULT '',
    traffic_gb      REAL DEFAULT 0,
    used_gb         REAL DEFAULT 0,
    expire_at       INTEGER NOT NULL,
    is_active       INTEGER DEFAULT 1,
    service_type    TEXT DEFAULT 'regular', -- regular/test/paygo
    created_at      INTEGER DEFAULT (strftime('%s','now'))
);

CREATE INDEX IF NOT EXISTS idx_services_user   ON services(user_id);
CREATE INDEX IF NOT EXISTS idx_services_expire ON services(expire_at);

-- ============================
-- Wallet Transactions
-- ============================
CREATE TABLE IF NOT EXISTS wallet_transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount      INTEGER NOT NULL,            -- + شارژ، - برداشت
    balance_after INTEGER DEFAULT 0,
    reason      TEXT DEFAULT '',             -- charge/order/refund/gift/referral
    ref_id      TEXT DEFAULT '',
    created_at  INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- Resellers
-- ============================
CREATE TABLE IF NOT EXISTS resellers (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id),
    discount_pct    INTEGER DEFAULT 10,
    balance         INTEGER DEFAULT 0,
    total_sales     INTEGER DEFAULT 0,
    total_customers INTEGER DEFAULT 0,
    level           TEXT DEFAULT 'bronze',   -- bronze/silver/gold/diamond
    custom_token    TEXT DEFAULT '',         -- برای mini-app
    is_approved     INTEGER DEFAULT 0,
    created_at      INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- Tickets
-- ============================
CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    subject     TEXT DEFAULT '',
    status      TEXT DEFAULT 'open',         -- open/in_progress/closed
    priority    TEXT DEFAULT 'normal',       -- low/normal/high/urgent
    created_at  INTEGER DEFAULT (strftime('%s','now')),
    closed_at   INTEGER DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL REFERENCES tickets(id),
    user_id     INTEGER NOT NULL,
    text        TEXT DEFAULT '',
    is_admin    INTEGER DEFAULT 0,
    file_id     TEXT DEFAULT '',
    created_at  INTEGER DEFAULT (strftime('%s','now'))
);

-- ============================
-- Settings (key-value)
-- ============================
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL DEFAULT ''
);

-- مقادیر پیش‌فرض
INSERT OR IGNORE INTO settings(key, value) VALUES
    ('maintenance_mode',       '0'),
    ('registration_open',      '1'),
    ('referral_enabled',       '1'),
    ('auto_accept_orders',     '0'),
    ('force_join_enabled',     '0'),
    ('force_join_channel',     ''),
    ('test_service_enabled',   '1'),
    ('test_max_per_user',      '1'),
    ('test_expire_hours',      '24'),
    ('test_plans',             '[]'),
    ('pm_card_enabled',        '1'),
    ('pm_wallet_enabled',      '1'),
    ('pm_uniquepay_enabled',   '0'),
    ('pm_paygo_enabled',       '0'),
    ('pm_cryptos',             '[]'),
    ('up_token',               ''),
    ('up_redirect',            ''),
    ('up_use_tglink',          '1'),
    ('up_show_card',           '1'),
    ('up_auto_confirm',        '0'),
    ('reseller_enabled',       '0'),
    ('reseller_discount',      '10'),
    ('reseller_auto_approve',  '0'),
    ('reseller_miniapp',       '1'),
    ('notif_new_order',        '1'),
    ('notif_payment',          '1'),
    ('notif_expire',           '1'),
    ('notif_new_user',         '1'),
    ('notif_ticket',           '1'),
    ('notif_panel_error',      '1'),
    ('order_log_channel',      ''),
    ('wallet_min_charge',      '10000'),
    ('wallet_gift_percent',    '0'),
    ('paygo_per_gb',           '5000'),
    ('expire_warning_days',    '3'),
    ('welcome_message',        '🍒 به Cherry VPN خوش آمدید!'),
    ('guide_text',             '📌 راهنمای اتصال VPN'),
    ('payment_text',           '💳 لطفاً پس از واریز، رسید را ارسال کنید'),
    ('service_ok_text',        '✅ سرویس شما آماده شد'),
    ('expire_text',            '⚠️ سرویس شما به زودی منقضی می‌شود'),
    ('test_text',              '🎁 سرویس تست رایگان'),
    ('maintenance_text',       '🛠️ در حال تعمیرات هستیم، بعداً تلاش کنید');

-- ============================
-- Pay-as-you-go
-- ============================
CREATE TABLE IF NOT EXISTS paygo_services (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    panel_id    INTEGER REFERENCES panels(id),
    panel_username TEXT NOT NULL,
    price_per_gb   INTEGER NOT NULL,
    used_gb     REAL DEFAULT 0,
    billed_gb   REAL DEFAULT 0,
    balance     INTEGER DEFAULT 0,          -- پیش‌پرداخت
    is_active   INTEGER DEFAULT 1,
    created_at  INTEGER DEFAULT (strftime('%s','now'))
);
