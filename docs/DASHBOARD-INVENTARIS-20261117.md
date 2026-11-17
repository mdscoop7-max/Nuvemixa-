# NUVEMIXA-dashboard: inventarisatie 17 november 2026

Peildatum: integratiebranch `41fad63` (PR #73–#77 samengevoegd). Gemeten lokaal met een testbeheerder, zonder Woo-, OpenAI- of Mollie-instellingen en zonder externe aanroepen. Basislijn tests: 289 geslaagd, 42 overgeslagen (Postgres-tests zonder testdatabase).

Alle 24 menuonderdelen geven HTTP 200. Er is niets verwijderd of hernoemd.

## Menu (4 groepen + Dashboard)

| Groep | Onderdeel | Status lokaal | Toelichting |
|---|---|---|---|
| Home | Dashboard | Werkt, dubbel | Twee overzichtsblokken onder elkaar met overlappende kerncijfers (oud blok + "NUVEMIXA Control"). |
| Winkel | Producten | Werkt | Zoeken in testcatalogus (100 producten). |
| | Categorieën | Werkt | 5 hoofdcollecties. |
| | Afbeeldingen | Werkt | |
| | Bestellingen | Wacht op koppeling | Alleen-lezen WooCommerce-orders; zonder instellingen "niet gekoppeld". |
| | Klanten | Gedeeltelijk | Klantaccount aanmaken aanwezig; lokale klantdatabase niet leesbaar in testomgeving. |
| | Klantenservice | Wacht op koppeling | Gmail nog niet gekoppeld; versturen alleen met toestemming. |
| | Kortingen | Werkt | Kortingscodes en testberekening. |
| Onderzoek | Productonderzoek | Werkt | Bronnen en beoordeling aanwezig. |
| | Internationaal marktonderzoek | Werkt | |
| | Viral Product Finder | Werkt | |
| | Prijs- en margecalculator | Werkt | Margetests aanwezig. |
| | Rapportages | Gedeeltelijk | Alleen cataloguscijfers; omzet niet meetbaar; bezoekerstelling uit tot `NUVEMIXA_WEBSHOP_TRACKING=true`. |
| Vindbaarheid | SEO & GEO | Werkt | |
| | RankFix AI | Wacht op koppeling | Buiten scope van deze opdracht. |
| | Google Shopping | Werkt | Merchant-voorbeeldfeed; pagina is zeer groot (~105 kB tekst). |
| | Google Ads | Wacht op koppeling | Geen autorisatie. |
| | Marketing | Werkt | Verwijspagina. |
| | Talen | Leeg | Geen inhoud, alleen "niet gekoppeld". |
| Beheer | Leveranciers | Werkt | Inclusief AI-leverancierszoekbalk (sleutel ontbreekt bewust). |
| | WooCommerce | Wacht op koppeling | Niet ingesteld. |
| | Accountbeheer | Werkt | Bevat medewerkersbeheer (zie risico's). |
| | Monitoring | Werkt | Systeemcontrole. |
| | Instellingen | Werkt | |

## Bevindingen

1. Dashboard-home bevat twee overzichten die deels hetzelfde tonen.
2. Talen en Klantenservice zijn alleen een melding; Rapportages heeft geen omzet.
3. Er bestaat een medewerkerssysteem (`staff_auth`, Accountbeheer). Dat botst met "alleen eigenaar". Niet verwijderd: besluit van de eigenaar nodig.
4. Klantaccounts (webshop) staan los van beheerderssessie (`nv_admin`); bestaande beveiligingstests slagen.
5. Productpublicatie naar WooCommerce, dubbele-productcontrole en margeoverzicht per product zijn nog niet als geheel bevestigd; vereist Woo-configuratie of mocks.
6. Administratie (omzet, kosten, winst per product) bestaat nog niet als pagina; alleen calculator.

## Nog ontbrekende koppelingen

WooCommerce (orders/publicatie), Gmail (klantberichten), Google Ads, boekhouding (bewust nog niet), webshoptracking, OpenAI-sleutel (bewust afwezig).
