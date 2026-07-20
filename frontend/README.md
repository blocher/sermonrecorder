# Pewcorder frontend

Vue 3, TypeScript, Vite, and Capacitor client for Pewcorder: AI Sermon Journal.

```sh
npm install
npm run dev
```

Use `npm test` for recording/Draft tests, `npm run typecheck` for TypeScript validation, and `npm run build` for a production bundle. Capacitor is configured with app ID `com.pewcorder.app`; native platform projects will be added after the background-recording spike.

The canonical visual system lives in `../docs/DESIGN.md`. UI colors and spacing are implemented in `src/styles/tokens.css`.

Foreground microphone recordings are saved as audio `Blob`s in IndexedDB and remain available after reload. Native background/lock-screen recording and server upload are deliberately separate follow-on slices.
