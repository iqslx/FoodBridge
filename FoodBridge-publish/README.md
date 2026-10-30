# FoodBridge — current version

See **SPRINT2.md** for the implemented Sprint 2 features, administrator setup, account approval, notifications and date-only expiry behavior.

The sections below describe the original Sprint 1 delivery and are retained as historical context. Sprint 2 supersedes its immediate-activation and expiry-input descriptions.

# FoodBridge – Sprint 1 (CS 388T, Group #3, Section 7C7)

FoodBridge is a web platform that connects donors (restaurants, bakeries, individuals) who have surplus food with charities that need it.
This folder contains the Sprint 1 version: donor and charity registration, login, adding a food donation, and the available donations list for charities.

## Requirements

- Python 3.9 or newer
- Flask (installed from `requirements.txt`)
- SQLite (included with Python)

## How to run

Run these commands from the project folder (the folder that contains `requirements.txt` and the `foodbridge` folder):

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1      macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m flask --app foodbridge init-db
python -m flask --app foodbridge run
```

Open http://127.0.0.1:5000 in the browser.

`init-db` builds the database `instance/foodbridge.db` from `foodbridge/schema.sql`. Do not copy a database file between team members; everyone creates it with `init-db`.

If you already have a database from an earlier version, run `python upgrade_db.py` once. It adds `charities.status` and `donations.donor_id`. Old donations keep an empty `donor_id`.

## Pages

| Page | Address | Who |
| --- | --- | --- |
| Home | `/` | everyone |
| Donor registration | `/register` | donor |
| Charity registration | `/charity` | charity |
| Login | `/login` | donor or charity |
| Donor dashboard | `/dashboard` | donor |
| Add a food donation | `/add` | donor |
| Available donations | `/donations` | charity |
| Logout | `/logout` | logged-in user |

## What Sprint 1 covers

| Story | Feature |
| --- | --- |
| US01 | Donor registration (empty fields and repeated email are refused; password is saved as a hash) |
| US05 | Charity registration (the new charity is Active in Sprint 1; admin approval comes in Sprint 2 with US13) |
| US02 | Login (wrong password shows a message; donor goes to the dashboard, charity goes to the donations list) |
| US03 | Add a food donation (quantity above zero, expiry time in the future, saved as Available and linked to the donor) |
| US06 | Available donations list (only Available and not expired donations; a message when the list is empty) |

## Files

- `foodbridge/__init__.py`, `foodbridge/db.py` – Flask application and database connection (T1.1)
- `foodbridge/schema.sql` – tables `users`, `charities`, `donations` (T1.2, T2.1, T4.1)
- `foodbridge/vi.py` – the pages: registration, login, dashboard, add donation, donations list
- `foodbridge/donations.py` – query for available, not expired donations (T5.2)
- `foodbridge/templates/` – HTML pages
- `upgrade_db.py` – one-time upgrade for an existing database

## Expiry time format

`donations.expiry_time` is saved as text in UTC, in exactly this format: `YYYY-MM-DDTHH:MM:SS.ffffffZ` (example: `2026-10-22T16:57:00.000000Z`).
The donor enters the time in Saudi time (UTC+3) in the form, and the program converts it to UTC before saving. The list currently shows the saved UTC time. Showing Saudi time is planned for Sprint 2.

## Notes

- Test accounts used in the Sprint Review (Noor Charity, Sara Bakery) are for testing only.
- This is a development version: the secret key is a fixed development key and the app is not meant for a public server.
