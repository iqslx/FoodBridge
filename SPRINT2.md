# FoodBridge: implemented backlog

All new pages use the existing English interface and responsive green theme.

| Story | Implementation |
| --- | --- |
| US07 | Donation detail page: food, quantity, expiry date, pickup address, donor and role-specific actions. |
| US08 | Only active, logged-in charities can request available, unexpired donations. Duplicate requests are blocked. |
| US09 | Only the owning donor can accept or reject pending requests. Acceptance reserves the donation for one charity and rejects other pending requests. |
| US10 | Donor dashboard and request pages show available/requested/accepted/collected/expired states. A donation stays Available while requests are pending; the dashboard shows Requested with the pending count. |
| US11 | The owner confirms collection of an accepted, unexpired donation. Both the request and donation become Collected. |
| US04 | Owners can edit or remove active donations. Affected charities receive notifications. Deletion cancels requests and retains an administrative audit record. Collected and expired donations cannot be changed. |
| US16 | Charity search combines food text, minimum quantity and pickup area. Clear filters returns the full available list. |
| US15 | In-app notifications for requests, decisions, edits, removal, expiry, collection and account status. Unread badge and mark-all-read. |
| US12 | Donor history shows collected/expired donations, with recipient charity for collected donations. |
| US13 | Admin reviews donor/charity accounts, organization license and address, approves, deactivates and reactivates accounts. New accounts activate immediately without approval. |
| US14 | Admin overview shows all donation statuses, user accounts and the latest 100 recorded activity events. |

## Agreed behavior

- As requested, expiry input and display use a date only. New donations expire at the end of that date in Saudi Arabia (23:59:59.999999 UTC+3), saved in the original fixed UTC format. The backlog should reflect this date-only choice.
- Notifications are inside the website. Expiry notifications and states are updated when an authenticated page is opened. No email/SMS service or background delivery is configured.
- Existing accounts remain Active during migration. Existing data are preserved; older charity accounts without a stored charity link show a manual-verification note to the admin.
- Deactivating a charity cancels its pending/accepted requests and releases its accepted donations. Deactivating a donor hides their donations from new requests and blocks the donor's sessions until reactivation.
- Existing donated records with no donor_id remain administrative records; their owners are not guessed.
- Requests have one row per charity per donation, including after rejection/cancellation. A charity cannot repeatedly request the same donation.
- Administrative activity records begin with this release. Earlier actions cannot be reconstructed.

## Administrator setup

For a fresh installation, install requirements then run from the project folder:

```powershell
python -m flask --app foodbridge create-admin
```

Enter an email and a password of at least 10 characters. The command never promotes existing accounts. Sign in via `/admin/login`; administrators are directed to `/admin`. Public `/login` accepts donor/charity accounts only. The two login sessions remain independent, even in the same browser.

The local instance prepared in this chat has its administrator login in the separate `FoodBridge-admin-access.txt` deliverable. That file and the local database are excluded from the shareable source ZIP.

## Running

```powershell
python -m pip install -r requirements.txt
python run.py
```

Open http://127.0.0.1:5000. Database creation and upgrades run automatically. New registrations activate immediately; admin review is optional. A private session key is generated inside `instance/secret.key` on first startup. The application binds only to localhost by default.

## Verification

Integration checks cover registration/approval, role isolation, CSRF, duplicate request protection, acceptance/rejection, collection, editing/deletion, filter combinations, expiry, recipient history, notifications, deactivation/reactivation, and data preservation on restart. Tests use a separate temporary database.

Run the standalone integration suite after installing requirements:

```powershell
python tests/test_workflow.py
```

Registration policy: donor and charity accounts are Active immediately. Previously Pending donor/charity accounts are upgraded to Active once loaded by this version. Inactive accounts remain disabled and administrator access stays separate.
