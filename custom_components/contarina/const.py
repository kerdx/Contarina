"""Costanti per l'integrazione Contarina."""

DOMAIN = "contarina"

CONF_SECCO = "secco"
CONF_UMIDO = "umido"
CONF_CARTA = "carta"
CONF_VPL = "vpl"
CONF_VEGETALE = "vegetale"

API_URL_TEMPLATE = "https://contarina.it/api/?query=genera_ics_calendari&zona={zona}&time=0700"

# Ogni quanto ricaricare dal sito Contarina (il calendario cambia 1-2 volte/anno,
# ma un refresh giornaliero tiene anche l'orologio dei sensori allineato).
UPDATE_INTERVAL_HOURS = 12

# Timeout HTTP
REQUEST_TIMEOUT = 30

# Tipi rifiuto gestiti, label canoniche come appaiono nel SUMMARY Contarina
WASTE_TYPES: list[str] = [CONF_SECCO, CONF_UMIDO, CONF_CARTA, CONF_VPL, CONF_VEGETALE]

WASTE_LABELS: dict[str, str] = {
    CONF_SECCO: "Secco",
    CONF_UMIDO: "Umido",
    CONF_CARTA: "Carta",
    CONF_VPL: "VPL",
    CONF_VEGETALE: "Vegetale",
}

WASTE_ICONS: dict[str, str] = {
    CONF_SECCO: "mdi:trash-can",
    CONF_UMIDO: "mdi:food-apple",
    CONF_CARTA: "mdi:newspaper",
    CONF_VPL: "mdi:bottle-soda",
    CONF_VEGETALE: "mdi:leaf",
}

# Mappatura Zone -> Nomi Comuni (da sito Contarina)
ZONE_MAP: dict[int, str] = {
    1: "Treviso Cintura Urbana",
    2: "Treviso Fuori Mura",
    3: "Treviso Centro Storico",
    4: "Arcade",
    5: "Breda di Piave",
    6: "Carbonera",
    7: "Casale sul Sile",
    8: "Casier",
    9: "Giavera del Montello",
    10: "Maserada sul Piave",
    11: "Monastier di Treviso",
    12: "Morgano",
    13: "Nervesa della Battaglia",
    14: "Paese",
    15: "Ponzano Veneto",
    16: "Povegliano",
    17: "Preganziol",
    18: "Quinto di Treviso",
    19: "Roncade",
    20: "San Biagio di Callalta",
    21: "Silea",
    22: "Spresiano",
    23: "Susegana",
    24: "Villorba",
    25: "Volpago del Montello",
    26: "Zenson di Piave",
    27: "Zero Branco",
    28: "Altivole",
    29: "Asolo Centro Storico",
    30: "Asolo Fuori Centro Storico",
    31: "Borso del Grappa",
    32: "Caerano di San Marco",
    33: "Castelcucco",
    34: "Castelfranco Veneto Centro Storico",
    35: "Castelfranco Veneto Fuori Centro Storico",
    36: "Castello di Godego",
    37: "Cavaso del Tomba",
    38: "Cornuda",
    40: "Crocetta del Montello",
    41: "Fonte",
    42: "Istrana",
    43: "Loria",
    44: "Maser",
    45: "Monfumo",
    46: "Montebelluna Centro Storico",
    47: "Montebelluna Fuori Centro Storico",
    49: "Pederobba",
    50: "Possagno",
    51: "Resana",
    52: "Riese Pio X",
    53: "San Zenone degli Ezzelini",
    54: "Trevignano",
    55: "Vedelago",
    56: "Pieve del Grappa",
}


def default_options() -> dict[str, bool]:
    """Opzioni di default: tutti i filtri attivi."""
    return {
        CONF_SECCO: True,
        CONF_UMIDO: True,
        CONF_CARTA: True,
        CONF_VPL: True,
        CONF_VEGETALE: True,
    }


def enabled_types(options: dict) -> dict[str, bool]:
    """Restituisce il dict tipo->bool con fallback True."""
    base = default_options()
    base.update({k: bool(options.get(k, True)) for k in WASTE_TYPES})
    return base
