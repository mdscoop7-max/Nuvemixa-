# Veilige preview van het vernieuwde dashboard

De afbeeldingen in `docs/preview/` zijn lokaal gemaakt met **testdata**: geen echte klantgegevens, geen productiegeheimen, geen echte API-sleutels, niets verbonden met Render, WooCommerce of Neon.

| Scherm | Desktop | Mobiel |
|---|---|---|
| Hoofdscherm | `desktop-dashboard.png` | `mobiel-dashboard.png` |
| Productpublicatie (testdata) | `desktop-publicatie.png` | `mobiel-publicatie.png` |
| Administratie (testdata) | `desktop-administratie.png` | `mobiel-administratie.png` |
| Menu | | `menu-mobiel.png` |

## Zelf lokaal bekijken (zonder productiegegevens)

Draai de tests (`python -m pytest`) of start de app lokaal met een eigen testbeheerder. Gebruik daarvoor geen productiegeheimen: stel `SECRET_KEY`, `NUVEMIXA_ADMIN_EMAIL` en `NUVEMIXA_ADMIN_PASSWORD_HASH` in met eigen testwaarden, zonder WooCommerce-, Mollie- of OpenAI-variabelen. Zonder die variabelen toont het dashboard overal "niet gekoppeld" of testdata.

Er is bewust **geen** gehoste preview aangemaakt: die zou een Render-omgeving of productiegeheimen vereisen.
