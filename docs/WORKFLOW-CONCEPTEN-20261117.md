# Workflow zoeken → beoordelen → concept → publicatievoorbereiding (17-11-2026)

Geen publicatie, geen echte sleutels, geen wijziging aan de live webshop, 2FA, Neon of Render.

## Wat werkt (getest met mocks en nagebootste bronnen)
1. **Zoeken** (Productonderzoek): resultaten tonen bron, controledatum en nu ook "uitgevoerd op …" (live of cache ≤ 10 min). Geen verkoopcijfers, marges of trendscores.
2. **Bewaar als conceptproduct** (knop bij elk resultaat): neemt alleen titel, bron, categorie en bronwinkel over. Prijzen, beschrijving en afbeeldingen blijven leeg tot jij ze invult.
3. **Kandidaten en concepten** (nieuw menu, alleen eigenaar): bewerken, 7 beoordelingscontroles, status nieuw → in beoordeling → geselecteerd / afgewezen (afgewezen blijft bewaard; er is geen verwijderfunctie). Marge wordt alleen uit jouw eigen invoer berekend.
4. **Productpublicatie**: geselecteerde concepten verschijnen daar met de bestaande controles (prijzen, marge ≥ 20%, titel, beschrijving, afbeeldingen, SKU, dubbele producten), WooCommerce-voorbeeld (altijd `draft`) en goedkeuring die aan de exacte gegevens is gebonden (1 uur).
5. **Verzenden als concept**: alleen mogelijk als alle 7 controles zijn afgevinkt, goedgekeurd, expliciet bevestigd én `NUVEMIXA_WOO_WRITE=on` plus de schrijfvariabelen bestaan. Nu staat dit uit, dus er wordt niets verzonden.

## WooCommerce: bestaand en ontbrekend
- Bestaand: alleen-lezen koppeling (`nv_woo_bridge`, leessleutel, hostnaamslot, geen aanroep bij paginaweergave).
- Voorbereid: `nv_woo_writer.py`, uitsluitend `POST /wp-json/wc/v3/products` met `status=draft`, eerst een SKU-controle (bestaat al → niets aanmaken), geen redirects, time-outs, https + hostnaamslot, foutmeldingen zonder sleutels. Getest met mocks.
- Ontbreekt (alleen namen): `NUVEMIXA_WOO_WRITE=on`, `NUVEMIXA_WOO_WRITE_KEY`, `NUVEMIXA_WOO_WRITE_SECRET` (naast bestaande `NUVEMIXA_WOO_URL`, `NUVEMIXA_WOO_HOST`). Een aparte WooCommerce-sleutel met schrijfrechten aanmaken en in Render zetten gebeurt pas na jouw toestemming.
- Let op: WooCommerce haalt afbeeldingen zelf op via de opgegeven https-links; controleer rechten. Merk- en afbeeldingsrechten zijn een beoordelingscontrole.

## Dropshipping zonder eigen voorraad
Beoordelingscontrole "Dropshipping zonder eigen voorraad bevestigd" blijft handmatig; zonder bevestiging door de leverancier blijft het concept onbevestigd. Er is geen automatische ordertoewijzing aan leveranciers.

## Sell The Trend (alleen onderzoek, niets afgesloten)
Gelezen op de eigen pagina's (17-11-2026): product-/trendonderzoek (NEXUS, 26 datapunten, "trend velocity scoring", methode niet vermeld), leveranciersdirectory (bijna 1.200, o.a. AliExpress en CJdropshipping), bestelautomatisering en WooCommerce-"Full Automation". **Geen API vermeld.** Alleen betaald: Essential $49,97/mnd ($32,97 jaarlijks), Pro $99,97, Pro+ $299,97; 14 dagen proef met betaalmiddel. Eigen cijfers zijn inconsistent (200M+ of 7 miljoen producten).
Aansluiten later: (a) via de WooCommerce-integratie van Sell The Trend (hij schrijft dan zelf in je webshop: apart besluit, raakt de live shop), of (b) handmatig gevonden producten als concept in dit dashboard zetten. Een directe dashboardkoppeling is niet vastgesteld mogelijk. Staat als "mogelijke partner (betaald)" in Partners zoeken.

## Open PR's
- #58 (Productonderzoek 500): conflicteert (nv_product_discovery.py, dashboard.html, test); het probleem is hier opgelost en getest → sluiten of vervangen, niet samenvoegen.
- #75 (databasepool, standaard uit): geen conflicten; gecombineerd met deze branch 522 geslaagd. Onafhankelijk; apart beoordelen voor Render.

## Beperkingen
- Niet live getest tegen leveranciers of WooCommerce (geen toegang vanuit de testomgeving).
- Concepten staan in `research_notes`: tijdelijk op Render Free (SQLite); in de dashboard-Postgres blijvend.
- Een brug van partnerkandidaten naar concepten is er alleen via het veld "leverancier" (handmatig).
