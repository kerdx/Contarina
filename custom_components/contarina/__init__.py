"""Setup integrazione Contarina."""

from __future__ import annotations

from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import DOMAIN
from .coordinator import ContarinaCoordinator

PLATFORMS = ["calendar", "sensor", "binary_sensor", "button", "switch"]

# Icone bidoni servite dall'integrazione: niente da copiare in www/.
# URL: /contarina/contarina-secco.svg (ecc.)
STATIC_URL = "/contarina"


def _register_static(hass: HomeAssistant) -> None:
    """Espone le icone su /contarina. Mai bloccante: se fallisce, si logga e basta."""
    import logging

    _LOGGER = logging.getLogger(__name__)
    if hass.data.get(f"{DOMAIN}_static"):
        return
    if hass.http is None:
        return
    www = Path(__file__).parent / "www"
    if not www.is_dir():
        _LOGGER.debug("[%s] cartella icone assente, salto static path", DOMAIN)
        return
    try:
        register_many = getattr(hass.http, "async_register_static_paths", None)
        if register_many is not None:
            from homeassistant.components.http import StaticPathConfig

            register_many([StaticPathConfig(STATIC_URL, str(www), True)])
        else:  # HA vecchi
            hass.http.register_static_path(STATIC_URL, str(www))
    except (RuntimeError, AttributeError) as err:
        _LOGGER.warning("[%s] static path non registrato (%s), icone non servite", DOMAIN, err)
        return
    hass.data[f"{DOMAIN}_static"] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _register_static(hass)
    coordinator = ContarinaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

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


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Pulizia alla rimozione (nessun file su disco nella v2, solo memoria)."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
