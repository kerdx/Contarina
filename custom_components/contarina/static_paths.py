"""Registrazione delle risorse statiche dell'integrazione."""

from __future__ import annotations

import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)


async def async_register_static(hass, domain: str, url: str, www: Path) -> None:
    """Registra le icone una volta; un problema HTTP non deve bloccare il setup."""
    key = f"{domain}_static"
    if hass.data.get(key) or hass.http is None:
        return
    if not www.is_dir():
        _LOGGER.debug("[%s] cartella icone assente, salto static path", domain)
        return
    try:
        register_many = getattr(hass.http, "async_register_static_paths", None)
        if register_many is not None:
            from homeassistant.components.http import StaticPathConfig

            await register_many([StaticPathConfig(url, str(www), True)])
        else:  # Compatibilità con versioni HA precedenti all'API async.
            hass.http.register_static_path(url, str(www))
    except Exception as err:  # noqa: BLE001 - registrazione opzionale, mai bloccante
        _LOGGER.warning(
            "[%s] static path non registrato (%s), icone non servite", domain, err
        )
        return
    hass.data[key] = True
