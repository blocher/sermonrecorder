from django.contrib import admin

from .models import Sermon


@admin.register(Sermon)
class SermonAdmin(admin.ModelAdmin):
    list_display = (
        "captured_at",
        "owner",
        "processing_status",
        "processing_attempts",
        "duration_seconds",
        "audio_size_bytes",
    )
    list_filter = ("processing_status", "captured_at")
    search_fields = ("owner__email", "source_draft_id")
    readonly_fields = (
        "id",
        "audio_mime_type",
        "audio_size_bytes",
        "processing_attempts",
        "processing_claim_id",
        "processing_started_at",
        "processing_finished_at",
        "created_at",
        "updated_at",
    )
