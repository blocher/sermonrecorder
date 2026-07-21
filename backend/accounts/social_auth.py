from dataclasses import dataclass
from functools import lru_cache

import jwt
from django.conf import settings
from django.db import transaction
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token

from .models import ExternalIdentity, User


class InvalidSocialCredential(Exception):
    pass


class SocialProviderUnavailable(Exception):
    pass


@dataclass(frozen=True)
class VerifiedSocialIdentity:
    provider: str
    subject: str
    email: str | None
    display_name: str = ""


def _audiences(provider: str) -> tuple[str, ...]:
    values = (
        settings.GOOGLE_OAUTH_CLIENT_IDS
        if provider == ExternalIdentity.Provider.GOOGLE
        else settings.APPLE_OAUTH_CLIENT_IDS
    )
    audiences = tuple(value for value in values if value)
    if not audiences:
        raise SocialProviderUnavailable(
            f"{provider.title()} sign-in is not configured."
        )
    return audiences


def _verified_email(claims: dict) -> str | None:
    email = claims.get("email")
    if not email:
        return None
    verified = claims.get("email_verified")
    if verified not in (True, "true"):
        raise InvalidSocialCredential("The provider did not verify this email address.")
    return str(email).strip().lower()


def _verify_google(id_token: str) -> VerifiedSocialIdentity:
    audiences = _audiences(ExternalIdentity.Provider.GOOGLE)
    try:
        claims = google_id_token.verify_oauth2_token(
            id_token,
            GoogleAuthRequest(),
            audience=None,
        )
    except Exception as error:
        raise InvalidSocialCredential(
            "Google rejected this sign-in credential."
        ) from error
    if claims.get("aud") not in audiences:
        raise InvalidSocialCredential("This Google credential belongs to another app.")
    subject = str(claims.get("sub", "")).strip()
    if not subject:
        raise InvalidSocialCredential("Google did not identify this account.")
    return VerifiedSocialIdentity(
        provider=ExternalIdentity.Provider.GOOGLE,
        subject=subject,
        email=_verified_email(claims),
        display_name=str(claims.get("name", "")).strip(),
    )


@lru_cache(maxsize=1)
def _apple_key_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient("https://appleid.apple.com/auth/keys")


def _verify_apple(id_token: str) -> VerifiedSocialIdentity:
    audiences = _audiences(ExternalIdentity.Provider.APPLE)
    try:
        signing_key = _apple_key_client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=("RS256",),
            audience=audiences,
            issuer="https://appleid.apple.com",
            options={"require": ("exp", "iat", "iss", "aud", "sub")},
        )
    except Exception as error:
        raise InvalidSocialCredential(
            "Apple rejected this sign-in credential."
        ) from error
    subject = str(claims.get("sub", "")).strip()
    if not subject:
        raise InvalidSocialCredential("Apple did not identify this account.")
    return VerifiedSocialIdentity(
        provider=ExternalIdentity.Provider.APPLE,
        subject=subject,
        email=_verified_email(claims),
    )


def verify_social_identity(provider: str, id_token: str) -> VerifiedSocialIdentity:
    if provider == ExternalIdentity.Provider.GOOGLE:
        return _verify_google(id_token)
    if provider == ExternalIdentity.Provider.APPLE:
        return _verify_apple(id_token)
    raise InvalidSocialCredential("Choose Apple or Google sign-in.")


@transaction.atomic
def resolve_social_user(identity: VerifiedSocialIdentity) -> User:
    linked = (
        ExternalIdentity.objects.select_for_update()
        .select_related("owner")
        .filter(provider=identity.provider, subject=identity.subject)
        .first()
    )
    if linked:
        if not linked.owner.is_active:
            raise InvalidSocialCredential("This Pewcorder account is unavailable.")
        return linked.owner
    if not identity.email:
        raise InvalidSocialCredential(
            "This provider no longer shared an email address and the account is not linked."
        )

    user = User.objects.select_for_update().filter(email__iexact=identity.email).first()
    if user is not None and not user.is_active:
        raise InvalidSocialCredential("This Pewcorder account is unavailable.")
    if user is None:
        user = User.objects.create_user(
            email=identity.email,
            password=None,
            display_name=identity.display_name,
        )
    ExternalIdentity.objects.create(
        owner=user,
        provider=identity.provider,
        subject=identity.subject,
    )
    return user
