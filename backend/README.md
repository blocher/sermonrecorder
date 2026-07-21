# Pewcorder API

Django 5.2 LTS and Django REST Framework API for authenticated Sermon uploads and processing state.

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Run `uv run python manage.py test` for the API suite, `uv run ruff check .` for linting, and `uv run black --check .` for formatting.

Email/password registration and JWT endpoints live under `/api/auth/`. `POST /api/sermons/` accepts multipart audio plus `source_draft_id`, `captured_at`, and `duration_seconds` as form fields or query parameters. Repeating the same Draft ID for one Congregant returns the original Sermon, making upload retries idempotent.

## Processing workers

Redis carries Celery jobs. Run a worker and scheduler alongside Django:

```sh
redis-server
uv run celery -A config worker --loglevel=INFO
uv run celery -A config beat --loglevel=INFO
```

New Sermons begin in `uploaded`, move to `processing` while claimed, and end in `ready` or `failed`. Temporary failures return to `uploaded` and retry after 1, 5, and 15 minutes. The scheduler re-enqueues safely stored uploads if the broker was unavailable during the original request.

`SERMON_PROCESSOR` is the dotted path to a no-argument class implementing `process(sermon)`. It returns one complete `ProcessedSermon`; Django validates and atomically persists the cleaned Transcript, every required Study artifact, Scripture references, Tag suggestions, and same-owner Related Sermons before marking the Sermon Ready. The processor must tolerate at-least-once calls. Raise `RetryableProcessingError` for transient provider failures or `PermanentProcessingError` when retrying cannot help.

The default provider pipeline uses OpenAI's diarizing transcription model, keeps only each audio chunk's predominant speaker, and sends that cleaned Transcript through the pinned simpleai facade for structured Study artifacts. Set `OPENAI_API_KEY` before running workers. Audio over 24 MB is transcoded to mono 32 kbps chunks with `ffmpeg`; install that binary in every worker image. `OPENAI_TRANSCRIPTION_MODEL`, `SIMPLEAI_OPENAI_MODEL`, `SERMON_ARTIFACT_MODEL`, and `SERMON_PROCESSOR` remain configurable so transcription and artifact providers can evolve independently.

Ready detail responses contain an owner-issued, four-hour audio capability URL rather than a permanent media path. The audio endpoint validates that signature and supports byte ranges for seeking; configure `SERMON_AUDIO_URL_MAX_AGE_SECONDS` and native Capacitor origins explicitly in production.

Ready Sermons can also publish one active unlisted Share Link. The public payload includes audio, the cleaned Transcript, Study artifacts, Scripture references, and Tag suggestions, but never Reflections or private-library relationships. Revocation immediately disables both the page and its range-capable audio endpoint. Set `PEWCORDER_PUBLIC_WEB_URL` to the deployed Vue application's HTTPS origin so native apps share a reachable web URL.

Congregants can keep an owner-private list of Saved Recipients and send each recipient an individual HTML/text handout linking to that Share page. Configure `DJANGO_EMAIL_BACKEND`, `DJANGO_DEFAULT_FROM_EMAIL`, and the provider-specific SMTP or transactional-email environment in production; the development default prints messages to the console.

Churches and Preachers are reusable, owner-private personal-book records. A Sermon can reference either and can store a standard Occasion kind plus an optional free-text Liturgical day. These fields are optional, editable after capture, and included in owner, Share-page, and email projections without becoming prerequisites for recording.

The authenticated Sermon list accepts `search`, `church`, `preacher`, `occasion`, `tag`, `date_from`, and `date_to` query parameters. Search remains owner-scoped while matching Transcript text, generated Study artifacts, Scripture references, Tags, private Reflections, related-Sermon reasons, and structured Sermon context.

Native device registrations are owner-private and their tokens are never returned by the API. Ready and terminal Failed transitions create one durable `ProcessingAlert` per active device; Celery retries delivery independently from Sermon processing and Beat recovers unsent or abandoned delivery claims. Development uses `sermons.push_alerts.LoggingPushAlertSender`. Production sets `PUSH_ALERT_SENDER=sermons.push_alerts.NativePushAlertSender`.

Direct iOS delivery requires `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_AUTH_KEY_PATH`, `APNS_TOPIC`, and the correct `APNS_USE_SANDBOX` value. Direct Android delivery requires `FCM_PROJECT_ID` and `FCM_SERVICE_ACCOUNT_FILE` for a service account authorized to send Firebase Cloud Messaging HTTP v1 messages. Keep the Apple `.p8` key and Firebase service-account JSON outside the repository; `backend/credentials/` is ignored for local credential mounts. Confirmed unregistered tokens are deactivated, transient provider failures retry with backoff, and credential/payload errors fail their delivery without retrying Sermon processing.

The authenticated Church-suggestion endpoint accepts one validated coordinate pair and queries the configured `CHURCH_SUGGESTION_PROVIDER`. The default Overpass adapter finds nearby Christian places of worship, deduplicates and distance-orders them, and identifies itself through `OVERPASS_USER_AGENT` as required by the public service. The coordinate fix is not persisted by lookup; only a suggestion the Congregant confirms becomes a reusable private Church with provider coordinates.

SQLite and local media storage are development defaults. Production must provide `DJANGO_SECRET_KEY`, persistent database/object storage, HTTPS hosts, and worker infrastructure.
