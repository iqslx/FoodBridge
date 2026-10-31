# Permanent hosting readiness

This is a separate copy of the current FoodBridge application, prepared for a Python/Docker web host. Local databases, session keys and administrator credentials are excluded.

## Runtime
- Python 3.12 and Gunicorn, one worker with four threads.
- Container HTTP port: 8000.
- Health check: GET /login.
- Persistent directory: /app/instance. Mount durable storage here to retain SQLite accounts, requests, notifications, and the private session key across restarts and redeployments.
- No hosting service has been created or billed yet.

## First deployment
1. Connect the hosting account and provide a private source repository or supported source upload.
2. Build the supplied Dockerfile.
3. Mount persistent storage at /app/instance before accepting registrations.
4. Set up the administrator through the existing create-admin command on the deployed service; local administrator credentials are not copied.
5. Verify the public HTTPS URL, registration approval, requests and collection workflow before sharing.

Persistent disks on Render require a paid service. Confirm the selected plan and price with the user before activation. Free services without durable storage must not be presented as a persistent database solution.

The source project on the user's computer is unchanged by this preparation.
