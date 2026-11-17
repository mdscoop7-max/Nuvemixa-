# NUVEMIXA — openstaande punten (INTERN, niet publiceren)

Deze punten zijn bewust leeg gelaten; er zijn geen gegevens verzonnen.

| Onderdeel | Wat ontbreekt | Waar het in de code zit |
|---|---|---|
| KvK-nummer, rechtsvorm, vestigingsadres | Echte bedrijfsgegevens | Juridische pagina's (`/voorwaarden`, `/privacy`, `/over-nuvemixa`) vermelden nu "volgt vóór livegang" |
| Btw-nummer en btw-tarieven | Btw-gegevens en prijsweergave incl./excl. btw | Winkelwagen/checkout tonen "btw wordt getoond zodra gegevens bevestigd zijn" |
| Verzendkosten en levertijden | Tarieven per land/leverancier | `nv_checkout.order_summary()` geeft `shipping: None`; checkout toont "Wordt later bepaald" |
| Betaalprovider (bijv. Mollie) en betaalmethoden | Contract, sleutels, webhook | `nv_checkout.PaymentProvider` is een lege aansluiting (`configured=False`); geen betaling mogelijk |
| Definitieve juridische teksten | Voorwaarden, privacyverklaring, herroeping door jurist | Huidige teksten zijn ontwikkelfase-teksten |
| Retouradres en klantenservice-gegevens | Echt adres/e-mail/telefoon | Contact- en retourpagina |
| Echte producten en leveranciers | Alle huidige producten zijn voorbeeld/demo | `products/*/products.json` |
| Hero-afbeeldingen met "TrendMix"/ingebakken tekst | Nieuwe artwork door eigenaar (afbeeldingen zijn niet aangepast) | `static/images/hero/` |
