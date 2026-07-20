from rest_framework import serializers

from .models import (
    RelatedSermon,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    TagSuggestion,
    Transcript,
)

MAX_AUDIO_SIZE_BYTES = 500 * 1024 * 1024
SUPPORTED_AUDIO_TYPES = {
    "audio/aac",
    "audio/m4a",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "video/mp4",
}


class SermonSerializer(serializers.ModelSerializer):
    audio = serializers.FileField(write_only=True)
    processing_message = serializers.SerializerMethodField()

    class Meta:
        model = Sermon
        fields = (
            "id",
            "source_draft_id",
            "captured_at",
            "duration_seconds",
            "audio",
            "audio_mime_type",
            "audio_size_bytes",
            "processing_status",
            "processing_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "audio_mime_type",
            "audio_size_bytes",
            "processing_status",
            "processing_message",
            "created_at",
            "updated_at",
        )

    def validate_audio(self, audio):
        mime_type = (audio.content_type or "").split(";", 1)[0].lower()
        if mime_type not in SUPPORTED_AUDIO_TYPES:
            raise serializers.ValidationError(
                "Upload an AAC, M4A, MP4, Ogg, or WebM audio file."
            )
        if audio.size <= 0:
            raise serializers.ValidationError("The recording contains no audio.")
        if audio.size > MAX_AUDIO_SIZE_BYTES:
            raise serializers.ValidationError(
                "The recording exceeds the 500 MB upload limit."
            )
        return audio

    def create(self, validated_data):
        audio = validated_data["audio"]
        validated_data["audio_mime_type"] = (audio.content_type or "").lower()
        validated_data["audio_size_bytes"] = audio.size
        return super().create(validated_data)

    def get_processing_message(self, sermon: Sermon) -> str:
        if sermon.processing_status == Sermon.ProcessingStatus.UPLOADED:
            return "Safely uploaded and waiting to process."
        if sermon.processing_status == Sermon.ProcessingStatus.PROCESSING:
            return "Preparing the transcript and study guide."
        if sermon.processing_status == Sermon.ProcessingStatus.FAILED:
            return "Processing could not finish. The recording is still safe."
        return "Ready to revisit."


class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ("text", "segments", "updated_at")


class StudyArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyArtifact
        fields = ("kind", "content", "edited_at", "updated_at")


class ScriptureReferenceSerializer(serializers.ModelSerializer):
    display = serializers.SerializerMethodField()

    class Meta:
        model = ScriptureReference
        fields = (
            "book",
            "chapter_start",
            "verse_start",
            "chapter_end",
            "verse_end",
            "display",
        )

    def get_display(self, reference: ScriptureReference) -> str:
        display = f"{reference.book} {reference.chapter_start}"
        if reference.verse_start is not None:
            display += f":{reference.verse_start}"
        if reference.chapter_end is not None:
            display += f"–{reference.chapter_end}"
            if reference.verse_end is not None:
                display += f":{reference.verse_end}"
        elif reference.verse_end is not None:
            display += f"–{reference.verse_end}"
        return display


class TagSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TagSuggestion
        fields = ("name",)


class RelatedSermonSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="related_sermon_id", read_only=True)
    captured_at = serializers.DateTimeField(
        source="related_sermon.captured_at",
        read_only=True,
    )

    class Meta:
        model = RelatedSermon
        fields = ("id", "captured_at", "score", "reason")


class SermonDetailSerializer(SermonSerializer):
    transcript = TranscriptSerializer(read_only=True, allow_null=True)
    study_artifacts = StudyArtifactSerializer(many=True, read_only=True)
    scripture_references = ScriptureReferenceSerializer(many=True, read_only=True)
    tag_suggestions = TagSuggestionSerializer(many=True, read_only=True)
    related_sermons = RelatedSermonSerializer(many=True, read_only=True)

    class Meta(SermonSerializer.Meta):
        fields = SermonSerializer.Meta.fields + (
            "transcript",
            "study_artifacts",
            "scripture_references",
            "tag_suggestions",
            "related_sermons",
        )
        read_only_fields = SermonSerializer.Meta.read_only_fields + (
            "transcript",
            "study_artifacts",
            "scripture_references",
            "tag_suggestions",
            "related_sermons",
        )
