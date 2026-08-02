from django.core.management.base import BaseCommand, CommandError

from sermons.audio_faststart import (
    ensure_sermon_listen_audio_faststart,
    m4a_needs_faststart,
)
from sermons.models import Sermon
from sermons.processing import PermanentProcessingError


class Command(BaseCommand):
    help = (
        "Rewrite Sermon M4A files with moov-before-mdat (faststart) so iOS "
        "Safari can play progressive audio."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List sermons that need faststart without rewriting files.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most this many sermons (0 = no limit).",
        )
        parser.add_argument(
            "--sermon-id",
            action="append",
            dest="sermon_ids",
            default=[],
            help="Faststart only this Sermon UUID (repeatable).",
        )

    def handle(self, *args, **options):
        queryset = Sermon.objects.exclude(audio="").order_by("created_at")
        sermon_ids = options["sermon_ids"]
        if sermon_ids:
            queryset = queryset.filter(id__in=sermon_ids)

        limit = options["limit"]
        if limit < 0:
            raise CommandError("--limit must be >= 0.")
        if limit:
            queryset = queryset[:limit]

        dry_run = options["dry_run"]
        rewritten = 0
        skipped = 0
        failed = 0

        for sermon in queryset.iterator():
            label = str(sermon.id)
            try:
                needs_original = m4a_needs_faststart(sermon.original_audio_path())
                needs_playback = bool(
                    sermon.playback_audio
                    and m4a_needs_faststart(sermon.playback_audio.path)
                )
            except (NotImplementedError, OSError, ValueError) as error:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Failed {label}: {error}"))
                continue

            if not needs_original and not needs_playback:
                skipped += 1
                continue

            if dry_run:
                parts = []
                if needs_original:
                    parts.append("original")
                if needs_playback:
                    parts.append("playback")
                self.stdout.write(f"Would faststart {label} ({', '.join(parts)})")
                rewritten += 1
                continue

            try:
                changed = ensure_sermon_listen_audio_faststart(sermon)
            except PermanentProcessingError as error:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Failed {label}: {error}"))
                continue

            if changed:
                rewritten += 1
                self.stdout.write(self.style.SUCCESS(f"Faststarted {label}"))
            else:
                skipped += 1

        summary = (
            f"Done. rewritten={rewritten} skipped={skipped} failed={failed}"
            + (" (dry-run)" if dry_run else "")
        )
        self.stdout.write(summary)
        if failed:
            raise CommandError(f"{failed} sermon(s) failed to faststart.")
