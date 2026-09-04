"""Sensor platform Contarina.

- sensor.<zona>_prossima_raccolta: prossima data di raccolta (device_class=date)
- sensor.<zona>_<tipo>_prossimo: prossima data per ogni frazione
"""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WASTE_ICONS, WASTE_LABELS, WASTE_TYPES
from .coordinator import ContarinaCoordinator, WasteEvent


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ContarinaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        ContarinaNextSensor(coordinator, entry),
        ContarinaLabelSensor(coordinator, entry),
    ]
    entities.extend(ContarinaWasteSensor(coordinator, entry, key) for key in WASTE_TYPES)
    async_add_entities(entities)


def _today(tz) -> date:
    return datetime.now(tz=tz).date()


def _next_events(events: list[WasteEvent], today: date, limit: int = 5) -> list[WasteEvent]:
    return [e for e in events if e.start.date() >= today][:limit]


class _Base(CoordinatorEntity[ContarinaCoordinator], SensorEntity):
    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.zona_name,
            "manufacturer": "Contarina",
            "model": f"Zona {coordinator.zona}",
        }


class ContarinaNextSensor(_Base):
    """Prossima raccolta (qualsiasi tipo attivo)."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_collection"
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next"

    @property
    def native_value(self) -> date | None:
        events = self.coordinator.events
        if not events:
            return None
        tz = events[0].start.tzinfo
        today = _today(tz)
        nxt = _next_events(events, today, 1)
        return nxt[0].start.date() if nxt else None

    @property
    def extra_state_attributes(self) -> dict:
        events = self.coordinator.events
        if not events:
            return {}
        tz = events[0].start.tzinfo
        today = _today(tz)
        upcoming = _next_events(events, today, 5)
        if not upcoming:
            return {}
        first = upcoming[0]
        giorni = (first.start.date() - today).days
        return {
            "tipi": first.summary,
            "tipi_lista": list(first.types),
            "giorni_mancanti": giorni,
            "giorno_settimana": first.start.strftime("%A"),
            "zona": self.coordinator.zona_name,
            "prossimi": [
                {
                    "data": e.start.date().isoformat(),
                    "tipi": e.summary,
                    "giorni_mancanti": (e.start.date() - today).days,
                }
                for e in upcoming
            ],
        }


class ContarinaWasteSensor(_Base):
    """Prossima data per una singola frazione (secco, umido, ...)."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator, entry)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = f"next_{key}"
        self._attr_icon = WASTE_ICONS.get(key)

    @property
    def _next_for_type(self) -> WasteEvent | None:
        events = self.coordinator.events
        if not events:
            return None
        tz = events[0].start.tzinfo
        today = _today(tz)
        for ev in events:
            if ev.start.date() >= today and self._key in ev.types:
                return ev
        return None

    @property
    def native_value(self) -> date | None:
        nxt = self._next_for_type
        return nxt.start.date() if nxt else None

    @property
    def extra_state_attributes(self) -> dict:
        filt_on = bool(self.coordinator.config_entry.options.get(self._key, True))
        nxt = self._next_for_type
        if not nxt:
            return {"frazione": WASTE_LABELS[self._key], "filtro_attivo": filt_on}
        tz = nxt.start.tzinfo
        today = _today(tz)
        return {
            "frazione": WASTE_LABELS[self._key],
            "filtro_attivo": filt_on,
            "giorni_mancanti": (nxt.start.date() - today).days,
            "giorno_settimana": nxt.start.strftime("%A"),
            "tipi_giorno": nxt.summary,
        }


class ContarinaLabelSensor(_Base):
    """Label pronta per la card: 'Oggi', 'Domani', 'Lunedì 15', ... + tipi.

    Pensata per il titolo Bubble Card: Raccolta rifiuti: <stato>.
    Le foto bidoni si pilotano con l'attributo `tipi_lista`.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "next_label"
    _attr_icon = "mdi:trash-can-outline"

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_label"

    def _first(self) -> tuple[WasteEvent | None, int]:
        events = self.coordinator.events
        if not events:
            return None, -1
        tz = events[0].start.tzinfo
        today = _today(tz)
        upcoming = _next_events(events, today, 1)
        if not upcoming:
            return None, -1
        first = upcoming[0]
        return first, (first.start.date() - today).days

    @property
    def native_value(self) -> str | None:
        first, giorni = self._first()
        if first is None:
            return None
        if giorni == 0:
            quando = "Oggi"
        elif giorni == 1:
            quando = "Domani"
        elif giorni == 2:
            quando = "Dopodomani"
        else:
            # es. "Lunedì 15" — data completa resta negli attributi
            quando = first.start.strftime("%A %d").capitalize()
        return f"{quando} · {first.summary}"

    @property
    def extra_state_attributes(self) -> dict:
        first, giorni = self._first()
        if first is None:
            return {}
        return {
            "quando": "oggi" if giorni == 0 else "domani" if giorni == 1 else "prossimi_giorni",
            "giorni_mancanti": giorni,
            "data": first.start.date().isoformat(),
            "tipi": first.summary,
            "tipi_lista": list(first.types),
            "zona": self.coordinator.zona_name,
        }
