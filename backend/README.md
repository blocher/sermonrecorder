# Pewcorder API

Django 5.2 LTS and Django REST Framework API for authenticated Sermon uploads and processing state.

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Run `uv run python manage.py test` for the API suite, `uv run ruff check .` for linting, and `uv run black --check .` for formatting.

Email/password registration and JWT endpoints live under `/api/auth/`. `POST /api/sermons/` accepts multipart audio plus `source_draft_id`, `captured_at`, and `duration_seconds` as form fields or query parameters. Repeating the same Draft ID for one Congregant returns the original Sermon, making upload retries idempotent. New Sermons begin in `uploaded`; transcription workers will own later transitions to `processing`, `ready`, or `failed`.

SQLite and local media storage are development defaults. Production must provide `DJANGO_SECRET_KEY`, persistent database/object storage, HTTPS hosts, and worker infrastructure.
