# Capacitor + Vue client, Django API

We need one iOS/Android app with local Drafts, upload, and push-when-Ready, plus a central App Admin. We chose Capacitor wrapping a Vue UI and a Django backend (Admin + async processing workers) because it matches the team's strengths and keeps a single Congregant UI codebase. We rejected Expo/React Native and Flutter for v1 unless a recording/upload spike proves Capacitor unreliable for pew capture.
