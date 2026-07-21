# Pewcorder frontend

Vue 3, TypeScript, Vite, and Capacitor client for Pewcorder: AI Sermon Journal.

```sh
npm install
npm run dev
```

Use `npm test` for recording/Draft tests, `npm run typecheck` for TypeScript validation, and `npm run build` for a production bundle. Run `npm run native:sync` after web changes to build and copy them into the iOS and Android projects. Capacitor uses app ID `com.pewcorder.app`.

The canonical visual system lives in `../docs/DESIGN.md`. UI colors and spacing are implemented in `src/styles/tokens.css`.

Browser recordings are saved as audio `Blob`s in IndexedDB. Native recordings use `@capgo/capacitor-audio-recorder`; the completed file is moved out of temporary storage into the app's no-cloud data directory while IndexedDB keeps its Draft metadata. iOS enables background audio, and Android runs a microphone foreground service with an ongoing notification and partial wake lock so screen locking does not suspend an active capture. Force-closing the app still ends a recording by design.

Set `VITE_API_URL` to the Django API origin. Email/password and Apple/Google sign-in all exchange for the same short-lived Pewcorder JWT session; raw provider credentials are sent only to Django for verification. Draft uploads are idempotent by local Draft ID. Browser audio uses multipart `fetch`; native audio streams directly from the app file through `@capacitor/file-transfer` so long recordings are not copied into JavaScript memory.

Social buttons appear only when their platform is configured. Set `VITE_GOOGLE_WEB_CLIENT_ID` for Android/web and `VITE_GOOGLE_IOS_CLIENT_ID` for iOS; use the web ID as a server audience. The Google iOS credential's reversed client ID must also be added as a URL scheme in `ios/App/App/Info.plist`. Set `VITE_APPLE_CLIENT_ID` to the Apple Service ID used by Android/web and `VITE_APPLE_REDIRECT_URL` for web; native iOS uses the app's Sign in with Apple entitlement. Register `com.pewcorder.app` and each signing certificate/package SHA with the providers, enable Sign in with Apple on the Apple App ID, then run `npm run native:sync`. The matching IDs must be allowlisted by Django.

Signed-in users can explicitly enable native Ready/Failed completion alerts from Account. iOS forwards APNs registration through `AppDelegate.swift` and includes the Push Notifications entitlement; the Apple Developer App ID and provisioning profiles must also enable Push Notifications. Android requires the deployment's Firebase `google-services.json` in `android/app/`. Signing out removes the owner-private backend registration and unregisters the native token.

Sermon details offer an explicit “Find nearby Churches” action. Only that action requests foreground precise-location permission and sends one coordinate pair for a non-persisting provider lookup; denied permission leaves the manual Church flow intact. A selected suggestion is saved to the Congregant's private place book and remains editable.

The native projects compile from `ios/App/App.xcodeproj` and `android/`; Android builds require JDK 21. Background behavior and microphone interruptions must also be exercised on physical iOS and Android devices before release.
