# Partnerzoeker NUVEMIXA (17-11-2026)

Bouwt voort op de leveranciersregistratie van PR #80. Geen betaalde AI, geen abonnement, geen contract, geen automatische aanvraag of affiliateaanmelding, geen wijziging aan WooCommerce, 2FA, Neon of Render.

## Modellen (strikt gescheiden)
A directe dropshipping · B potentiële dropship-/resellerpartner (nog te vragen) · C affiliate (NUVEMIXA is niet de verkoper; nooit automatisch in WooCommerce).
Status per bedrijf: aantoonbaar dropshipping · mogelijke partner · alleen affiliate · ongeschikt. Per criterium (11) een status: **feit** (gelezen op de eigen pagina), **aanwijzing** (derde bron, zoekresultaat of bestaande code), **onbekend**.

## Vastgestelde bedrijven (bron = gelezen pagina; alles onder voorbehoud, niets is een overeenkomst)
- Beautinow (NL, parfum): biedt dropshipping aan, EU+VK, productfeed, aanvraag per e-mail. Kosten en voorwaarden onbekend.
- Droppery (NL): leveranciers keuren webshops goed; Lightspeed/Sendcloud-apps; WooCommerce niet vermeld.
- Hertwill (EE), BigBuy (ES), Syncee, CJdropshipping, dropXL: grote/gevestigde platformen (zie register voor bron en kosten).
- Aqara, Homey (smart home): resellerprogramma's met aanvraag; dropshipping niet vermeld. Nuki: ongeschikt (installateurs).
- Alleen via derde bron (aanwijzing): GOGETTERS, SelfNamed, Everspring, Droplo, Orderchamp, Awin, Daisycon, TradeTracker, 123Wonen (affiliate).
- Ongeschikt: BrandsGateway (mode, vanaf €180/mnd), SaleHoo (betaalde gids).
- Niet onderzocht (pagina niet bereikbaar): Versa, Sirocco, JG Distribution, Avasam.
- Extra merken met zakelijke aanmeldlink worden uit de bestaande catalogusbronnen afgeleid (model B, alleen aanwijzing).

## Kleinere webshops vinden
Geen enkele kleine webshop is als dropshippingpartner vastgesteld: dat kan alleen na contact. De pagina genereert per filter (zoekwoord/categorie/land) handmatige zoeklinks (reseller/dealer, B2B/groothandel, affiliate, fabrikanten) en laat een eigen vondst bewaren, gemarkeerd als ongecontroleerd.

## Gebouwd
`nv_partners.py`, dashboardmenu **Partners zoeken**: filters (productnaam, categorie, land, type, model, status, gratis/betaald, API/feed), kaarten met criteriatabel en score (geschiktheid alleen uit bekende gegevens + zekerheidslabel), kandidatenlijst (bewaard via de bestaande leverancierslijst als "[Kandidaat …]", status onderzoek; verstuurt niets).

## Eerlijke beperkingen
Niet live getest op Render; alle bedrijfsgegevens komen uit een leessessie op 17-11-2026 en kunnen veranderen. De kandidatenlijst gebruikt SQLite op Render Free en is tijdelijk. Screenshots: `docs/zoek-bewijs/partners-*.png` (echte paginarender van het register, geen testdata van leveranciers).
