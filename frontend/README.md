# Pewcorder frontend

Vue 3, TypeScript, Vite, and Capacitor client for Pewcorder: AI Sermon Journal.

```sh
npm install
npm run dev
```

Use `npm test` for recording/Draft tests, `npm run typecheck` for TypeScript validation, and `npm run build` for a production bundle. Run `npm run native:sync` after web changes to build and copy them into the iOS and Android projects. Capacitor uses app ID `com.pewcorder.app`.

The canonical visual system lives in `../docs/DESIGN.md`. UI colors and spacing are implemented in `src/styles/tokens.css`.

Browser recordings are saved as audio `Blob`s in IndexedDB. Native recordings use `@capgo/capacitor-audio-recorder`; the completed file is moved out of temporary storage into the app's no-cloud data directory while IndexedDB keeps its Draft metadata. iOS enables background audio, and Android runs a microphone foreground service with an ongoing notification and partial wake lock so screen locking does not suspend an active capture. Force-closing the app still ends a recording by design.

The native projects compile from `ios/App/App.xcodeproj` and `android/`; Android builds require JDK 21. Background behavior and microphone interruptions must also be exercised on physical iOS and Android devices before release.
