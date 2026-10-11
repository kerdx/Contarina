"""Parsing ICS Contarina — funzioni pure, senza dipendenze Home Assistant.

Separato dal coordinator per permettere test pytest senza HA.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .waste_types import (
    WASTE_LABELS as _CANONICAL_LABELS,
    WASTE_TYPES as _CANONICAL_ORDER,
)

_LOGGER = logging.getLogger(__name__)

ROME_TZ = ZoneInfo("Europe/Rome")

_SUMMARY_ESCAPE_RE = re.compile(r"\\([nN,;\\])")
_DATE_RE = re.compile(r"\d{8}")
_DATE_TIME_RE = re.compile(r"\d{8}T\d{6}Z?")
_PROPERTY_NAME_RE = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)?\Z", re.ASCII)

_DATE_ONLY = "DATE"


@dataclass(frozen=True)
class WasteEvent:
    """Singolo svuotamento."""

    start: datetime
    end: datetime
    summary: str  # es. "VPL, Umido" (senza prefisso comune)
    types: tuple[str, ...]  # chiavi, es. ("vpl", "umido")
    uid: str


def _unfold_ics(content: str) -> str:
    """Rimuove il folding RFC5545 (righe che iniziano con spazio/tab)."""
    return re.sub(r"\r?\n[ \t]", "", content)


def _extract_event_blocks(content: str) -> tuple[list[str], bool]:
    """Estrae gli eventi e valida struttura e annidamento RFC5545."""
    lines = _unfold_ics(content.lstrip("\ufeff")).splitlines()
    blocks: list[str] = []
    stack: list[str] = []
    current_event: list[str] | None = None
    root_properties: set[str] = set()
    valid = True
    root_count = 0
    root_closed = False
    allowed = {
        "VCALENDAR": {"VEVENT", "VTODO", "VJOURNAL", "VFREEBUSY", "VTIMEZONE"},
        "VEVENT": {"VALARM"}, "VTODO": {"VALARM"},
        "VTIMEZONE": {"STANDARD", "DAYLIGHT"},
    }

    for line in lines:
        text = line.strip()
        if not text:
            continue
        marker = text.upper()
        if marker.startswith("BEGIN:"):
            component = marker[6:]
            if not component:
                valid = False
                continue
            if not stack:
                if component != "VCALENDAR" or root_count or root_closed:
                    valid = False
                root_count += 1
            else:
                parent = stack[-1]
                if component not in allowed.get(parent, set()) and not component.startswith("X-"):
                    valid = False
            stack.append(component)
            if component == "VEVENT":
                if current_event is not None:
                    valid = False
                current_event = []
            elif current_event is not None:
                current_event.append(line)
            continue
        if marker.startswith("END:"):
            component = marker[4:]
            if not stack or stack[-1] != component:
                valid = False
                continue
            if component == "VEVENT" and current_event is not None:
                blocks.append("\n".join(current_event))
                current_event = None
            elif current_event is not None:
                current_event.append(line)
            stack.pop()
            if component == "VCALENDAR":
                root_closed = True
            continue
        if not stack:
            valid = False
        else:
            # Ogni riga non vuota in un componente deve essere una content-line
            # (nome non vuoto seguito dal separatore ':'). Le righe strutturali
            # BEGIN/END sono gestite sopra.
            prop = _parse_property(text)
            if prop is None or not prop[0]:
                valid = False
            elif len(stack) == 1 and stack[0] == "VCALENDAR":
                root_properties.add(f"{prop[0]}:{prop[2]}".upper())
        if current_event is not None:
            current_event.append(line)

    valid = valid and not stack and current_event is None and root_count == 1 and root_closed
    valid = valid and "VERSION:2.0" in root_properties and any(
        item.startswith("PRODID:") for item in root_properties
    )
    return blocks, valid


def _parse_property(line: str) -> tuple[str, dict[str, str], str] | None:
    """Divide una content line ICS in nome, parametri e valore."""
    head, separator, value = line.partition(":")
    if not separator:
        return None

    parts = head.split(";")
    # RFC5545 consente i gruppi opzionali, per esempio item1.DTSTART.
    qualified_name = parts[0]
    if not _PROPERTY_NAME_RE.fullmatch(qualified_name):
        return None
    name = qualified_name.rsplit(".", 1)[-1].upper()
    params: dict[str, str] = {}
    for part in parts[1:]:
        key, equals, param_value = part.partition("=")
        if equals:
            params[key.upper()] = param_value.strip().strip('"')
    return name, params, value


def _parse_dt(value: str, params: dict[str, str] | None = None) -> datetime | None:
    """Parsa date e date-time ICS, restituendo sempre un datetime Europe/Rome.

    Le date locali senza TZID sono interpretate in Europe/Rome, come l'API
    Contarina. Le date UTC e quelle con TZID vengono convertite in tale zona.
    """
    params = params or {}
    value = value.strip()
    value_type = params.get("VALUE", "").upper()

    try:
        if value_type == "DATE" or (
            not value_type and _DATE_RE.fullmatch(value)
        ):
            if not _DATE_RE.fullmatch(value):
                return None
            parsed = datetime.strptime(value, "%Y%m%d")
            return parsed.replace(tzinfo=ROME_TZ)

        if not _DATE_TIME_RE.fullmatch(value):
            return None
        is_utc = value.endswith("Z")
        parsed = datetime.strptime(value[:-1] if is_utc else value, "%Y%m%dT%H%M%S")
        if is_utc:
            return parsed.replace(tzinfo=UTC).astimezone(ROME_TZ)

        tzid = params.get("TZID")
        if tzid:
            try:
                timezone = ZoneInfo(tzid)
            except (ZoneInfoNotFoundError, ValueError):
                return None
        else:
            timezone = ROME_TZ
        return parsed.replace(tzinfo=timezone).astimezone(ROME_TZ)
    except (ValueError, AttributeError):
        return None


def _unescape_ics_text(value: str) -> str:
    """Decodifica gli escape RFC5545 più comuni per il valore TEXT."""
    replacements = {
        "n": "\n",
        "N": "\n",
        ",": ",",
        ";": ";",
        "\\": "\\",
    }
    return _SUMMARY_ESCAPE_RE.sub(lambda match: replacements[match.group(1)], value)


def clean_summary(raw_summary: str) -> str:
    """Rimuove il prefisso '<Comune>:' e normalizza spazi/virgole."""
    text = raw_summary.replace("\r", "").strip()
    if ": " in text:
        text = text.split(": ", 1)[1]
    elif ":" in text:
        text = text.split(":", 1)[1]
    parts = [p.strip() for p in text.split(",")]
    parts = [p for p in parts if p]
    return ", ".join(parts)


def detect_types(summary_clean: str) -> tuple[str, ...]:
    """Riconosce i tipi rifiuto dentro una summary pulita, in ordine di apparizione."""
    lowered = summary_clean.lower()
    hits: list[tuple[int, str]] = []
    for key in _CANONICAL_ORDER:
        label = _CANONICAL_LABELS[key].lower()
        match = re.search(rf"(?<![a-z]){re.escape(label)}(?![a-z])", lowered)
        if match:
            hits.append((match.start(), key))
    hits.sort()
    return tuple(key for _, key in hits)


def _parse_ics_events(
    content: str, zona: int
) -> tuple[list[WasteEvent], bool]:
    """Parsa eventi e segnala campi data invalidi negli eventi riconosciuti."""
    blocks, _ = _extract_event_blocks(content)
    events: list[WasteEvent] = []
    malformed_recognized_event = False
    for block in blocks:
        properties: dict[str, tuple[dict[str, str], str]] = {}
        for line in block.splitlines():
            parsed = _parse_property(line)
            if parsed is None:
                continue
            name, params, value = parsed
            if name in {"DTSTART", "DTEND", "SUMMARY"} and name not in properties:
                properties[name] = (params, value)

        summary_property = properties.get("SUMMARY")
        raw_summary = (
            _unescape_ics_text(summary_property[1]).strip()
            if summary_property is not None
            else ""
        )
        summary = clean_summary(raw_summary)
        if not summary:
            continue
        types = detect_types(summary)
        if not types:
            _LOGGER.debug("SUMMARY non riconosciuta, scartata: %r", raw_summary[:80])
            continue

        start_property = properties.get("DTSTART")
        if start_property is None:
            malformed_recognized_event = True
            continue
        start = _parse_dt(start_property[1], start_property[0])
        if start is None:
            malformed_recognized_event = True
            continue

        end_property = properties.get("DTEND")
        if end_property is not None:
            start_is_date = (
                start_property[0].get("VALUE", "").upper() == _DATE_ONLY
                or bool(_DATE_RE.fullmatch(start_property[1].strip()))
            )
            end_is_date = (
                end_property[0].get("VALUE", "").upper() == _DATE_ONLY
                or bool(_DATE_RE.fullmatch(end_property[1].strip()))
            )
            if start_is_date != end_is_date:
                malformed_recognized_event = True
                continue
            end = _parse_dt(end_property[1], end_property[0])
            if end is None or end.astimezone(UTC) <= start.astimezone(UTC):
                malformed_recognized_event = True
                continue
        elif (
            start_property[0].get("VALUE", "").upper() == "DATE"
            or _DATE_RE.fullmatch(start_property[1].strip())
        ):
            # DTSTART di tipo DATE rappresenta una raccolta per l'intera giornata.
            end = start + timedelta(days=1)
        else:
            end = start + timedelta(hours=1)

        canonical = ", ".join(_CANONICAL_LABELS[key] for key in types)
        uid = f"{zona}-{start.isoformat()}-{canonical}"
        events.append(
            WasteEvent(start=start, end=end, summary=canonical, types=types, uid=uid)
        )

    seen: set[str] = set()
    unique: list[WasteEvent] = []
    for event in sorted(events, key=lambda item: item.start.astimezone(UTC)):
        if event.uid not in seen:
            seen.add(event.uid)
            unique.append(event)
    return unique, malformed_recognized_event


def parse_ics(content: str, zona: int) -> list[WasteEvent]:
    """Parsa il contenuto ICS Contarina in eventi ordinati e deduplicati."""
    events, _ = _parse_ics_events(content, zona)
    return events


def parse_ics_candidate(content: str, zona: int) -> list[WasteEvent] | None:
    """Parsa una risposta ICS usabile, oppure restituisce ``None`` se è corrotta.

    Un calendario strutturalmente valido senza VEVENT è un risultato vuoto
    legittimo. Se invece dichiara eventi ma nessuno è interpretabile, il
    contenuto non deve sostituire l'ultima cache funzionante.
    """
    blocks, valid_structure = _extract_event_blocks(content)
    if not valid_structure:
        return None
    events, malformed_recognized_event = _parse_ics_events(content, zona)
    if malformed_recognized_event or (blocks and not events):
        return None
    return events


def filter_events(events: list[WasteEvent], options: dict) -> list[WasteEvent]:
    """Applica i filtri utente: rimuove tipi disabilitati, scarta eventi vuoti."""
    enabled = {key: bool(options.get(key, True)) for key in _CANONICAL_ORDER}
    if all(enabled.values()):
        return list(events)
    filtered: list[WasteEvent] = []
    for event in events:
        kept = tuple(kind for kind in event.types if enabled.get(kind, True))
        if not kept:
            continue
        summary = ", ".join(_CANONICAL_LABELS[kind] for kind in kept)
        filtered.append(
            WasteEvent(
                start=event.start,
                end=event.end,
                summary=summary,
                types=kept,
                uid=event.uid,
            )
        )
    return filtered
