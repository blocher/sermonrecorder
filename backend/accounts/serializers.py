from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import DeviceRegistration, SavedRecipient, User


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


class DeviceRegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceRegistration
        fields = ("id", "platform", "token", "active", "created_at", "updated_at")
        read_only_fields = ("id", "active", "created_at", "updated_at")
        extra_kwargs = {"token": {"write_only": True, "validators": []}}

    def validate_token(self, token: str) -> str:
        token = token.strip()
        if not token:
            raise serializers.ValidationError("A native push token is required.")
        return token

    def create(self, validated_data):
        owner = self.context["request"].user
        with transaction.atomic():
            registration = (
                DeviceRegistration.objects.select_for_update()
                .filter(token=validated_data["token"])
                .first()
            )
            if registration is None:
                return DeviceRegistration.objects.create(
                    owner=owner,
                    platform=validated_data["platform"],
                    token=validated_data["token"],
                )
            if registration.owner_id != owner.id:
                registration.processing_alerts.filter(
                    delivery_status__in=("pending", "delivering")
                ).delete()
            registration.owner = owner
            registration.platform = validated_data["platform"]
            registration.active = True
            registration.save(
                update_fields=("owner", "platform", "active", "updated_at")
            )
            return registration
