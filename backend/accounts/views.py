from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import DeviceRegistration, SavedRecipient
from .serializers import (
    DeviceRegistrationSerializer,
    RegisterSerializer,
    SavedRecipientSerializer,
    SocialLoginSerializer,
    UserSerializer,
)
from .social_auth import (
    InvalidSocialCredential,
    SocialProviderUnavailable,
    resolve_social_user,
    verify_social_identity,
)


class RegisterView(generics.CreateAPIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class SocialLoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            identity = verify_social_identity(
                serializer.validated_data["provider"],
                serializer.validated_data["id_token"],
            )
            user = resolve_social_user(identity)
        except InvalidSocialCredential as error:
            raise ValidationError({"id_token": str(error)}) from error
        except SocialProviderUnavailable as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class CurrentUserView(generics.RetrieveAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class SavedRecipientListCreateView(generics.ListCreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SavedRecipientSerializer

    def get_queryset(self):
        return SavedRecipient.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class SavedRecipientDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = SavedRecipientSerializer

    def get_queryset(self):
        return SavedRecipient.objects.filter(owner=self.request.user)


class DeviceRegistrationCreateView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DeviceRegistrationSerializer


class DeviceRegistrationDeleteView(generics.DestroyAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = DeviceRegistrationSerializer

    def get_queryset(self):
        return DeviceRegistration.objects.filter(owner=self.request.user)
