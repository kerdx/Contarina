"""Test funzioni pure parser Contarina — nessun HA richiesto, nessun network."""

import importlib.util
from pathlib import Path
import sys as _sys

_PARSER = Path(__file__).resolve().parents[1] / "custom_components" / "contarina" / "parser.py"
_spec = importlib.util.spec_from_file_location("contarina_parser", _PARSER)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_sys.modules["contarina_parser"] = _mod
_spec.loader.exec_module(_mod)

clean_summary = _mod.clean_summary
detect_types = _mod.detect_types
filter_events = _mod.filter_events
parse_ics = _mod.parse_ics

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
