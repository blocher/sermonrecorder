MAX_SCRIPTURE_NUMBER = 32_767


def normalize_scripture_reference(
    *,
    book: str,
    chapter_start: int,
    verse_start: int | None,
    chapter_end: int | None,
    verse_end: int | None,
) -> dict[str, str | int | None]:
    normalized_book = " ".join(book.split())
    if not normalized_book or len(normalized_book) > 64:
        raise ValueError("A Scripture book must be between 1 and 64 characters.")

    numbered_fields = {
        "Starting chapter": chapter_start,
        "Starting verse": verse_start,
        "Ending chapter": chapter_end,
        "Ending verse": verse_end,
    }
    for label, value in numbered_fields.items():
        if value is not None and (value < 1 or value > MAX_SCRIPTURE_NUMBER):
            raise ValueError(f"{label} must be between 1 and {MAX_SCRIPTURE_NUMBER}.")

    if chapter_end is not None and chapter_end < chapter_start:
        raise ValueError("The ending chapter cannot precede the starting chapter.")
    if chapter_end == chapter_start:
        chapter_end = None
    if verse_end is not None and verse_start is None and chapter_end is None:
        raise ValueError("Give a starting verse before an ending verse.")
    if (
        verse_start is not None
        and verse_end is not None
        and chapter_end in (None, chapter_start)
        and verse_end < verse_start
    ):
        raise ValueError("The ending verse cannot precede the starting verse.")

    return {
        "book": normalized_book,
        "chapter_start": chapter_start,
        "verse_start": verse_start,
        "chapter_end": chapter_end,
        "verse_end": verse_end,
    }
