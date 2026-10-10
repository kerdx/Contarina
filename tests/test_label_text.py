import importlib.util
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components/contarina/label_text.py"
)
_SPEC = importlib.util.spec_from_file_location("contarina_label_text", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

label_when = _MODULE.label_when
language_code = _MODULE.language_code
weekday_name = _MODULE.weekday_name
when_attribute = _MODULE.when_attribute


def test_italian_label_text():
    assert label_when(0, "it-IT") == "Oggi"
    assert label_when(1, "it") == "Domani"
    assert label_when(2, "it") == "Dopodomani"
    assert weekday_name(0, "it", capitalize=True) == "Lunedì"
    assert when_attribute(1, "it") == "domani"


def test_english_and_explicit_fallback():
    assert label_when(0, "en-US") == "Today"
    assert label_when(2, "en") == "Day after tomorrow"
    assert weekday_name(6, "en") == "Sunday"
    assert when_attribute(5, "en") == "upcoming_days"
    assert language_code("fr") == "en"
    assert label_when(1, None) == "Tomorrow"
