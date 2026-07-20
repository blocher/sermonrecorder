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

`SERMON_PROCESSOR` is the dotted path to a no-argument class implementing `process(sermon)`. It returns one complete `ProcessedSermon`; Django validates and atomically persists the cleaned Transcript, every required Study artifact, Scripture references, Tag suggestions, and same-owner Related Sermons before marking the Sermon Ready. The processor must tolerate at-least-once calls. Raise `RetryableProcessingError` for transient provider failures or `PermanentProcessingError` when retrying cannot help. The default processor is intentionally unconfigured and fails rather than falsely marking an empty Sermon Ready.

SQLite and local media storage are development defaults. Production must provide `DJANGO_SECRET_KEY`, persistent database/object storage, HTTPS hosts, and worker infrastructure.
