-- PostgreSQL schema for durable hosting. Existing records are never dropped.
CREATE TABLE IF NOT EXISTS charities (
    id SERIAL PRIMARY KEY,
    organization_name TEXT,
    license_number TEXT,
    city TEXT,
    address TEXT,
    status TEXT NOT NULL DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT,
    email TEXT UNIQUE,
    password TEXT,
    phone TEXT,
    role TEXT,
    account_status TEXT NOT NULL DEFAULT 'Active',
    charity_id INTEGER REFERENCES charities(id)
);
CREATE TABLE IF NOT EXISTS donations (
    id SERIAL PRIMARY KEY,
    food_type TEXT,
    quantity DOUBLE PRECISION,
    expiry_time TEXT,
    pickup_address TEXT,
    status TEXT,
    donor_id INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS donation_requests (
    id SERIAL PRIMARY KEY,
    donation_id INTEGER NOT NULL REFERENCES donations(id),
    charity_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(donation_id, charity_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_accepted_charity
    ON donation_requests(donation_id) WHERE status IN ('Accepted','Collected');
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    donation_id INTEGER REFERENCES donations(id),
    event_key TEXT UNIQUE,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    id SERIAL PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
