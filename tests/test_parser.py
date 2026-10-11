"""Test funzioni pure parser Contarina — nessun HA richiesto, nessun network."""

import importlib.util
from datetime import UTC, timedelta
from pathlib import Path
import sys as _sys

_PARSER = Path(__file__).resolve().parents[1] / "custom_components" / "contarina" / "parser.py"
_WASTE_TYPES = _PARSER.with_name("waste_types.py")
_PACKAGE_NAME = "contarina_parser_test_package"
_package_spec = importlib.util.spec_from_loader(_PACKAGE_NAME, loader=None)
assert _package_spec
_package = importlib.util.module_from_spec(_package_spec)
_package.__path__ = [str(_PARSER.parent)]
_sys.modules[_PACKAGE_NAME] = _package
_types_spec = importlib.util.spec_from_file_location(f"{_PACKAGE_NAME}.waste_types", _WASTE_TYPES)
assert _types_spec and _types_spec.loader
_types_mod = importlib.util.module_from_spec(_types_spec)
_sys.modules[_types_spec.name] = _types_mod
_types_spec.loader.exec_module(_types_mod)
_spec = importlib.util.spec_from_file_location(f"{_PACKAGE_NAME}.parser", _PARSER)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

clean_summary = _mod.clean_summary
detect_types = _mod.detect_types
filter_events = _mod.filter_events
parse_ics = _mod.parse_ics
parse_ics_candidate = _mod.parse_ics_candidate

SAMPLE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ZContent.net//ZapCalLib 1.0//EN
BEGIN:VEVENT
DTSTART:20260929T060000
DTEND:20260929T070000
SUMMARY:Giavera del Montello: VPL, Umido
END:VEVENT
BEGIN:VEVENT
DTSTART:20261002T060000
DTEND:20261002T070000
SUMMARY:Giavera del Montello: Vegetale, Umido
END:VEVENT
BEGIN:VEVENT
DTSTART:20261001T060000
DTEND:20261001T070000
SUMMARY:Giavera del Montello: Carta
END:VEVENT
END:VCALENDAR
"""


def test_clean_summary():
    assert clean_summary("Giavera del Montello: Secco") == "Secco"
    assert (
        clean_summary("Treviso - centro storico: VPL, Umido, Vegetale")
        == "VPL, Umido, Vegetale"
    )
    assert clean_summary("SoloTipo") == "SoloTipo"


def test_detect_types_order():
    assert detect_types("VPL, Umido") == ("vpl", "umido")
    assert detect_types("Carta, Secco") == ("carta", "secco")
    assert detect_types("Secco") == ("secco",)


def test_parse_ics_basic():
    evs = parse_ics(SAMPLE, 9)
    assert len(evs) == 3
    # ordinati per data
    assert evs[0].start.day == 29
    assert evs[0].summary == "VPL, Umido"
    assert all(e.start.tzinfo is not None for e in evs)


def test_candidate_allows_only_null_trailer_after_calendar():
    with_trailer = SAMPLE + "\nnull\n"
    assert parse_ics_candidate(with_trailer, 9) == parse_ics(SAMPLE, 9)
    assert parse_ics_candidate(SAMPLE + "\r\n NULL \r\n", 9) == parse_ics(SAMPLE, 9)
    assert parse_ics_candidate(with_trailer + "garbage\n", 9) is None
    assert parse_ics_candidate(SAMPLE.replace("END:VCALENDAR", "null\nEND:VCALENDAR"), 9) is None
    assert parse_ics_candidate(SAMPLE + "garbage\nnull\n", 9) is None


def test_parse_ics_folding():
    folded = (
        "BEGIN:VCALENDAR\n"
        "BEGIN:VEVENT\r\nDTSTART:20260929T060000\r\nDTEND:20260929T070000\r\n"
        "SUMMARY:Giavera del \r\n Montello: VPL, Umido\r\nEND:VEVENT\nEND:VCALENDAR"
    )
    evs = parse_ics(folded, 9)
    assert len(evs) == 1
    assert evs[0].summary == "VPL, Umido"


def test_filter_events():
    evs = parse_ics(SAMPLE, 9)
    filt = filter_events(
        evs, {"secco": False, "umido": True, "carta": True, "vpl": True, "vegetale": True}
    )
    assert all("secco" not in e.types for e in filt)
    # VPL, Umido resta; Carta resta
    assert len(filt) == 3
    filt2 = filter_events(
        evs, {"secco": True, "umido": True, "carta": True, "vpl": False, "vegetale": False}
    )
    # VPL,Umido -> Umido ; Vegetale,Umido -> Umido ; Carta resta
    assert any(e.summary == "Umido" for e in filt2)
    assert any(e.summary == "Carta" for e in filt2)


def test_filter_drops_empty():
    evs = parse_ics(SAMPLE, 9)
    filt = filter_events(
        evs,
        {"secco": False, "umido": False, "carta": False, "vpl": False, "vegetale": False},
    )
    assert filt == []


def test_parse_ics_parameters_utc_and_text_escapes():
    content = r"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;TZID=Europe/Rome:20261001T060000
DTEND;TZID=Europe/Rome:20261001T070000
SUMMARY;LANGUAGE=it:Giavera del Montello: VPL\, Umido
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261002
DTEND;VALUE=DATE:20261003
SUMMARY:Giavera del Montello: Carta
END:VEVENT
BEGIN:VEVENT
DTSTART:20261004T040000Z
SUMMARY:Giavera del Montello: Secco
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20261005
SUMMARY:Giavera del Montello: Vegetale
END:VEVENT
END:VCALENDAR
"""
    events = parse_ics(content, 9)

    assert len(events) == 4
    assert events[0].summary == "VPL, Umido"
    assert events[0].start.hour == 6
    assert events[1].start.hour == 0
    assert events[1].end.day == 3  # DTEND DATE è esclusivo
    assert events[2].start.hour == 6  # 04:00 UTC convertito in Europe/Rome
    assert events[3].end.day == 6  # DTSTART DATE senza DTEND dura l'intera giornata


def test_parse_ics_candidate_rejects_bad_feed_but_accepts_empty_calendar():
    empty_calendar = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Contarina//EN\nEND:VCALENDAR\n"
    )
    assert parse_ics_candidate(SAMPLE, 9) == parse_ics(SAMPLE, 9)
    assert parse_ics_candidate(empty_calendar, 9) == []

    missing_calendar_envelope = """BEGIN:VEVENT
DTSTART:20260929T060000
SUMMARY:Giavera del Montello: Umido
END:VEVENT
"""
    no_recognized_events = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260929T060000
SUMMARY:Giavera del Montello: Ingombranti
END:VEVENT
END:VCALENDAR
"""
    assert parse_ics_candidate(missing_calendar_envelope, 9) is None
    assert parse_ics_candidate(no_recognized_events, 9) is None


def test_parse_ics_candidate_rejects_invalid_dtend():
    invalid_dtend = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Contarina//EN
BEGIN:VEVENT
DTSTART:20260929T060000
DTEND;TZID=Unknown/Zone:20260929T070000
SUMMARY:Giavera del Montello: Umido
END:VEVENT
END:VCALENDAR
    """
    assert parse_ics_candidate(invalid_dtend, 9) is None


def test_candidate_rejects_component_line_without_colon_and_accepts_unknown_property():
    template = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Contarina//EN
BEGIN:VEVENT
DTSTART:20260929T060000
SUMMARY:Giavera del Montello: Umido
{extra}
END:VEVENT
END:VCALENDAR
"""
    assert parse_ics_candidate(template.format(extra="BROKEN PROPERTY"), 9) is None

    events = parse_ics_candidate(template.format(extra="X-EXTRA:opaque value"), 9)
    assert events is not None and len(events) == 1


def test_candidate_rejects_invalid_property_name_but_accepts_grouped_property():
    template = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Contarina//EN
BEGIN:VEVENT
DTSTART:20260929T060000
SUMMARY:Giavera del Montello: Umido
{extra}
END:VEVENT
END:VCALENDAR
"""
    assert parse_ics_candidate(template.format(extra="BROKEN PROPERTY:foo"), 9) is None
    assert parse_ics_candidate(template.format(extra="item1.X-EXTRA:opaque value"), 9)


def test_parse_ics_candidate_requires_matching_date_value_types():
    def calendar(start, end):
        return f"""BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Contarina//EN
BEGIN:VEVENT\n{start}\n{end}\nSUMMARY:Giavera del Montello: Umido
END:VEVENT\nEND:VCALENDAR\n"""

    assert parse_ics_candidate(
        calendar("DTSTART;VALUE=DATE:20260929", "DTEND:20260930T000000"), 9
    ) is None
    assert parse_ics_candidate(
        calendar("DTSTART:20260929T060000", "DTEND;VALUE=DATE:20260929"), 9
    ) is None
    assert parse_ics_candidate(
        calendar("DTSTART;VALUE=DATE:20260929", "DTEND;VALUE=DATE:20260930"), 9
    )
    assert parse_ics_candidate(
        calendar("DTSTART:20260929T060000", "DTEND:20260929T070000"), 9
    )


def test_candidate_accepts_timezone_and_alarm_components():
    content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Contarina//EN
BEGIN:VTIMEZONE
TZID:Europe/Rome
BEGIN:STANDARD
DTSTART:20261025T030000
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20260329T020000
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
END:DAYLIGHT
END:VTIMEZONE
BEGIN:VEVENT
DTSTART:20260929T060000
SUMMARY:Giavera del Montello: Umido
BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT1H
DESCRIPTION:Reminder
END:VALARM
END:VEVENT
END:VCALENDAR
"""
    events = parse_ics_candidate(content, 9)
    assert events is not None and len(events) == 1


def test_candidate_rejects_malformed_envelopes_and_components():
    base = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Contarina//EN\n{}\nEND:VCALENDAR\n"
    assert parse_ics_candidate(base.format(
        "BEGIN:VEVENT\nSUMMARY:Umido\nBEGIN:VALARM\nACTION:DISPLAY\nEND:VEVENT"
    ), 9) is None
    assert parse_ics_candidate(base.format(
        "BEGIN:VTIMEZONE\nTZID:Europe/Rome\nBEGIN:STANDARD\nEND:VTIMEZONE"
    ), 9) is None
    assert parse_ics_candidate(
        "VERSION:2.0\nPRODID:-//Contarina//EN\n" + base.format(""), 9
    ) is None
    assert parse_ics_candidate(base.format("") + "BEGIN:VCALENDAR\nEND:VCALENDAR\n", 9) is None


def test_parse_ics_keeps_repeated_dst_hour_order_by_utc_instant():
    # In Europe/Rome, 02:30 occurs twice when DST ends on 2026-10-25.
    content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Contarina//EN
BEGIN:VEVENT
DTSTART:20261025T003000Z
DTEND:20261025T013000Z
SUMMARY:Giavera del Montello: Umido
END:VEVENT
END:VCALENDAR
"""
    events = parse_ics_candidate(content, 9)

    assert events is not None and len(events) == 1
    event = events[0]
    assert event.start.hour == event.end.hour == 2
    assert event.start.utcoffset() != event.end.utcoffset()
    assert event.end.astimezone(UTC) - event.start.astimezone(UTC) == timedelta(hours=1)
