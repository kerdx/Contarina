"""Pure helpers for language-dependent label sensor text."""

_WEEKDAYS = {
    "it": (
        "lunedì",
        "martedì",
        "mercoledì",
        "giovedì",
        "venerdì",
        "sabato",
        "domenica",
    ),
    "en": (
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ),
}


def language_code(language: str | None) -> str:
    """Return a supported language, explicitly falling back to English."""
    code = (language or "").replace("_", "-").split("-", 1)[0].lower()
    return code if code in _WEEKDAYS else "en"


def label_when(days: int, language: str | None) -> str:
    lang = language_code(language)
    if days == 0:
        return "Oggi" if lang == "it" else "Today"
    if days == 1:
        return "Domani" if lang == "it" else "Tomorrow"
    if days == 2:
        return "Dopodomani" if lang == "it" else "Day after tomorrow"
    return "upcoming days" if lang == "en" else "prossimi giorni"


def weekday_name(day: int, language: str | None, *, capitalize: bool = False) -> str:
    name = _WEEKDAYS[language_code(language)][day]
    return name.capitalize() if capitalize else name


def when_attribute(days: int, language: str | None) -> str:
    lang = language_code(language)
    if days == 0:
        return "oggi" if lang == "it" else "today"
    if days == 1:
        return "domani" if lang == "it" else "tomorrow"
    return "prossimi_giorni" if lang == "it" else "upcoming_days"
