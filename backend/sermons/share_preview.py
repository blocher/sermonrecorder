"""Open Graph / link-unfurl metadata for public Share Links."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.html import escape

from .models import Sermon, StudyArtifact


def _format_share_date(captured_at) -> str:
    local = timezone.localtime(captured_at)
    return f"{local.strftime('%b')} {local.day}, {local.year}"

# iMessage / Slack / Discord show roughly two short lines of description.
_DESCRIPTION_MAX_CHARS = 220
_SUMMARY_MAX_CHARS = 140

_TITLE_RE = re.compile(
    r"<title[^>]*>.*?</title>",
    flags=re.IGNORECASE | re.DOTALL,
)
_DESCRIPTION_META_RE = re.compile(
    r'<meta\s+name=["\']description["\'][^>]*>',
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class SharePreview:
    title: str
    description: str
    page_title: str


def _short_summary(sermon: Sermon) -> str:
    artifact = next(
        (
            artifact
            for artifact in sermon.study_artifacts.all()
            if artifact.kind == StudyArtifact.Kind.SHORT_SUMMARY
        ),
        None,
    )
    return (artifact.content or "").strip() if artifact else ""


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, max_chars: int) -> str:
    text = _collapse_whitespace(text)
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars - 1].rstrip(" .,;:—-")
    return f"{clipped}…"


def _sermon_title(sermon: Sermon) -> str:
    title = (sermon.title or "").strip()
    if title:
        return title
    return f"Sermon · {_format_share_date(sermon.captured_at)}"


def build_share_preview(sermon: Sermon) -> SharePreview:
    title = _sermon_title(sermon)
    date_label = _format_share_date(sermon.captured_at)

    identity_bits: list[str] = []
    if sermon.preacher and sermon.preacher.name.strip():
        identity_bits.append(sermon.preacher.name.strip())
    identity_bits.append(date_label)
    if sermon.church and sermon.church.name.strip():
        identity_bits.append(sermon.church.name.strip())

    parts = [" · ".join(identity_bits)]
    liturgical = (sermon.liturgical_day or "").strip()
    if liturgical:
        parts.append(liturgical)

    summary = _truncate(_short_summary(sermon), _SUMMARY_MAX_CHARS)
    if summary:
        parts.append(summary)

    # Single-line descriptions unfurl more reliably in iMessage and Slack.
    description = _truncate(" — ".join(parts), _DESCRIPTION_MAX_CHARS)
    return SharePreview(
        title=title,
        description=description,
        page_title=f"{title} · Pewcorder",
    )


def share_page_canonical_url(token: str) -> str:
    base = settings.PEWCORDER_PUBLIC_WEB_URL.rstrip("/")
    return f"{base}/share/{token}"


def share_og_image_url() -> str:
    base = settings.PEWCORDER_PUBLIC_WEB_URL.rstrip("/")
    return f"{base}/og-share.png"


def _meta_tags(*, preview: SharePreview, canonical_url: str, image_url: str) -> str:
    title = escape(preview.title)
    description = escape(preview.description)
    page_title = escape(preview.page_title)
    url = escape(canonical_url)
    image = escape(image_url)
    return "\n".join(
        (
            f"<title>{page_title}</title>",
            f'<meta name="description" content="{description}" />',
            f'<link rel="canonical" href="{url}" />',
            f'<meta property="og:site_name" content="Pewcorder" />',
            f'<meta property="og:type" content="article" />',
            f'<meta property="og:title" content="{title}" />',
            f'<meta property="og:description" content="{description}" />',
            f'<meta property="og:url" content="{url}" />',
            f'<meta property="og:image" content="{image}" />',
            f'<meta property="og:image:width" content="1200" />',
            f'<meta property="og:image:height" content="630" />',
            f'<meta property="og:image:alt" content="Pewcorder" />',
            f'<meta name="twitter:card" content="summary_large_image" />',
            f'<meta name="twitter:title" content="{title}" />',
            f'<meta name="twitter:description" content="{description}" />',
            f'<meta name="twitter:image" content="{image}" />',
        )
    )


def inject_share_preview_meta(
    html_document: str,
    *,
    preview: SharePreview,
    canonical_url: str,
    image_url: str,
) -> str:
    tags = _meta_tags(
        preview=preview,
        canonical_url=canonical_url,
        image_url=image_url,
    )
    document = _TITLE_RE.sub("", html_document, count=1)
    document = _DESCRIPTION_META_RE.sub("", document, count=1)
    if "</head>" not in document.lower():
        return f"{tags}\n{document}"
    # Preserve original casing of the closing head tag.
    match = re.search(r"</head>", document, flags=re.IGNORECASE)
    assert match is not None
    insert_at = match.start()
    return f"{document[:insert_at]}{tags}\n{document[insert_at:]}"


def load_spa_shell_html() -> str | None:
    dist_dir = Path(settings.PEWCORDER_WEB_DIST_DIR)
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        return None
    return index_path.read_text(encoding="utf-8")


def render_share_preview_html(
    *,
    preview: SharePreview,
    canonical_url: str,
    image_url: str | None = None,
) -> str:
    image = image_url or share_og_image_url()
    shell = load_spa_shell_html()
    if shell is not None:
        return inject_share_preview_meta(
            shell,
            preview=preview,
            canonical_url=canonical_url,
            image_url=image,
        )

    # Fallback when the built SPA is unavailable (tests / misconfigured deploy).
    tags = _meta_tags(
        preview=preview,
        canonical_url=canonical_url,
        image_url=image,
    )
    safe_url = escape(canonical_url)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
        f"{tags}\n"
        "</head>\n"
        "<body>\n"
        "<p>Opening shared sermon…</p>\n"
        f'<p><a href="{safe_url}">Continue to Pewcorder</a></p>\n'
        "</body>\n"
        "</html>\n"
    )
