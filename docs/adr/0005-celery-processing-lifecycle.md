# Celery owns delivery; Django owns processing truth

Uploaded Sermons must survive provider outages, worker crashes, duplicate delivery, and temporary broker loss without losing the pew recording or falsely becoming Ready.

V1 uses Celery with Redis for asynchronous delivery. Durable lifecycle state remains on the Django `Sermon`: status, attempt count, claim ID, and timestamps. Tasks claim rows transactionally, accept redelivery of the same Celery job, ignore competing or completed jobs, and only mark Ready after the configured `SermonProcessor` returns. Temporary failures retry with bounded backoff; permanent or exhausted failures become Failed while retaining the original audio. A periodic dispatcher recovers Sermons left Uploaded when the broker was unavailable.

The worker knows one provider-neutral interface: `process(sermon)`. A concrete processor owns transcription, predominant-speaker cleanup, Study artifact generation, and atomic, idempotent persistence because Celery delivery is at least once. This keeps queue and retry policy outside custom transcription and simpleai adapters, and preserves the domain rule that Ready means every required result exists.
