PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL CHECK(length(trim(full_name)) BETWEEN 2 AND 150),
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'master')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL CHECK(length(trim(full_name)) BETWEEN 2 AND 150),
    phone TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    device_type TEXT NOT NULL,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    serial_number TEXT UNIQUE,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS repair_statuses (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL UNIQUE,
    is_terminal INTEGER NOT NULL DEFAULT 0 CHECK(is_terminal IN (0, 1))
);

CREATE TABLE IF NOT EXISTS repair_orders (
    id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE RESTRICT,
    created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    master_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status_id INTEGER NOT NULL REFERENCES repair_statuses(id) ON DELETE RESTRICT,
    complaint TEXT NOT NULL CHECK(length(trim(complaint)) BETWEEN 5 AND 3000),
    diagnosis TEXT NOT NULL DEFAULT '',
    due_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    price_kopecks INTEGER NOT NULL
        CHECK(typeof(price_kopecks) = 'integer' AND price_kopecks BETWEEN 0 AND 1000000000),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS order_services (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES repair_orders(id) ON DELETE RESTRICT,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL
        CHECK(typeof(quantity) = 'integer' AND quantity BETWEEN 1 AND 1000),
    unit_price_kopecks INTEGER NOT NULL
        CHECK(typeof(unit_price_kopecks) = 'integer' AND unit_price_kopecks BETWEEN 0 AND 1000000000),
    UNIQUE(order_id, service_id)
);

CREATE TABLE IF NOT EXISTS order_status_history (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES repair_orders(id) ON DELETE RESTRICT,
    from_status_id INTEGER REFERENCES repair_statuses(id) ON DELETE RESTRICT,
    to_status_id INTEGER NOT NULL REFERENCES repair_statuses(id) ON DELETE RESTRICT,
    changed_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    note TEXT NOT NULL DEFAULT '',
    changed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_devices_client ON devices(client_id);
CREATE INDEX IF NOT EXISTS idx_orders_master_status ON repair_orders(master_id, status_id);
CREATE INDEX IF NOT EXISTS idx_orders_created ON repair_orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_device ON repair_orders(device_id);
CREATE INDEX IF NOT EXISTS idx_history_order ON order_status_history(order_id);
