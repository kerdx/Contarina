"""Parsing ICS Contarina — funzioni pure, senza dipendenze Home Assistant.

Separato dal coordinator per permettere test pytest senza HA.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_LOGGER = logging.getLogger(__name__)

ROME_TZ = ZoneInfo("Europe/Rome")

_DT_RE = re.compile(r"DTSTART:(\d{8}T\d{6})")
_DT_END_RE = re.compile(r"DTEND:(\d{8}T\d{6})")
_SUMMARY_RE = re.compile(r"SUMMARY:(.*)")

# Queste label devono restare sincronizzate con const.WASTE_LABELS,
# ma le duplichiamo qui per non importare HA. Mappa key -> label.
_CANONICAL_LABELS: dict[str, str] = {
    "secco": "Secco",
    "umido": "Umido",
    "carta": "Carta",
    "vpl": "VPL",
    "vegetale": "Vegetale",
}
_CANONICAL_ORDER: tuple[str, ...] = ("secco", "umido", "carta", "vpl", "vegetale")


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


def _parse_dt(value: str) -> datetime | None:
    """Parsa DTSTART/DTEND tipo 20260929T060000 come Europe/Rome."""
    try:
        naive = datetime.strptime(value.strip(), "%Y%m%dT%H%M%S")
        return naive.replace(tzinfo=ROME_TZ)
    except (ValueError, AttributeError):
        return None


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
        m = re.search(rf"(?<![a-z]){re.escape(label)}(?![a-z])", lowered)
        if m:
            hits.append((m.start(), key))
    hits.sort()
    return tuple(k for _, k in hits)


def parse_ics(content: str, zona: int) -> list[WasteEvent]:
    """Parsa il contenuto ICS Contarina in eventi ordinati e deduplicati."""
    unfolded = _unfold_ics(content)
    blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, re.DOTALL)
    events: list[WasteEvent] = []
    for block in blocks:
        m_start = _DT_RE.search(block)
        if not m_start:
            continue
        start = _parse_dt(m_start.group(1))
        if start is None:
            continue
        m_end = _DT_END_RE.search(block)
        end = _parse_dt(m_end.group(1)) if m_end else None
        if end is None:
            end = start + timedelta(hours=1)

        m_sum = _SUMMARY_RE.search(block)
        raw_sum = m_sum.group(1).strip() if m_sum else ""
        summary = clean_summary(raw_sum)
        if not summary:
            continue
        types = detect_types(summary)
        if not types:
            _LOGGER.debug("SUMMARY non riconosciuta, scartata: %r", raw_sum[:80])
            continue
        canonical = ", ".join(_CANONICAL_LABELS[t] for t in types)
        uid = f"{zona}-{start.isoformat()}-{canonical}"
        events.append(WasteEvent(start=start, end=end, summary=canonical, types=types, uid=uid))

    seen: set[str] = set()
    unique: list[WasteEvent] = []
    for ev in sorted(events, key=lambda e: e.start):
        if ev.uid not in seen:
            seen.add(ev.uid)
            unique.append(ev)
    return unique


def filter_events(events: list[WasteEvent], options: dict) -> list[WasteEvent]:
    """Applica i filtri utente: rimuove tipi disabilitati, scarta eventi vuoti."""
    enabled = {k: bool(options.get(k, True)) for k in _CANONICAL_ORDER}
    if all(enabled.values()):
        return list(events)
    filtered: list[WasteEvent] = []
    for ev in events:
        kept = tuple(t for t in ev.types if enabled.get(t, True))
        if not kept:
            continue
        summary = ", ".join(_CANONICAL_LABELS[t] for t in kept)
        filtered.append(
            WasteEvent(start=ev.start, end=ev.end, summary=summary, types=kept, uid=ev.uid)
        )
    return filtered
