# TestFlight checklist (Pewcorder iOS)

Bundle id: `com.pewcorder.app`

## One-time Apple setup

1. App Store Connect → create app for `com.pewcorder.app`.
2. Apple Developer → Identifiers: enable **Push Notifications** and **Sign in with Apple**.
3. Create an APNs Auth Key (`.p8`) → download once; note Key ID + Team ID.
4. On the server:

```bash
# copy AuthKey_XXXX.p8 to:
/var/www/api.pewcorder.benlocher.com/backend/credentials/AuthKey_XXXXX.p8
chown pewcorder:pewcorder ...
chmod 600 ...
```

Add to `/var/www/api.pewcorder.benlocher.com/backend/.env`:

```
APNS_KEY_ID=...
APNS_TEAM_ID=...
APNS_AUTH_KEY_PATH=/var/www/api.pewcorder.benlocher.com/backend/credentials/AuthKey_XXXXX.p8
APNS_TOPIC=com.pewcorder.app
APNS_USE_SANDBOX=1
PUSH_ALERT_SENDER=sermons.push_alerts.NativePushAlertSender
```

Then `systemctl restart pewcorder pewcorder-worker pewcorder-beat`.

## Build + upload

From your Mac (with Xcode signing configured):

```bash
cd frontend
VITE_API_URL=https://api.pewcorder.benlocher.com npm run native:sync
open ios/App/App.xcodeproj
```

In Xcode: select a Team, Archive → Distribute App → App Store Connect → TestFlight.

Set `VITE_APPLE_CLIENT_ID` / redirect URL in the frontend env used for the Capacitor build if Sign in with Apple is enabled for web-style flows.
