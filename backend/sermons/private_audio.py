import re
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.http import FileResponse, HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_http_methods

from .audio_faststart import m4a_moov_exclusive_end
from .models import Sermon

AUDIO_TOKEN_SALT = "pewcorder.private-sermon-audio"
RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")
# iOS Safari often asks for ~1–2 KiB first; that is smaller than a typical moov.
_MIN_PREFIX_RANGE_BYTES = 512 * 1024


def private_audio_url(
    request: HttpRequest,
    sermon: Sermon,
    *,
    variant: str | None = None,
) -> str:
    token = signing.dumps(
        {
            "sermon_id": str(sermon.id),
            "owner_id": str(sermon.owner_id),
        },
        salt=AUDIO_TOKEN_SALT,
        compress=True,
    )
    path = reverse("sermon-private-audio", kwargs={"sermon_id": sermon.id})
    params: dict[str, str] = {"token": token}
    if variant:
        params["variant"] = variant
    return request.build_absolute_uri(f"{path}?{urlencode(params)}")


def _audio_variant(request: HttpRequest) -> str:
    return (request.GET.get("variant") or "").strip().lower()


def _resolve_sermon_audio(sermon: Sermon, variant: str):
    if variant == "original":
        return sermon.audio, sermon.audio_mime_type, sermon.audio_size_bytes
    if variant == "playback":
        if not sermon.playback_audio:
            return None
        return (
            sermon.playback_audio,
            sermon.playback_audio_mime_type or "audio/mp4",
            sermon.playback_audio_size_bytes
            if sermon.playback_audio_size_bytes is not None
            else sermon.playback_audio.size,
        )
    return (
        sermon.listening_audio_file(),
        sermon.listening_audio_mime_type(),
        sermon.listening_audio_size_bytes(),
    )


def _range_bounds(header: str, size: int) -> tuple[int, int] | None:
    match = RANGE_PATTERN.fullmatch(header.strip())
    if not match:
        return None

    start_text, end_text = match.groups()
    if not start_text:
        if not end_text:
            return None
        suffix_length = int(end_text)
        if suffix_length <= 0:
            return None
        return max(0, size - suffix_length), size - 1

    start = int(start_text)
    end = int(end_text) if end_text else size - 1
    if start >= size or end < start:
        return None
    return start, min(end, size - 1)


def _expand_ios_prefix_range(
    audio_file,
    start: int,
    end: int,
    size: int,
) -> tuple[int, int]:
    """Widen tiny ``bytes=0-N`` probes so the response includes the moov atom.

    Chrome/Safari on iOS commonly request the first ~1.4 KiB, then give up if
    moov is larger and a follow-up range never arrives.
    """
    if start != 0 or end >= size - 1:
        return start, end
    if (end - start + 1) >= _MIN_PREFIX_RANGE_BYTES:
        return start, end

    target_end = _MIN_PREFIX_RANGE_BYTES - 1
    try:
        moov_end = m4a_moov_exclusive_end(Path(audio_file.path))
    except (NotImplementedError, ValueError, OSError):
        moov_end = None
    if moov_end is not None:
        target_end = max(target_end, moov_end - 1)
    return start, min(size - 1, max(end, target_end))


def _file_range(file, start: int, length: int) -> Iterator[bytes]:
    try:
        file.seek(start)
        remaining = length
        while remaining > 0:
            chunk = file.read(min(64 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        file.close()


def sermon_audio_response(request: HttpRequest, sermon: Sermon) -> HttpResponse:
    resolved = _resolve_sermon_audio(sermon, _audio_variant(request))
    if resolved is None:
        return HttpResponse(status=404)

    audio_file, content_type, size = resolved
    audio = audio_file.open("rb")
    filename = Path(audio_file.name).name
    range_header = request.headers.get("Range")

    if not range_header:
        response = FileResponse(audio, content_type=content_type)
        response["Content-Length"] = size
    else:
        bounds = _range_bounds(range_header, size)
        if bounds is None:
            audio.close()
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response

        start, end = _expand_ios_prefix_range(audio_file, *bounds, size)
        length = end - start + 1
        response = StreamingHttpResponse(
            _file_range(audio, start, length),
            status=206,
            content_type=content_type,
        )
        response["Content-Length"] = length
        response["Content-Range"] = f"bytes {start}-{end}/{size}"

    response["Accept-Ranges"] = "bytes"
    # Keep disposition optional; some iOS WebViews mishandle filename on media.
    response["Content-Disposition"] = content_disposition_header(False, filename)
    response["Cache-Control"] = "private, max-age=3600"
    return response


@require_http_methods(["GET", "HEAD"])
def sermon_private_audio(request: HttpRequest, sermon_id: UUID) -> HttpResponse:
    token = request.GET.get("token", "")
    try:
        payload = signing.loads(
            token,
            salt=AUDIO_TOKEN_SALT,
            max_age=settings.SERMON_AUDIO_URL_MAX_AGE_SECONDS,
        )
    except (signing.BadSignature, signing.SignatureExpired):
        return HttpResponse(status=403)

    if payload.get("sermon_id") != str(sermon_id):
        return HttpResponse(status=403)

    sermon = get_object_or_404(
        Sermon,
        id=sermon_id,
        owner_id=payload.get("owner_id"),
    )
    return sermon_audio_response(request, sermon)
