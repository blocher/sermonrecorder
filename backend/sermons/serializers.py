from rest_framework import serializers

from .models import Sermon

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
            "processing_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "audio_mime_type",
            "audio_size_bytes",
            "processing_status",
            "processing_error",
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
