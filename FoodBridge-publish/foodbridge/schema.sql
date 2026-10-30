-- T1.2: User fields only. Password hashing belongs to registration (T1.4).
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    email TEXT,
    password TEXT,
    phone TEXT,
    role TEXT
);

-- T2.1 with the approved T2.3 status addition.
CREATE TABLE IF NOT EXISTS charities (
    id INTEGER PRIMARY KEY,
    organization_name TEXT,
    license_number TEXT,
    city TEXT,
    address TEXT,
    status TEXT NOT NULL DEFAULT 'Active'
);

-- T4.1: expiry_time uses YYYY-MM-DDTHH:MM:SS.ffffffZ, always UTC.
-- Every writer must use this exact fixed-width format (see README.md).
CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY,
    food_type TEXT,
    quantity REAL,
    expiry_time TEXT,
    pickup_address TEXT,
    status TEXT,
    donor_id INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS donation_requests (
    id INTEGER PRIMARY KEY,
    donation_id INTEGER NOT NULL REFERENCES donations(id),
    charity_id INTEGER NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(donation_id, charity_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_accepted_charity ON donation_requests(donation_id) WHERE status IN ('Accepted','Collected');
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    donation_id INTEGER REFERENCES donations(id),
    event_key TEXT UNIQUE,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
