"""Sorgente pura delle chiavi e delle label canoniche dei rifiuti."""

CONF_SECCO = "secco"
CONF_UMIDO = "umido"
CONF_CARTA = "carta"
CONF_VPL = "vpl"
CONF_VEGETALE = "vegetale"

WASTE_LABELS: dict[str, str] = {
    CONF_SECCO: "Secco",
    CONF_UMIDO: "Umido",
    CONF_CARTA: "Carta",
    CONF_VPL: "VPL",
    CONF_VEGETALE: "Vegetale",
}
WASTE_TYPES: tuple[str, ...] = tuple(WASTE_LABELS)
