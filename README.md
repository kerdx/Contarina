# Calendario Contarina v2.5

[![Validate](https://github.com/kerdx/Contarina/actions/workflows/validate.yml/badge.svg)](https://github.com/kerdx/Contarina/actions/workflows/validate.yml)
[![HACS](https://img.shields.io/badge/HACS-integration-blue)](https://hacs.xyz)
[![HA](https://img.shields.io/badge/Home%20Assistant-2026.9%2B-41BDF5)](https://www.home-assistant.io)

Integrazione Home Assistant per il calendario raccolta rifiuti Contarina (Treviso).

Riscrittura della [versione originale di gianlucaf81](https://github.com/gianlucaf81/calendario_contarina): niente più file `.ics` in `www/`, niente più `ical-sensor` esterno.

## Cosa cambia rispetto alla v1

| v1 | v2 |
|---|---|
| Scarica `.ics` in `www/` con `urllib` + regex | `DataUpdateCoordinator` con `aiohttp` + `asyncio.timeout`, parsing RFC5545, timezone `Europe/Rome`, cache offline in `.storage/` |
| Aggiornamento solo manuale | Auto-refresh 12h + refresh 00:05 + pulsante |
| Richiede `ical-sensor` + `/local/*.ics` | `calendar` nativa + sensori + binary sensor |
| Nessun sensore | 7 sensori + 2 binary sensor |
| Filtri con riscrittura file | Filtri in-memory (switch + opzioni) |
| Manca `unload`, servizio per-entry | `unload` corretto, multi-comune, `unique_id` per zona |
| Nessuna traduzione/test | `it/en`, `icon.json`, test pytest, hassfest + hacs validation |

## Installazione

[![Apri in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kerdx&repository=Contarina&category=integration)

1. HACS → repo custom → **Calendario Contarina** (oppure copia `custom_components/contarina` in `config/custom_components/`).
2. Riavvia HA.
3. Impostazioni → Dispositivi e servizi → Aggiungi → **Calendario Contarina** → scegli zona.

Icone bidoni servite dall'integrazione su `/contarina/contarina-<tipo>.svg`: niente da copiare. Solo le Tile con `icon: local:contarina-*` richiedono una copia una tantum in `config/www/custom_icons/` (vedi `custom_icons/README.md`), altrimenti usa le MDI indicate lì.

## Entità (per zona)

- `calendar.<zona>_calendario_rifiuti` — calendario nativo.
- `sensor.<zona>_prossima_raccolta` (date) + attributi `tipi, tipi_lista, giorni_mancanti, prossimi[5]`.
- `sensor.<zona>_raccolta_rifiuti` (label card: `Domani · VPL, Umido`) + `tipi_lista, giorni_mancanti, data`.
- `sensor.<zona>_prossimo_secco/_prossimo_umido/_prossima_carta/_prossimo_vpl/_prossimo_vegetale` (date per frazione, nota il femminile di carta).
- `binary_sensor.<zona>_esporre_stasera` — `on` se domani c'è raccolta (per badge e automazioni).
- `binary_sensor.<zona>_raccolta_oggi` — `on` se raccolta oggi.
- `button.<zona>_aggiorna_calendario`, `switch.<zona>_filtro_*` (5).

## Card Bubble (titolo + foto, auto a mezzanotte)

Vedi `dashboard-example-bubble.yaml`: bottone Bubble con `sensor.xxx_raccolta_rifiuti` + Markdown foto da `tipi_lista`. `dashboard-example-popup.yaml`: tap → popup con calendario mese + prossimi 5 + filtri.

## Dashboard unificata (consigliata)

`dashboard-rifiuti.yaml`: 1 vista Sections pronta — badge condizionali (stasera/oggi), chip Mushroom, Tile per frazione con `giorni_mancanti`, lista auto-entities senza Jinja manuale, calendario mese, filtri. Trova e sostituisci `ZONA` con lo slug del device. Richiede HACS: `mushroom`, `auto-entities`, `template-entity-row`. Le varianti Bubble restano negli altri 2 file. I pezzi separati sono anche in `dashboard-example-tiles.yaml` (solo Tile+chip+badge) e `dashboard-example-list.yaml` (solo lista).

## Gestione entry

- Cambiare zona senza ricreare: Impostazioni → Integrazione → … → Riconfigura.
- Filtri: Configura (sezioni Frazioni principali / Altre frazioni) oppure gli switch.
- Problemi rete: se Contarina non risponde compare un repair Impostazioni → Riparazioni e i dati restano da cache. Diagnostica scaricabile da … → Scarica diagnostica.

## Blueprint avviso sera prima

`blueprints/automation/contarina/avviso_serale.yaml`: alle 20:00 se `esporre_stasera=on` → notify con tipi + foto primo bidone.

[![Importa blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fkerdx%2FContarina%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcontarina%2Favviso_serale.yaml)

```yaml
automation:
  - alias: "Avvisa raccolta domani"
    trigger:
      - platform: state
        entity_id: binary_sensor.giavera_del_montello_esporre_stasera
        to: "on"
    action:
      - service: notify.mobile_app_telefono
        data:
          message: "{{ states('sensor.giavera_del_montello_raccolta_rifiuti') }}"
```

## Note tecniche

- Sorgente: `https://contarina.it/api/?query=genera_ics_calendari&zona={zona}&time=0700`
- Refresh 12h + 00:05, timeout 30s, fallback cache `.storage/contarina_zona_<id>.ics`.
- `DTSTART:YYYYMMDDTHHMMSS` → `Europe/Rome`. Zero dipendenze extra.

## Risoluzione problemi

- Dopo un aggiornamento HACS riavvia sempre HA, altrimenti resta caricata la versione vecchia (controlla `"version"` in `custom_components/contarina/manifest.json`).
- Entità `unknown` dopo il setup: quasi sempre rete/DNS verso `contarina.it`. Controlla il registro con `custom_components.contarina: debug` nel logger.
- Vedi ancora la 2.5.1 in HACS: … → Riscarica, poi riavvia.
