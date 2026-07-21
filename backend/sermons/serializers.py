from rest_framework import serializers
from django.urls import reverse

from .models import (
    Church,
    Preacher,
    Reflection,
    RelatedSermon,
    ScriptureReference,
    Sermon,
    StudyArtifact,
    Transcript,
    normalize_personal_book_value,
)
from .private_audio import private_audio_url
from .scripture import MAX_SCRIPTURE_NUMBER, normalize_scripture_reference
from .tagging import normalize_tag

MAX_AUDIO_SIZE_BYTES = 500 * 1024 * 1024
SUPPORTED_AUDIO_TYPES = {
    "audio/aac",
    "audio/m4a",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",
    "video/mp4",
}


class ChurchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Church
        fields = (
            "id",
            "name",
            "address",
            "latitude",
            "longitude",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, name: str) -> str:
        name = " ".join(name.split())
        if not name:
            raise serializers.ValidationError("Give this Church a name.")
        return name

    def validate(self, attrs):
        latitude = attrs.get("latitude", getattr(self.instance, "latitude", None))
        longitude = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if (latitude is None) != (longitude is None):
            raise serializers.ValidationError(
                "Save latitude and longitude together, or leave both blank."
            )

        request = self.context["request"]
        name = attrs.get("name", getattr(self.instance, "name", ""))
        address = attrs.get("address", getattr(self.instance, "address", ""))
        existing = Church.objects.filter(
            owner=request.user,
            normalized_name=normalize_personal_book_value(name),
            normalized_address=normalize_personal_book_value(address),
        )
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(
                "This Church is already in your personal place book."
            )
        return attrs


class PreacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Preacher
        fields = ("id", "name", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, name: str) -> str:
        name = " ".join(name.split())
        if not name:
            raise serializers.ValidationError("Give this Preacher a name.")
        request = self.context["request"]
        existing = Preacher.objects.filter(
            owner=request.user,
            normalized_name=normalize_personal_book_value(name),
        )
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(
                "This Preacher is already in your personal preacher book."
            )
        return name


class ChurchSuggestionQuerySerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    radius_meters = serializers.IntegerField(
        min_value=100,
        max_value=5_000,
        required=False,
        default=1_500,
    )


class SermonContextUpdateSerializer(serializers.Serializer):
    church_id = serializers.UUIDField(required=False, allow_null=True)
    preacher_id = serializers.UUIDField(required=False, allow_null=True)
    occasion_kind = serializers.ChoiceField(
        choices=Sermon.OccasionKind,
        required=False,
        allow_blank=True,
    )
    liturgical_day = serializers.CharField(
        max_length=160,
        required=False,
        allow_blank=True,
    )

    def validate_liturgical_day(self, liturgical_day: str) -> str:
        return " ".join(liturgical_day.split())


class LibrarySearchQuerySerializer(serializers.Serializer):
    search = serializers.CharField(max_length=500, required=False, allow_blank=True)
    church = serializers.UUIDField(required=False)
    preacher = serializers.UUIDField(required=False)
    occasion = serializers.ChoiceField(
        choices=Sermon.OccasionKind,
        required=False,
    )
    tag = serializers.CharField(max_length=80, required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    processing_status = serializers.ChoiceField(
        choices=Sermon.ProcessingStatus,
        required=False,
    )

    def validate(self, attrs):
        if (
            attrs.get("date_from")
            and attrs.get("date_to")
            and attrs["date_from"] > attrs["date_to"]
        ):
            raise serializers.ValidationError(
                "The start date must not be after the end date."
            )
        return attrs


class SermonSerializer(serializers.ModelSerializer):
    audio = serializers.FileField(write_only=True)
    processing_message = serializers.SerializerMethodField()
    short_summary = serializers.SerializerMethodField()
    tag_suggestions = serializers.SerializerMethodField()
    church = ChurchSerializer(read_only=True)
    preacher = PreacherSerializer(read_only=True)

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
            "church",
            "preacher",
            "occasion_kind",
            "liturgical_day",
            "processing_status",
            "processing_message",
            "short_summary",
            "tag_suggestions",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "audio_mime_type",
            "audio_size_bytes",
            "church",
            "preacher",
            "occasion_kind",
            "liturgical_day",
            "processing_status",
            "processing_message",
            "short_summary",
            "tag_suggestions",
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

    def get_short_summary(self, sermon: Sermon) -> str:
        if sermon.processing_status != Sermon.ProcessingStatus.READY:
            return ""
        artifact = next(
            (
                artifact
                for artifact in sermon.study_artifacts.all()
                if artifact.kind == StudyArtifact.Kind.SHORT_SUMMARY
            ),
            None,
        )
        return artifact.content if artifact else ""

    def get_tag_suggestions(self, sermon: Sermon) -> list[str]:
        if sermon.processing_status != Sermon.ProcessingStatus.READY:
            return []
        return [suggestion.name for suggestion in sermon.tag_suggestions.all()]


class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ("text", "segments", "updated_at")


class TranscriptSegmentEditSerializer(serializers.Serializer):
    start_seconds = serializers.FloatField(min_value=0)
    text = serializers.CharField(max_length=10_000, trim_whitespace=True)


class TranscriptEditSerializer(serializers.Serializer):
    segments = TranscriptSegmentEditSerializer(many=True, allow_empty=False)

    def validate_segments(self, segments):
        current_segments = self.context["transcript"].segments
        if len(segments) != len(current_segments):
            raise serializers.ValidationError(
                "Transcript segment boundaries cannot be added or removed."
            )
        updated = []
        for current, edited in zip(current_segments, segments, strict=True):
            if abs(float(current["start_seconds"]) - edited["start_seconds"]) > 0.001:
                raise serializers.ValidationError(
                    "Transcript timestamps cannot be changed."
                )
            updated.append({**current, "text": edited["text"]})
        return updated


class TagsEditSerializer(serializers.Serializer):
    tags = serializers.ListField(
        child=serializers.CharField(
            max_length=80,
            trim_whitespace=True,
        ),
        allow_empty=True,
        max_length=12,
    )

    def validate_tags(self, tags):
        normalized = []
        seen = set()
        for tag in tags:
            try:
                name, normalized_name = normalize_tag(tag)
            except ValueError as error:
                raise serializers.ValidationError(str(error)) from error
            if normalized_name in seen:
                raise serializers.ValidationError("Tags must be unique.")
            seen.add(normalized_name)
            normalized.append(
                {
                    "name": name,
                    "normalized_name": normalized_name,
                }
            )
        return normalized


class StudyArtifactSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyArtifact
        fields = ("kind", "content", "edited_at", "updated_at")


class StudyArtifactEditSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyArtifact
        fields = ("kind", "content", "edited_at", "updated_at")
        read_only_fields = ("kind", "edited_at", "updated_at")

    def validate_content(self, content: str) -> str:
        content = content.strip()
        if not content:
            raise serializers.ValidationError("A Study artifact cannot be empty.")
        if len(content) > 100_000:
            raise serializers.ValidationError("A Study artifact is too long.")
        return content


class ReflectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reflection
        fields = ("id", "prompt", "content", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_prompt(self, prompt: str) -> str:
        prompt = prompt.strip()
        if len(prompt) > 2_000:
            raise serializers.ValidationError("A Reflection prompt is too long.")
        return prompt

    def validate_content(self, content: str) -> str:
        content = content.strip()
        if not content:
            raise serializers.ValidationError("A Reflection cannot be empty.")
        if len(content) > 100_000:
            raise serializers.ValidationError("A Reflection is too long.")
        return content


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


class ScriptureReferenceEditSerializer(serializers.Serializer):
    book = serializers.CharField(max_length=64, trim_whitespace=True)
    chapter_start = serializers.IntegerField(
        min_value=1,
        max_value=MAX_SCRIPTURE_NUMBER,
    )
    verse_start = serializers.IntegerField(
        min_value=1,
        max_value=MAX_SCRIPTURE_NUMBER,
        allow_null=True,
        required=False,
        default=None,
    )
    chapter_end = serializers.IntegerField(
        min_value=1,
        max_value=MAX_SCRIPTURE_NUMBER,
        allow_null=True,
        required=False,
        default=None,
    )
    verse_end = serializers.IntegerField(
        min_value=1,
        max_value=MAX_SCRIPTURE_NUMBER,
        allow_null=True,
        required=False,
        default=None,
    )

    def validate(self, attrs):
        try:
            return normalize_scripture_reference(**attrs)
        except ValueError as error:
            raise serializers.ValidationError(str(error)) from error


class ScriptureReferencesEditSerializer(serializers.Serializer):
    scripture_references = ScriptureReferenceEditSerializer(
        many=True,
        allow_empty=True,
        max_length=20,
    )

    def validate_scripture_references(self, references):
        identities = [
            (
                reference["book"].casefold(),
                reference["chapter_start"],
                reference["verse_start"],
                reference["chapter_end"],
                reference["verse_end"],
            )
            for reference in references
        ]
        if len(identities) != len(set(identities)):
            raise serializers.ValidationError("Scripture references must be unique.")
        return references


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
    audio_url = serializers.SerializerMethodField()
    transcript = TranscriptSerializer(read_only=True, allow_null=True)
    study_artifacts = StudyArtifactSerializer(many=True, read_only=True)
    scripture_references = ScriptureReferenceSerializer(many=True, read_only=True)
    related_sermons = RelatedSermonSerializer(many=True, read_only=True)
    reflections = ReflectionSerializer(many=True, read_only=True)

    class Meta(SermonSerializer.Meta):
        fields = SermonSerializer.Meta.fields + (
            "audio_url",
            "transcript",
            "study_artifacts",
            "scripture_references",
            "related_sermons",
            "reflections",
        )
        read_only_fields = SermonSerializer.Meta.read_only_fields + (
            "audio_url",
            "transcript",
            "study_artifacts",
            "scripture_references",
            "related_sermons",
            "reflections",
        )

    def get_audio_url(self, sermon: Sermon) -> str:
        request = self.context.get("request")
        return private_audio_url(request, sermon) if request else ""


class PublicSharedSermonSerializer(serializers.ModelSerializer):
    audio_url = serializers.SerializerMethodField()
    church = ChurchSerializer(read_only=True)
    preacher = PreacherSerializer(read_only=True)
    transcript = TranscriptSerializer(read_only=True, allow_null=True)
    study_artifacts = StudyArtifactSerializer(many=True, read_only=True)
    scripture_references = ScriptureReferenceSerializer(many=True, read_only=True)
    tag_suggestions = serializers.SerializerMethodField()

    class Meta:
        model = Sermon
        fields = (
            "captured_at",
            "duration_seconds",
            "church",
            "preacher",
            "occasion_kind",
            "liturgical_day",
            "audio_url",
            "transcript",
            "study_artifacts",
            "scripture_references",
            "tag_suggestions",
            "updated_at",
        )

    def get_audio_url(self, sermon: Sermon) -> str:
        request = self.context.get("request")
        token = self.context.get("share_token")
        if not request or not token:
            return ""
        path = reverse("shared-sermon-audio", kwargs={"token": token})
        return request.build_absolute_uri(path)

    def get_tag_suggestions(self, sermon: Sermon) -> list[str]:
        return [suggestion.name for suggestion in sermon.tag_suggestions.all()]
