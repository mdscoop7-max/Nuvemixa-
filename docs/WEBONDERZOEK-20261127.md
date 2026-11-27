# Onderzoeksfuncties dashboard: analyse en oplossing (27-11-2026)

## Gemeten oorzaken
| Probleem | Oorzaak (bewijs) | Laag |
|---|---|---|
| Vaak 0 resultaten | Productonderzoek vraagt alleen ~25 vaste merkwebshops (UGREEN, Baseus, Nedis, Cocunat, Ferm Living, Manduka …) en Syncee. Lokale meting tegen de echte bronnen: "slimme stekker" (dropship) 0 leveranciers, "opbergbox" 1 (Ferm Living), "yogamat" 1 (Manduka). | Bronintegratie |
| Steeds dezelfde leveranciers | Dezelfde vaste lijst per categorie: gadgets geven steeds Hama/Nedis/UGREEN/Baseus/Xtorm, Home & Living altijd Ferm Living. De AI-leverancierszoeker mocht alleen 9 vaste B2B-gidsen citeren, max. 3 (dropXL, BigBuy …). | Bronintegratie / AI-opzet |
| AI werkt onvoldoende | Render-log 25-11 22:54: `HTTP 400 param=tools … Parameter 'filters' not supported with model 'gpt-4.1-mini'`. Elke AI-leverancierszoekopdracht begon met een geweigerd verzoek; daarna mocht AI alleen de 9 vaste domeinen gebruiken. Bij productonderzoek deed AI alleen zoekwoorden uitbreiden en filteren, niet zoeken. | AI-verwerking |
| Internationaal zwak | Zoektermen niet in de taal van het doelland; bronnen per land vast. | Backend |
| Partners vast register | `nv_partners.PARTNERS` is een handmatige lijst (17-11-2026) plus Google-links. | Backend |
| Trage pagina | Onderzoekspagina met alle platforms ~28 s (log 26-11 18:02:34 → 18:03:02), vlak onder de gunicorn-time-out van 30 s. | Backend |

## Oplossing
`nv_web_discovery.py` + `nv_web_discovery_view.py` + `_dashboard_web_discovery.html` + `static/nv-web-discovery.js`:
1. AI (Responses API, web_search, gpt-4.1-mini, max. 3 zoekacties) zoekt **open** op het web, in het Engels en de taal van het gekozen land, binnen een van de vijf webshopcategorieën (Gadgets, Smart Home, Beauty & Care, Home & Living, Lifestyle & Sport). Geen domeinfilter meer (oorzaak van de HTTP 400).
2. De server opent elke voorgestelde pagina zelf. **Gecontroleerd** = pagina bereikbaar, product of categorie staat erop, en een zakelijk signaal (groothandel, dropshipping, fabrikant, partnerprogramma; meertalig) staat er letterlijk. Het bewijs is een citaat van die pagina. Al het andere staat apart als aanwijzing of wordt met reden weggelaten.
3. Eén resultaat per bedrijf (registreerbaar domein); "Meer andere bedrijven zoeken" sluit getoonde domeinen uit.
4. Consumentenwinkels, zoekmachines en social media vallen weg; interne adressen worden nooit opgevraagd (SSRF-bescherming).
5. Loopt asynchroon (JSON), zodat de dashboardpagina zelf niet trager wordt. Cache 12 uur; daglimiet 25 (`NUVEMIXA_WEB_RESEARCH_DAILY_LIMIT`); kosten via het bestaande centrale AI-maandbudget in `nv_openai` (niet verhoogd). Valt onder de AI-bevriezing in `nv_freeze`.
6. Opgenomen in Productonderzoek & niches, Leveranciers (vervangt de oude AI-zoekbalk), Partners en Internationaal.

De oude AI-route `/dashboard/leveranciers/ai-zoeken` blijft bestaan, maar slaat bij gpt-4.1-* de geweigerde filtervariant over.

## Beperkingen
* Prijzen, levertijden en voorwaarden blijven "Niet bevestigd": die staan zelden openbaar en worden niet verzonnen.
* Sommige sites blokkeren automatische controle (bijv. HTTP 403); die verschijnen alleen als de AI-zoekmachine ze citeerde, en nooit als gecontroleerd.
* Land is een aanwijzing (afgeleid uit het domein of opgave AI), geen gecontroleerd vestigingsadres.
* Kosten per live zoekopdracht ca. US$ 0,05–0,10; met het interne maandbudget van US$ 3 zijn dat grofweg 30–60 nieuwe zoekopdrachten per maand (herhalingen uit cache zijn gratis).
