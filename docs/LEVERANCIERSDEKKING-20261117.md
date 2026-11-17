# Leveranciersdekking NUVEMIXA — onderzoek en verbeterplan (17-11-2026)

Geen betaalde AI, geen abonnement, geen wijziging aan WooCommerce of Render. Alleen branch `fix/productzoeken-algemeen-20261117`.

## Wat NUVEMIXA nu echt doorzoekt (code, niet live bevestigd)
23 merkwebshops (Shopify/WooCommerce-zoekfunctie), Hama (NL/DE), Hurtel, en de openbare productlijst van Syncee. **Geen enkele bron is vanuit mijn testomgeving live bevestigd**: de omgeving heeft geen toegang tot leveranciersites. Gebruik daarom de knop *Bronnen testen* (Productonderzoek → Bronnen en dekking) op Render.

## Bronnen om verder te onderzoeken (alleen link, geen koppeling)
| Bron | Type | Toegang | Kosten / voorwaarde | Status |
|---|---|---|---|---|
| BigBuy | Dropshipping EU | Officiële API (sleutel, Ecommerce-contract) | pack-prijs niet gevonden | onderzocht |
| CJdropshipping | Dropshipping INT | Officiële API (key, token 180 dgn) | kosten niet in docs | onderzocht |
| dropXL (vidaXL) | Dropshipping EU, wonen | Account + API-token | maandelijkse kosten (bedrag niet gevonden) | onderzocht |
| Hertwill | Dropshipping EU, beauty/wonen | Account (gratis plan) + API | betaalde plannen | onderzocht |
| Ikonka | Groothandel PL | Alleen via Shoper/Apilo-integratie | Shoper betaald | onderzocht |
| Syncee | Marktplaats | Gratis kijken; import betaald | vanaf $39,99/mnd | onderzocht |
| Versa, Sirocco, JG Distribution, Avasam | Groothandel/platform | Handmatig | onbekend | **niet onderzocht** (pagina's niet bereikbaar) |

Bewijslinks staan per bron in de interface en in `nv_supplier_sources.py`.

## Gebouwd
- `nv_supplier_sources.py`: register met type, toegangsklasse, kosten, bewijs en status; suggesties afhankelijk van categorie en doelland; Google `site:`-link per bron.
- Leveranciers-tab toont nu altijd "Verder zoeken" (handmatige links, expliciet niet bevestigd).
- Paneel *Bronnen en dekking* per categorie, plus handmatige, alleen-lezen bronnentest (POST, CSRF, alleen ingelogd; pagina opent zonder aanroepen).
- USB/powerbank-voorkeur weggehaald: standaardzoekwoord gadgets is nu "headphones"; Hama voegt het vaste Qi2-model alleen toe bij een passende zoekterm. Expliciete powerbank-zoekopdrachten blijven werken.
- Tests: 439 geslaagd, 42 overgeslagen, 0 mislukt. Screenshots: `docs/zoek-bewijs/dekking-*.png` (testdata-banner).

## Nodig voor echte dekking (later, na jouw akkoord)
BigBuy-API-contract, CJ API-key, dropXL-account, Hertwill-account (gratis plan), eventueel Syncee-betaald plan. Per bron is dan een aparte koppeling nodig.
