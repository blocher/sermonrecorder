# ADR 0006: Durable processing alerts

## Status

Accepted

## Context

Sermon processing continues after upload and may finish while the native app is suspended. Polling updates an open Library but cannot reliably alert a congregant in the background. Notification delivery must not determine whether processing itself succeeds, and a token from one device or account must never receive another account's Sermon status.

## Decision

- The native app requests notification permission only after an authenticated user explicitly enables completion alerts.
- Each APNs or FCM registration token belongs to one current account. Re-registering the same token moves it to that account; signing out deletes the registration and unregisters the token locally.
- A terminal `Ready` or `Failed` transition creates one durable `ProcessingAlert` per active device in the same database transaction that records the transition.
- Celery delivers each alert independently with bounded retries. A periodic recovery task re-enqueues pending alerts and releases stale delivery claims.
- Sermon processing never retries or fails because notification delivery failed.
- An invalid native token is deactivated. Notification tokens remain write-only in the public API.
- Delivery uses a small `PushAlertSender` interface. Development logs deliveries; production selects `NativePushAlertSender`, which sends iOS tokens directly to APNs over HTTP/2 and Android tokens to FCM HTTP v1.
- Opening an alert routes directly to the owner-authenticated Sermon detail.

## Consequences

The database is the durable handoff between processing and push delivery, so broker outages do not lose alerts and duplicate processing jobs do not create duplicate notifications. Actual device delivery still depends on Apple/Google credentials and physical-device configuration. Delivery is at-least-once across a worker crash after the gateway accepts a message but before the database records it as sent.
