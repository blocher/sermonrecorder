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
from django.views.decorators.http import require_GET

from .models import Sermon

AUDIO_TOKEN_SALT = "pewcorder.private-sermon-audio"
RANGE_PATTERN = re.compile(r"^bytes=(\d*)-(\d*)$")


def private_audio_url(request: HttpRequest, sermon: Sermon) -> str:
    token = signing.dumps(
        {
            "sermon_id": str(sermon.id),
            "owner_id": str(sermon.owner_id),
        },
        salt=AUDIO_TOKEN_SALT,
        compress=True,
    )
    path = reverse("sermon-private-audio", kwargs={"sermon_id": sermon.id})
    return request.build_absolute_uri(f"{path}?{urlencode({'token': token})}")


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
    audio = sermon.audio.open("rb")
    size = sermon.audio_size_bytes
    filename = Path(sermon.audio.name).name
    range_header = request.headers.get("Range")

    if not range_header:
        response = FileResponse(audio, content_type=sermon.audio_mime_type)
        response["Content-Length"] = size
    else:
        bounds = _range_bounds(range_header, size)
        if bounds is None:
            audio.close()
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
            return response

        start, end = bounds
        length = end - start + 1
        response = StreamingHttpResponse(
            _file_range(audio, start, length),
            status=206,
            content_type=sermon.audio_mime_type,
        )
        response["Content-Length"] = length
        response["Content-Range"] = f"bytes {start}-{end}/{size}"

    response["Accept-Ranges"] = "bytes"
    response["Content-Disposition"] = content_disposition_header(False, filename)
    response["Cache-Control"] = "private, max-age=3600"
    return response


@require_GET
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
