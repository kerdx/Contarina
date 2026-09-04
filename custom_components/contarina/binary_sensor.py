"""Binary sensor Contarina: da esporre stasera / oggi."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ContarinaCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ContarinaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ContarinaExposeTonight(coordinator, entry),
            ContarinaExposeToday(coordinator, entry),
        ]
    )


class _Base(CoordinatorEntity[ContarinaCoordinator], BinarySensorEntity):
    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.zona_name,
            "manufacturer": "Contarina",
            "model": f"Zona {coordinator.zona}",
        }

    def _first(self):
        events = self.coordinator.events
        if not events:
            return None, -1
        tz = events[0].start.tzinfo
        today = datetime.now(tz=tz).date()
        for ev in events:
            giorni = (ev.start.date() - today).days
            if giorni >= 0:
                return ev, giorni
        return None, -1


class ContarinaExposeTonight(_Base):
    """ON se domani c'è una raccolta → stasera bisogna esporre i bidoni."""

    _attr_has_entity_name = True
    _attr_translation_key = "expose_tonight"
    _attr_icon = "mdi:delete-alert-outline"

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_expose_tonight"

    @property
    def is_on(self) -> bool | None:
        _, giorni = self._first()
        if giorni < 0:
            return None
        return giorni == 1

    @property
    def extra_state_attributes(self) -> dict:
        first, giorni = self._first()
        if first is None:
            return {}
        return {
            "tipi": first.summary,
            "tipi_lista": list(first.types),
            "data": first.start.date().isoformat(),
            "giorni_mancanti": giorni,
            "zona": self.coordinator.zona_name,
        }


class ContarinaExposeToday(_Base):
    """ON se oggi c'è una raccolta (bidoni già fuori / da ritirare)."""

    _attr_has_entity_name = True
    _attr_translation_key = "expose_today"
    _attr_icon = "mdi:trash-can-outline"

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_expose_today"

    @property
    def is_on(self) -> bool | None:
        _, giorni = self._first()
        if giorni < 0:
            return None
        return giorni == 0

    @property
    def extra_state_attributes(self) -> dict:
        first, giorni = self._first()
        if first is None:
            return {}
        return {
            "tipi": first.summary,
            "tipi_lista": list(first.types),
            "data": first.start.date().isoformat(),
            "giorni_mancanti": giorni,
            "zona": self.coordinator.zona_name,
        }
