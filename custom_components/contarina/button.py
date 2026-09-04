"""Button platform: aggiornamento manuale (trigger coordinator)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([ContarinaRefreshButton(coordinator, entry)])


class ContarinaRefreshButton(CoordinatorEntity[ContarinaCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "refresh"

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.zona_name,
            "manufacturer": "Contarina",
            "model": f"Zona {coordinator.zona}",
        }

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
