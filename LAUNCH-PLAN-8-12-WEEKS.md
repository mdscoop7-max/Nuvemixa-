# Trend Mix — verkoopklaar in 8–12 weken (werkplan)

**Status:** plan, geen livegang of verkoopgarantie. Wijzigingen op de ontwikkelbranch testen vóór merge. Geen eigen voorraad: dropshipping via geverifieerde leveranciers.

## Uitgangspunt
- Start met **5–10 geverifieerde producten** die een herkenbaar probleem oplossen. Dit is een **verkoopselectie**, niet de uiteindelijke omvang van de webshop.
- Bepaal een primaire markt (bijv. Nederland), één duidelijke doelgroep en meetbare conversies.
- Geen betaalde advertenties naar demo-/testproducten, onzekere voorraad, tijdelijke foto's of niet-afgeronde betalingen.
- Productclaims (materiaal, prestaties, certificering, levertijd, prijs, beschikbaarheid) uitsluitend uit gecontroleerde leveranciersgegevens.
- Stel een advertentiebudget en maximaal aanvaardbare acquisitiekosten vast vóór campagne-activatie.

## Week 1–2 — Product en leveranciersselectie
- Controleer Droppery, BTSWholesaler en eventueel andere EU-leveranciers op assortiment, dropshippingvoorwaarden, werkelijke verzendkosten, retourafhandeling, feed/API, voorraadupdate, facturatie en tracking.
- Maak per kandidaat een productrecord: supplier_id, leverancier, merk, GTIN/EAN (indien aanwezig), SKU, variant, prijs inclusief btw, inkoopprijs, verzendkosten, levertijd, voorraadstatus, afbeeldingsrechten, specificaties, garanties, retouradres en land van levering.
- Selecteer pas definitief na aantoonbare product- en leveringsinformatie. Geen nepbeoordelingen of verzonnen USP's.
- Productkeuze: zoekintentie, vraag, voldoende marge, lage retourkans en duidelijke voordelen. Begin niet met claims die wettelijk bewijs vereisen.

## Week 2–4 — Betalingen en operationele betrouwbaarheid (blokkerend)
- Controleer bestaande Flask-/WooCommerce-koppeling: `create_woo_order` maakt bestellingen aan met `set_paid: False` en lege `payment_method`; dit bewijst **geen** werkende betaalafhandeling.
- Integreer een legitieme hosted checkout/betaalprovider of bestaande WooCommerce-betaalflow; verifieer betaalbevestiging op de server, idempotentie, mislukte/geannuleerde betalingen en orderstatus. Geheimen uitsluitend in omgevingvariabelen.
- Doe een echte toegestane end-to-end proefbestelling met testmodus/sandbox waar mogelijk; controleer voorraadreservering, bevestigingsmail, verzendstatus, annulering en retourproces.
- Controleer verplichte consumenten- en bedrijfsinformatie voor de daadwerkelijke verkooplanden; laat juridische/btw-specifieke punten zo nodig deskundig toetsen.
- Controleer mobiele checkout, formulieren, CSRF, sessies, betaalintegratie en logmelding van fouten.

## Week 3–5 — Productinformatie voor SEO, AI en Shopping
- Eén canonieke bron per product met titel, feitelijke omschrijving, specificaties, URL, merk, GTIN waar beschikbaar, echte afbeelding, prijs, valuta, beschikbaarheid en verzendinformatie.
- Unieke productbeschrijvingen: concrete toepassing, producteigenschappen, wat inbegrepen is, beperkingen en FAQ op basis van feiten.
- Consistente `Product` JSON-LD, canonical, `BreadcrumbList`, Open Graph en sitemap. Voeg `Offer`-gegevens alleen toe wanneer prijs/voorraad betrouwbaar zijn; gebruik één definitief domein via `SITE_URL`.
- Categoriepagina's met originele tekst, relevante interne links en toegankelijke menustructuur.
- Merchant Center-productfeed pas vullen met overeenkomende prijzen, voorraad, beschikbaarheid en verzend-/retourgegevens.
- Laat demo-artikelen niet als koopklaar adverteren.

## Week 5–8 — Metingen en gecontroleerde lancering
- Test complete klantreis op mobiel en desktop: advertentie > landingspagina > product > winkelwagen > betaling > orderbevestiging.
- Stel analytics in (met passende toestemming), conversiemeting, opbrengst en brutomarge.
- Google Ads: begin beperkt met bewezen koopgerichte zoekvragen/Shopping waar toegestaan; stop zoektermen en producten zonder rendement.
- Meet per product: sessies, add-to-cart, checkout-start, betaalde bestellingen, conversieratio, advertentiekosten, retouren en bijdrage na kosten.
- RankFix scan als QA-instrument, niet als garantie voor ranking of AI-vermelding.

## Week 8–12 — Evalueren en uitbreiden
- Vergelijk gerealiseerde marge met advertentiekosten, verzending, betaalfees, retouren en support.
- Schaal alleen winnaars met verifieerbaar positieve unit economics. Breid de catalogus pas daarna uit.
- Geen vooraf beloofde omzet of aantal orders: resultaten hangen af van product-markt-fit, budget, uitvoering en vraag.

## Beslisregels voor 'klaar voor advertenties'
- [ ] Leverancier en voorraad bewezen
- [ ] Foto's en productclaims geverifieerd
- [ ] Eindprijs, btw, verzending en levertijd betrouwbaar
- [ ] Werkende betaalflow en bevestigde orderstatus
- [ ] Retour-/contact-/bedrijfsinformatie klopt
- [ ] SEO/structured data valide en consistent
- [ ] Consent en conversiemeting ingericht
- [ ] Mobile QA en volledige regressietests slagen
- [ ] Reclame- en acquisitiebudget met stopcriteria vastgesteld

## Unit economics per bestelling
`bijdrage = verkoopprijs excl. btw - inkoop excl. btw - verzend-/fulfilmentkosten - betaalfees - verwachte retour-/supportkosten - advertentiekosten`

**Open beslissingen:** markt/land, leverancierscontracten, domein, concrete betaalprovider, startbudget en de geverifieerde eerste 5–10 producten. Geen van deze punten stilzwijgend invullen.
