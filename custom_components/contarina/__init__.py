"""Setup integrazione Contarina."""

from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .coordinator import ContarinaCoordinator
from .static_paths import async_register_static

PLATFORMS = ["calendar", "sensor", "binary_sensor", "button", "switch"]

# Icone bidoni servite dall'integrazione: niente da copiare in www/.
# URL: /contarina/contarina-secco.svg (ecc.)
STATIC_URL = "/contarina"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await async_register_static(hass, DOMAIN, STATIC_URL, Path(__file__).parent / "www")
    coordinator = ContarinaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    # Refresh garantito dopo mezzanotte: ricalcola "oggi/domani" e riallinea
    # anche se l'intervallo 12h non cade esattamente a cavallo della mezzanotte.
    async def _midnight_refresh(now=None):
        await coordinator.async_request_refresh()

    entry.async_on_unload(
        async_track_time_change(hass, _midnight_refresh, hour=0, minute=5, second=0)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ricalcola le entità con le nuove opzioni senza ricreare il coordinator."""
    coordinator: ContarinaCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator is not None:
        coordinator.async_update_listeners()


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Pulizia alla rimozione (nessun file su disco nella v2, solo memoria)."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
