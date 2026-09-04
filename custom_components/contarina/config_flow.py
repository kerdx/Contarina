"""Config flow Contarina: select ricercabile, reconfigure, options a sezioni."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CARTA,
    CONF_SECCO,
    CONF_UMIDO,
    CONF_VEGETALE,
    CONF_VPL,
    DOMAIN,
    ZONE_MAP,
    default_options,
)

_HAS_SECTION = hasattr(data_entry_flow, "section")

# Opzioni ordinate alfabeticamente per nome: con 50+ zone la ricerca conta.
_ZONE_OPTIONS = [
    {"value": str(k), "label": v}
    for k, v in sorted(ZONE_MAP.items(), key=lambda kv: kv[1])
]


def _zona_schema(default: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("zona", default=default): SelectSelector(
                SelectSelectorConfig(
                    options=_ZONE_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _options_schema(current: dict) -> vol.Schema:
    base = vol.Schema(
        {
            vol.Optional(CONF_SECCO, default=current[CONF_SECCO]): bool,
            vol.Optional(CONF_UMIDO, default=current[CONF_UMIDO]): bool,
            vol.Optional(CONF_CARTA, default=current[CONF_CARTA]): bool,
        }
    )
    extra = vol.Schema(
        {
            vol.Optional(CONF_VPL, default=current[CONF_VPL]): bool,
            vol.Optional(CONF_VEGETALE, default=current[CONF_VEGETALE]): bool,
        }
    )
    if _HAS_SECTION:
        return vol.Schema(
            {
                vol.Required("base"): data_entry_flow.section(base, {"collapsed": False}),
                vol.Required("extra"): data_entry_flow.section(
                    extra, {"collapsed": False}
                ),
            }
        )
    # Fallback HA vecchi: singolo form piatto.
    return vol.Schema({**base.schema, **extra.schema})


def _flatten_options(user_input: dict) -> dict:
    if "base" in user_input or "extra" in user_input:
        data: dict = {}
        data.update(user_input.get("base", {}))
        data.update(user_input.get("extra", {}))
        return data
    return dict(user_input)


class ContarinaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flusso di configurazione iniziale + reconfigure zona."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            zona = int(user_input["zona"])
            await self.async_set_unique_id(str(zona))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=ZONE_MAP[zona], data={"zona": zona})

        return self.async_show_form(step_id="user", data_schema=_zona_schema("9"))

    async def async_step_reconfigure(self, user_input=None):
        """Cambia zona senza cancellare e ricreare l'entry."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            zona = int(user_input["zona"])
            await self.async_set_unique_id(str(zona))
            for other in self._async_current_entries():
                if other.entry_id != entry.entry_id and other.unique_id == str(zona):
                    return self.async_abort(reason="already_configured")
            return self.async_update_reload_and_abort(
                entry,
                unique_id=str(zona),
                data_updates={"zona": zona},
                title=ZONE_MAP[zona],
            )

        current = str(entry.data.get("zona", 9))
        return self.async_show_form(
            step_id="reconfigure", data_schema=_zona_schema(current)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ContarinaOptionsFlowHandler()


class ContarinaOptionsFlowHandler(config_entries.OptionsFlow):
    """Pannello Opzioni: filtri per tipo rifiuto, in due sezioni."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=_flatten_options(user_input))

        current = dict(default_options())
        current.update(self.config_entry.options)
        return self.async_show_form(step_id="init", data_schema=_options_schema(current))
