import re

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_WRAP_PAIRS = {('"', '"'), ("“", "”"), ("‘", "’"), ("'", "'")}
_ENDING_PUNCTUATION = ".!?"


def quotation_words(text: str) -> tuple[str, ...]:
    return tuple(_WORD_RE.findall(text.casefold()))


def strip_wrapping_quotes(text: str) -> str:
    quotation = " ".join(text.split())
    if len(quotation) >= 2 and (quotation[0], quotation[-1]) in _WRAP_PAIRS:
        return quotation[1:-1].strip()
    return quotation


def quotation_matches_transcript(quotation: str, transcript: str) -> bool:
    """True when the quotation's words appear contiguously in the Transcript."""
    needle = quotation_words(quotation)
    if not needle:
        return False
    haystack = quotation_words(transcript)
    width = len(needle)
    return any(haystack[index : index + width] == needle for index in range(len(haystack) - width + 1))


def normalize_quotation_display(quotation: str) -> str:
    """Light display polish: casing and terminal punctuation, words unchanged."""
    text = strip_wrapping_quotes(quotation)
    if not text:
        return text
    for index, character in enumerate(text):
        if character.isalpha():
            text = f"{text[:index]}{character.upper()}{text[index + 1 :]}"
            break
    if text[-1] not in _ENDING_PUNCTUATION and text[-1] not in "…’”'\"":
        text = f"{text}."
    return text


def accepted_quotations(items: list[str], transcript: str) -> tuple[str, ...]:
    quotations: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for item in items:
        candidate = strip_wrapping_quotes(item)
        if not candidate or not quotation_matches_transcript(candidate, transcript):
            continue
        display = normalize_quotation_display(candidate)
        identity = quotation_words(display)
        if not identity or identity in seen:
            continue
        seen.add(identity)
        quotations.append(display)
    return tuple(quotations)
