from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import SavedRecipient, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "display_name")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("email", "display_name", "password")

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class SavedRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedRecipient
        fields = ("id", "name", "email", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise serializers.ValidationError("Give this recipient a name.")
        return name

    def validate_email(self, email: str) -> str:
        return email.strip().lower()

    def validate(self, attrs):
        request = self.context["request"]
        email = attrs.get("email", getattr(self.instance, "email", None))
        existing = SavedRecipient.objects.filter(owner=request.user, email=email)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError(
                {"email": "This email is already in your saved recipients."}
            )
        return attrs
