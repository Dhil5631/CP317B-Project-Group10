-- my three tables: users, cars and reservations
-- users holds both customers and managers; the role column tells them apart
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    licence_no TEXT NOT NULL,
    password_hash TEXT NOT NULL,   -- hashed, never the real password
    role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer','manager')),
    failed_attempts INTEGER NOT NULL DEFAULT 0,  -- used for the login lockout
    locked_until TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    make TEXT NOT NULL,
    model TEXT NOT NULL,
    car_type TEXT NOT NULL,
    seats INTEGER NOT NULL,
    daily_rate REAL NOT NULL
);
-- reservations is what the availability search checks against
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    car_id INTEGER NOT NULL REFERENCES cars(id),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','cancelled'))
);
