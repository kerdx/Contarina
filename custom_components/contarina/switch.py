"""Switch platform: filtri per tipo rifiuto (scrivono in entry.options)."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WASTE_ICONS, WASTE_LABELS, WASTE_TYPES
from .coordinator import ContarinaCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ContarinaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ContarinaFilterSwitch(coordinator, entry, key) for key in WASTE_TYPES
    )


class ContarinaFilterSwitch(CoordinatorEntity[ContarinaCoordinator], SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: ContarinaCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_filter_{key}"
        self._attr_translation_key = f"filter_{key}"
        self._attr_icon = WASTE_ICONS.get(key)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.zona_name,
            "manufacturer": "Contarina",
            "model": f"Zona {coordinator.zona}",
        }

    @property
    def is_on(self) -> bool:
        return bool(self._entry.options.get(self._key, True))

    async def async_turn_on(self, **kwargs) -> None:
        await self._async_set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._async_set(False)

    async def _async_set(self, value: bool) -> None:
        new_options = dict(self._entry.options)
        new_options[self._key] = value
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        # Il reload (update listener in __init__.py) ricrea il coordinator;
        # aggiorniamo comunque i listener per un feedback immediato.
        self.coordinator.async_update_listeners()
