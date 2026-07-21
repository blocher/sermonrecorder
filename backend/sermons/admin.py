from django.contrib import admin

from .models import (
    Reflection,
    RelatedSermon,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)


class TranscriptInline(admin.StackedInline):
    model = Transcript
    extra = 0
    max_num = 1


class StudyArtifactInline(admin.StackedInline):
    model = StudyArtifact
    extra = 0


class ScriptureReferenceInline(admin.TabularInline):
    model = ScriptureReference
    extra = 0


class TagSuggestionInline(admin.TabularInline):
    model = TagSuggestion
    extra = 0


class RelatedSermonInline(admin.TabularInline):
    model = RelatedSermon
    fk_name = "sermon"
    extra = 0


class ReflectionInline(admin.StackedInline):
    model = Reflection
    extra = 0


@admin.register(Sermon)
class SermonAdmin(admin.ModelAdmin):
    inlines = (
        TranscriptInline,
        StudyArtifactInline,
        ScriptureReferenceInline,
        TagSuggestionInline,
        RelatedSermonInline,
        ReflectionInline,
    )
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
