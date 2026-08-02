from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from sermons.models import Sermon
from sermons.playback_audio import normalize_sermon_playback_audio
from sermons.processing import PermanentProcessingError


class Command(BaseCommand):
    help = (
        "Create loudness-normalized Sermon playback audio from each original "
        "(fixes quiet pew recordings without re-transcribing)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List sermons that would be normalized without rewriting files.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-normalize even when audio_normalized_at is already set.",
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
            help="Normalize only this Sermon UUID (repeatable).",
        )

    def handle(self, *args, **options):
        queryset = Sermon.objects.exclude(audio="").order_by("created_at")
        sermon_ids = options["sermon_ids"]
        if sermon_ids:
            queryset = queryset.filter(id__in=sermon_ids)
        elif not options["force"]:
            queryset = queryset.filter(
                Q(audio_normalized_at__isnull=True) | Q(playback_audio="")
            )

        limit = options["limit"]
        if limit < 0:
            raise CommandError("--limit must be >= 0.")
        if limit:
            queryset = queryset[:limit]

        sermons = list(queryset)
        if not sermons:
            self.stdout.write("No sermons needed playback loudness normalization.")
            return

        dry_run = options["dry_run"]
        force = options["force"]
        rewritten = 0
        skipped = 0
        failed = 0

        for sermon in sermons:
            label = f"{sermon.id} ({sermon.audio_size_bytes} bytes)"
            if dry_run:
                self.stdout.write(f"Would normalize {label}")
                rewritten += 1
                continue
            try:
                changed = normalize_sermon_playback_audio(sermon, force=force)
            except PermanentProcessingError as error:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Failed {label}: {error}"))
                continue
            if changed:
                rewritten += 1
                sermon.refresh_from_db(
                    fields=(
                        "playback_audio_size_bytes",
                        "audio_normalized_at",
                        "duration_seconds",
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Normalized {sermon.id} → "
                        f"{sermon.playback_audio_size_bytes} bytes"
                    )
                )
            else:
                skipped += 1
                self.stdout.write(f"Skipped {label} (already normalized)")

        summary = (
            f"Done. rewritten={rewritten} skipped={skipped} failed={failed}"
            + (" (dry-run)" if dry_run else "")
        )
        self.stdout.write(summary)
        if failed:
            raise CommandError(f"{failed} sermon(s) failed to normalize.")
