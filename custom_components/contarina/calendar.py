"""Calendar platform Contarina: entità calendario nativa, niente più file ICS in www."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ContarinaCoordinator
from .parser import ROME_TZ


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ContarinaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ContarinaCalendar(coordinator, entry)])


class ContarinaCalendar(CoordinatorEntity[ContarinaCoordinator], CalendarEntity):
    """Calendario rifiuti per una zona."""

    _attr_has_entity_name = True
    _attr_translation_key = "waste_calendar"

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_name = None  # usa il nome del device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.zona_name,
            "manufacturer": "Contarina",
            "model": f"Zona {coordinator.zona}",
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Prossimo evento (usato dal pannello Calendario e dagli assistenti)."""
        events = self.coordinator.events
        if not events:
            return None
        now = datetime.now(tz=ROME_TZ)
        for ev in self.coordinator.events:
            if now is None or ev.end >= now:
                return CalendarEvent(
                    summary=ev.summary,
                    start=ev.start,
                    end=ev.end,
                    uid=ev.uid,
                    description=f"Contarina – {self.coordinator.zona_name}",
                )
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        out: list[CalendarEvent] = []
        for ev in self.coordinator.events:
            if ev.start < end_date and ev.end > start_date:
                out.append(
                    CalendarEvent(
                        summary=ev.summary,
                        start=ev.start,
                        end=ev.end,
                        uid=ev.uid,
                        description=f"Contarina – {self.coordinator.zona_name}",
                    )
                )
        return out
