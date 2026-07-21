def normalize_tag(name: str) -> tuple[str, str]:
    display_name = " ".join(name.split())
    if not display_name or len(display_name) > 80:
        raise ValueError("A Tag must be between 1 and 80 characters.")
    return display_name, display_name.casefold()
