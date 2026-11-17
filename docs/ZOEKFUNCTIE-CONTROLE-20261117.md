# Controle productzoekfunctie (PR #80) — 17 november 2026

> **Lees dit eerst.** Alle zoekresultaten hieronder komen uit **nagebootste testdata** (`tests/zoek_fixture.py`). Er is **geen enkel
> echt leveranciersantwoord** gebruikt. Echte bronnen waren vanuit deze omgeving niet bereikbaar (10 publieke zoekpagina's van
> bronnen werden door de sessie geweigerd: "niet op de allowlist"); die blokkade is niet omzeild. De "13 gevonden" in eerdere
> berichten zijn dus **13 testproducten die de code correct verwerkt**, geen 13 producten bij echte leveranciers.

## 1. Controles
| # | Controle | Uitkomst |
|---|---|---|
| 1 | GitHub-test op laatste commit | Zie de GitHub-check `test` op de laatste commit van PR #80. |
| 2 | Screenshots 5 categorieën | 30 afbeeldingen (15 zoekopdrachten × desktop/mobiel), zie §2. Elk met banner "NAGEBOOTSTE TESTDATA". |
| 3 | Valse matches | 15 afwijkende meerwoordzoekopdrachten (ander model, merk, inhoud, afmeting, producttype): **0 worden als bevestigd getoond** (tests). |
| 4 | Welke bronnen leveren welke categorie | Uit de code, niet live bevestigd. Zie §3. |
| 5 | Waarom Gadgets vooral opladers | Zie §4. |
| 6 | Echte dropshipping vs. informatielinks | Zie §5. |
| 7 | Uitleg bij nul resultaten | Ja: "Geen bevestigd product en geen bevestigde leverancier gevonden… dat betekent niet dat het product niet bestaat", plus tabblad Leveranciers met "Verder zoeken (niet bevestigd)". |
| 8 | Beveiliging en WooCommerce-tests | Volledige testset: 430 geslaagd, 42 overgeslagen (PostgreSQL/Windows, niet gedraaid), 0 mislukt. Staff-regel `== "on"` en alle Woo-tests (geen aanroep bij openen) slagen. |

## 2. Visuele bewijsstukken (testdata)
| Categorie | Zoekopdracht | Uitkomst (TESTDATA) | Desktop | Mobiel |
|---|---|---|---|---|
| Gadgets | Apple AirTag 4-pack | geen match (terecht) | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/gadgets-01-apple-airtag-4-pack-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/gadgets-01-apple-airtag-4-pack-mobiel.png) |
| Gadgets | Sony WH-1000XM5 koptelefoon | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/gadgets-02-sony-wh-1000xm5-koptelefoon-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/gadgets-02-sony-wh-1000xm5-koptelefoon-mobiel.png) |
| Gadgets | Anker Soundcore Bluetooth speaker | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/gadgets-03-anker-soundcore-bluetooth-sp-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/gadgets-03-anker-soundcore-bluetooth-sp-mobiel.png) |
| Beauty & Care | NIVEA Soft Hydraterende Crème 200 ml | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/beauty-care-04-nivea-soft-hydraterende-crem-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/beauty-care-04-nivea-soft-hydraterende-crem-mobiel.png) |
| Beauty & Care | Philips OneBlade scheerapparaat | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/beauty-care-05-philips-oneblade-scheerappar-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/beauty-care-05-philips-oneblade-scheerappar-mobiel.png) |
| Beauty & Care | The Ordinary Niacinamide serum | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/beauty-care-06-the-ordinary-niacinamide-ser-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/beauty-care-06-the-ordinary-niacinamide-ser-mobiel.png) |
| Lifestyle & Sport | Decathlon yogamat 8 mm | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/lifestyle-sport-07-decathlon-yogamat-8-mm-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/lifestyle-sport-07-decathlon-yogamat-8-mm-mobiel.png) |
| Lifestyle & Sport | Nike Dri-FIT hardloopshirt | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/lifestyle-sport-08-nike-dri-fit-hardloopshirt-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/lifestyle-sport-08-nike-dri-fit-hardloopshirt-mobiel.png) |
| Lifestyle & Sport | Bidon 750 ml roestvrij staal | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/lifestyle-sport-09-bidon-750-ml-roestvrij-staal-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/lifestyle-sport-09-bidon-750-ml-roestvrij-staal-mobiel.png) |
| Home & Living | Bamboe opbergbox met deksel | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/home-living-10-bamboe-opbergbox-met-deksel-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/home-living-10-bamboe-opbergbox-met-deksel-mobiel.png) |
| Home & Living | Philips Hue woonkamer tafellamp | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/home-living-11-philips-hue-woonkamer-tafell-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/home-living-11-philips-hue-woonkamer-tafell-mobiel.png) |
| Home & Living | Velvet sierkussen 45x45 | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/home-living-12-velvet-sierkussen-45x45-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/home-living-12-velvet-sierkussen-45x45-mobiel.png) |
| Smart Home | Ring Video Doorbell | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/smart-home-13-ring-video-doorbell-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/smart-home-13-ring-video-doorbell-mobiel.png) |
| Smart Home | TP-Link Tapo C200 camera | 1 testproduct + 1 testleverancier | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/smart-home-14-tp-link-tapo-c200-camera-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/smart-home-14-tp-link-tapo-c200-camera-mobiel.png) |
| Smart Home | Philips Hue slimme lamp E27 | geen match (terecht) | [desktop](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/smart-home-15-philips-hue-slimme-lamp-e27-desktop.png) | [mobiel](https://github.com/mdscoop7-max/Nuvemixa-/blob/fix/productzoeken-algemeen-20261117/docs/zoek-bewijs/smart-home-15-philips-hue-slimme-lamp-e27-mobiel.png) |

## 3. Tabel per categorie (doelland NL)

### Gadgets
| | |
|---|---|
| Geteste producten | Sony WH-1000XM5 koptelefoon · Anker Soundcore Bluetooth speaker · Apple AirTag 4-pack |
| Bevestigd uit echte bronnen | **Geen** (bronnen niet bereikbaar vanuit deze omgeving) |
| Resultaten uit testdata | 2 gevonden (nagebootst bij Nedis), AirTag terecht leeg |
| Bronnen in de code | Hoofdcatalogi: UGREEN, Baseus, Xtorm, Nedis (merk-/fabrikantwebshops). Verder Hama (NL/DE distributeur), Hurtel (PL groothandel), Syncee (marktplaats), CJdropshipping (één vaste powerbank-referentie) |
| Ontbrekende dekking | Geen bron voor merken als Sony, Apple, Bose of Anker; geen brede elektronica-groothandel met bevestigde dropshipping |
| Beperkingen | Merk-webshops verkopen vooral eigen producten; merk moet in de titel staan |

### Beauty & Care
| | |
|---|---|
| Geteste producten | NIVEA Soft Hydraterende Crème 200 ml · Philips OneBlade · The Ordinary Niacinamide serum |
| Bevestigd uit echte bronnen | **Geen** |
| Resultaten uit testdata | 3 gevonden (nagebootst bij Pureoil, Aytira, Cocunat) |
| Bronnen in de code | Hoofd: Cocunat. Fallback NL: Pureoil, Aytira, Aurgan (olie/argan-nichewinkels). Fallback buiten NL: Naissance (GB), McGrocer (GB), Veloura (US), Kumi (US) |
| Ontbrekende dekking | Geen drogisterij- of merkenleverancier (NIVEA, The Ordinary, Philips); de aangesloten shops zijn kleine niche- of eigenmerkwinkels |
| Beperkingen | Fallback-bronnen buiten NL: verzending naar NL niet bevestigd |

### Lifestyle & Sport
| | |
|---|---|
| Geteste producten | Decathlon yogamat 8 mm · Nike Dri-FIT hardloopshirt · Bidon 750 ml roestvrij staal |
| Bevestigd uit echte bronnen | **Geen** |
| Resultaten uit testdata | 3 gevonden (nagebootst bij Manduka, ATLETICA, GORNATION) |
| Bronnen in de code | Hoofd: Manduka (yoga). Fallback: GORNATION, ATLETICA (fitness/gym, EU) |
| Ontbrekende dekking | Geen sportkleding- of schoenenleverancier, geen drinkflessen-leverancier; Nike/Decathlon niet aangesloten |
| Beperkingen | Alleen yoga- en fitnessmerken |

### Home & Living
| | |
|---|---|
| Geteste producten | Bamboe opbergbox met deksel · Philips Hue woonkamer tafellamp · Velvet sierkussen 45x45 |
| Bevestigd uit echte bronnen | **Geen** |
| Resultaten uit testdata | 3 gevonden (nagebootst bij Ferm Living) |
| Bronnen in de code | Ferm Living (enige NL-leverbare catalogus); fallback AMEICO en Zafferano America (alleen VS, lampen). dropXL, Versa, Sirocco, BigBuy, Ikonka zijn alleen **informatielinks** ("Verder zoeken") |
| Ontbrekende dekking | Eén designmerk dekt geen opbergboxen, kussens of verlichting in de breedte; er is geen IKEA of andere woonwinkel gekoppeld |
| Beperkingen | De dropshippinggidsen worden niet doorzocht, alleen getoond |

### Smart Home
| | |
|---|---|
| Geteste producten | Ring Video Doorbell · TP-Link Tapo C200 camera · Philips Hue slimme lamp E27 |
| Bevestigd uit echte bronnen | **Geen** |
| Resultaten uit testdata | 2 gevonden (nagebootst bij SwitchBot en eufy), Hue-lamp terecht leeg |
| Bronnen in de code | Nedis, SwitchBot, eufy; fallback OpenELAB; Hurtel (PL groothandel, gadgets en smart home) |
| Ontbrekende dekking | Ring, TP-Link en Philips Hue zijn niet aangesloten; eufy en SwitchBot verkopen alleen eigen merk |
| Beperkingen | Eigenmerk-shops: merk van de zoekopdracht moet gelijk zijn |

## 4. Waarom Gadgets vooral opladers vond
Geen USB-standaard, maar zeven samenwerkende oorzaken in de code:
1. Alle vier hoofdcatalogi zijn oplader-/kabelmerken (UGREEN, Baseus, Xtorm, Nedis) met als startzoekterm "power bank".
2. Elke catalogus had een smalle woordenlijst (oplader, usb, powerbank…); een ander product werd afgewezen. *Opgelost bij specifieke zoekopdrachten.*
3. De categorielijst `CATEGORY_HINTS` voor Gadgets bevatte vooral opladers en kabels; smartwatch, projector, SSD, webcam, drone ontbraken terwijl je shop die verkoopt. *Verbreed; bij specifieke zoekopdrachten beslist de productmatch ook bij Syncee, Hama en Hurtel.*
4. Hama zoekt zonder zoekterm op "powerbank" en heeft één vast Qi2-powerbankmodel.
5. De CJ-referentie is één vaste magnetische powerbank.
6. Nedis krijgt een speciale powerbank-zoekopdracht.
7. Nieuwsbronnen (TechRadar, 9to5Mac, Android Central) leveren artikelen, geen leveranciers.

**Andere gadgets kunnen (volgens de code, niet live bevestigd) leveren:** Nedis (volgens woordenlijst: koptelefoons en Bluetooth-speakers; camera's onder Smart Home), UGREEN en Baseus (volgens hun woordenlijst: opladers, usb-producten, laptopstandaards), Hama (accessoires), Hurtel (elektronica-groothandel), Syncee (brede marktplaats, account nodig).

## 5. Echte dropshipping of alleen informatie?
Niets hieronder is door mij live geverifieerd; het is wat de code en de bronpagina's zelf vermelden.

| Soort | Bronnen | Betekenis |
|---|---|---|
| Dropshipping genoemd op eigen bronpagina (voorwaarden per SKU nog te controleren) | CJdropshipping (agreement + API), BigBuy (API/dropshipping), Sirocco, dropXL, JG Distribution, Versa Group, Avasam, Ikonka, Hertwill | Kandidaten om te onderzoeken. In de app alleen als **informatielink** ("Verder zoeken"); de zoekmotor doorzoekt hun catalogus niet. Alleen CJ heeft een vlag `dropshipping=True` (één vaste referentie). |
| Marktplaats met account | Syncee | Publieke lijst wordt doorzocht; levering per product en account/koppeling vereist |
| Groothandel, uitdrukkelijk **geen** dropshipping | Hurtel | Code zet `dropshipping=False` |
| Fabrikant/merk met zakelijk of wholesale-programma | UGREEN, Baseus, Xtorm, Nedis, eufy, Ferm Living, Manduka, GORNATION, Naissance, OpenELAB | Geen dropshipping bevestigd; aanmeld- of contactpagina |
| Gewone webwinkel, zakelijke voorwaarden onbekend | SwitchBot, Cocunat, Pureoil, Aytira, Aurgan, McGrocer, Veloura, Kumi, ATLETICA, AMEICO, Zafferano America | Alleen productzoeker; "Webwinkel (niet bevestigd)" |
| Alleen zoeklinks | Google, TikTok, Instagram, Facebook; publicaties | Informatief |

## 6. Wat dit NIET bewijst
- Dat een van deze bronnen nu echt producten teruggeeft (bereikbaarheid, blokkades, wijzigingen aan hun zoekfunctie).
- Dat een leverancier naar NL levert of dropshipping toestaat.
- Eerste echte controle moet na uitrol gebeuren, met één zoekopdracht per categorie, zonder OpenAI of betaalde diensten.
