# TestFlight checklist (Pewcorder iOS)

Bundle id: `com.pewcorder.app`  
Display name: Pewcorder  
Team: **The Daily Office, LLC** (`2TG4YK78KZ`)  
Version: `1.0` (build `1`)

## Already done on the server

- APNs Auth Key installed (`AuthKey_499SMMSNMR.p8`)
- `APNS_KEY_ID=499SMMSNMR`
- `APNS_TEAM_ID=2TG4YK78KZ` (The Daily Office, LLC)
- `APNS_USE_SANDBOX=0` (TestFlight / App Store use production APNs)
- `PUSH_ALERT_SENDER=sermons.push_alerts.NativePushAlertSender`

If push delivery fails after TestFlight install, create a new APNs Auth Key under the **Daily Office** Apple Developer account and replace the `.p8` + `APNS_KEY_ID` on the server (keys are team-scoped).

## One-time Apple Developer / App Store Connect

Use the **The Daily Office, LLC** membership (not the personal Benjamin Locher team).

1. [developer.apple.com/account](https://developer.apple.com/account) → **Identifiers** → App ID `com.pewcorder.app`
   - Enable **Push Notifications**
   - Enable **Sign in with Apple**
2. [appstoreconnect.apple.com](https://appstoreconnect.apple.com) → **My Apps** → **+** → New App
   - Platforms: iOS
   - Name: Pewcorder
   - Bundle ID: `com.pewcorder.app`
   - SKU: e.g. `pewcorder`
3. Fill the minimum App Privacy / export compliance answers when prompted on first upload.

## Build + upload (Mac)

```bash
cd frontend
VITE_API_URL=https://api.pewcorder.benlocher.com npm run native:sync
open ios/App/App.xcodeproj
```

In Xcode:

1. Signing & Capabilities → Team: **The Daily Office, LLC** (`2TG4YK78KZ`), Automatic signing
2. Confirm capabilities: **Push Notifications**, **Sign in with Apple**, Background Modes (Audio + Remote notifications)
3. Scheme: **App** → destination **Any iOS Device**
4. Product → **Archive**
5. Organizer → **Distribute App** → App Store Connect → Upload
6. App Store Connect → TestFlight → wait for processing → add Internal testers → Install from TestFlight

## Notes

- Native iOS Sign in with Apple uses the app entitlement (no `VITE_APPLE_CLIENT_ID` required on iOS).
- Google iOS sign-in needs `VITE_GOOGLE_IOS_CLIENT_ID` plus the reversed client ID URL scheme in `Info.plist` — can ship TestFlight without Google first.
- After each web/API client change that should land in the app: `npm run native:sync`, bump `CURRENT_PROJECT_VERSION`, Archive again.
