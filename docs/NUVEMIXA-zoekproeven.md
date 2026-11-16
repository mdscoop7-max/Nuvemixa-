# NUVEMIXA AI Productonderzoek — lokale zoekproeven

De basis was lokaal inhoudelijk identiek aan Render-commit `f71c931f2eef1b684f9996313b0392ff688852f9`. Render verwees een verzoek zonder sessie naar de inlogpagina. De zeven lege resultaten zijn gereproduceerd via de lokale backend van diezelfde versie. De exacte filterinstellingen uit de oorspronkelijke gebruikerssessie waren onbekend.

De twee backendproeven gebruikten Nederland, Alle leveranciers, alle standaardbronnen en het eerdere standaardzoektype Trends en nichekansen. In de browserproef is via het lokale formulier gezocht met Nederland en de nieuwe standaard Producten zoeken. De browser gebruikte testauthenticatie. Externe product- en publicatiebronnen zijn echt benaderd.

| Zoekopdracht | Basis producten / leveranciers | Nieuwe backend producten / leveranciers | Browser producten / leveranciers | Zoekduur nieuwe backend |
|---|---:|---:|---:|---:|
| Pure Argan Huidolie - 100ml | 0 / 0 | 3 / 0 | 2 / 0 bij 1440 px | 11,1 s |
| Elektrische siliconen gezichtsreinigingsborstel met USB-C | 0 / 0 | 1 / 0 | 1 / 0 bij 390 px | 11,0 s |
| Arganolie Puur & Koudgeperst | 0 / 0 | 3 / 0 | 3 / 0 bij 390 px | 10,9 s |
| WiFi slimme stekker 16A met energiemeter | 0 / 0 | 1 / 1 | 1 / 1 bij 1440 px | 7,3 s |
| Weerstandsbanden fitness set | 0 / 0 | 12 / 5 | 11 / 4 bij 1440 px | 8,3 s |
| Draadloze LED tafellamp oplaadbaar USB-C | 0 / 0 | 10 / 1 | 10 / 1 bij 390 px | 8,0 s |
| NIVEA Soft Hydraterende Crème 200 ml | 0 / 0 | 2 / 0 | 2 / 0 bij 390 px | 10,2 s |
| Magnetische powerbank 10.000 mAh met USB-C | 20 / 5 | 21 / 6 | 21 / 6 bij 1440 px | 10,9 s |

Productaantallen tellen beschikbare bronvermeldingen na samenvoeging op bron-ID, link of geverifieerde barcode. Verschillende uitvoeringen kunnen apart opgenomen zijn. Het leveranciersaantal telt uitsluitend de afzonderlijke bedrijven in het leverancierstabblad. Dit aantal bewijst op zichzelf geen dropshipping of levering aan Nederland.

Elke rij hieronder is één indexaanroep. Ruwe aantallen kunnen bij verschillende varianten dezelfde vermeldingen bevatten. De tabel bevat gemeten catalogus- en Syncee-aantallen. De andere bronadapters geven in deze proef geen ruwe aantallen terug. Op de oude versie staat de Syncee-HTML-telling afzonderlijk vermeld omdat die maat ook niet-geparseerde HTML-markeringen bevat.

## Pure Argan Huidolie - 100ml

**Basisversie**

Cocunat gaf twee algemene olievermeldingen terug. De volledige Nederlandstalige zoekterm werd als woordfilter gebruikt.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| www.techradar.com | pure argan huidolie 100ml | ruwe indexhits niet gemeten |
| www.cocunat.com | pure argan huidolie 100ml | 2 |
| syncee.com | pure argan huidolie 100ml | 119 HTML-markeringen |

**Nieuwe versie**

Bronnen in de zoekopdracht — Aurgan, Aytira, Cocunat, Kumi, McGrocer, Naissance, Pureoil, Syncee, TechRadar, Veloura Beauty US.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| Cocunat | Pure Argan Huidolie - 100ml | 0 | 0 | 0 | — |
| Cocunat | pure argan oil skin 100ml | 7 | 0 | 0 | 7 producttype, merk of model komt niet overeen |
| Syncee | argan oil | 59 | 0 | 0 | 13 productlink, categorie of zoekvariant past niet, 38 controlelimiet per leverancier of bron, 8 productspecificaties of levering onbevestigd |
| Cocunat | argan oil | 10 | 0 | 0 | 8 producttype, merk of model komt niet overeen, 2 categorie buiten selectie |
| Veloura Beauty US | Pure Argan Huidolie - 100ml | 0 | 0 | 0 | — |
| Aytira | Pure Argan Huidolie - 100ml | 1 | 0 | 1 | — |
| Kumi | Pure Argan Huidolie - 100ml | 0 | 0 | 0 | — |
| Cocunat | arganolie | 5 | 0 | 0 | 5 producttype, merk of model komt niet overeen |
| Veloura Beauty US | pure argan oil skin 100ml | 0 | 0 | 0 | — |
| Pureoil | Pure Argan Huidolie - 100ml | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Kumi | pure argan oil skin 100ml | 0 | 0 | 0 | — |
| Aurgan | Pure Argan Huidolie - 100ml | 0 | 0 | 0 | — |
| Veloura Beauty US | argan oil | 1 | 0 | 0 | 1 producttype, merk of model komt niet overeen |
| Cocunat | cosmetic argan oil | 10 | 0 | 0 | 9 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Aytira | pure argan oil skin 100ml | 10 | 0 | 1 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie, variantgegevens: HTTP 429 |
| Naissance | Pure Argan Huidolie - 100ml | 4 | 0 | 2 | 2 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Kumi | argan oil | 0 | 0 | 0 | — |
| Syncee | Pure Argan Huidolie - 100ml | 59 | 0 | 0 | 58 productlink, categorie of zoekvariant past niet, 1 productspecificaties of levering onbevestigd |
| Pureoil | pure argan oil skin 100ml | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Kumi | arganolie | 0 | 0 | 0 | — |
| Aytira | argan oil | 10 | 0 | 1 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie, variantgegevens: HTTP 429 |
| Veloura Beauty US | arganolie | 0 | 0 | 0 | — |
| McGrocer | Pure Argan Huidolie - 100ml | 10 | 2 | 5 | 3 categorie buiten selectie, variantgegevens: HTTP 429 |
| Naissance | pure argan oil skin 100ml | 10 | 0 | 2 | 8 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Aurgan | pure argan oil skin 100ml | 0 | 0 | 0 | — |
| Cocunat | argan olie | — | — | 0 | time-out |
| Pureoil | argan oil | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Kumi | cosmetic argan oil | 0 | 0 | 0 | — |
| Veloura Beauty US | cosmetic argan oil | 10 | 0 | 0 | 10 producttype, merk of model komt niet overeen |
| Aytira | arganolie | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Pureoil | arganolie | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Aurgan | argan oil | 0 | 0 | 0 | — |
| Kumi | argan olie | 0 | 0 | 0 | — |
| Syncee | pure argan oil skin 100ml | 59 | 0 | 0 | 58 productlink, categorie of zoekvariant past niet, 1 productspecificaties of levering onbevestigd |
| Veloura Beauty US | argan olie | 0 | 0 | 0 | — |
| Naissance | argan oil | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Aytira | cosmetic argan oil | 10 | 0 | 1 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie, variantgegevens: HTTP 429 |
| Pureoil | cosmetic argan oil | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Aytira | argan olie | 10 | 0 | 1 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie, variantgegevens: HTTP 429 |
| Naissance | arganolie | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Pureoil | argan olie | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Aurgan | arganolie | 10 | 1 | 8 | 1 producttype, merk of model komt niet overeen |
| Naissance | cosmetic argan oil | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Naissance | argan olie | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |

Voorbeeld van een gematchte bronvermelding — [Pure Arganolie Cosmetisch Pipetfles – 100 mL](https://aurgan.nl/product/pure-arganolie-cosmetisch-pipetfles-100-ml/).

Voor dit resultaat was in de proef geen passende leverancier met onderbouwde zakelijke of dropshippingvermelding beschikbaar. De productbron blijft zichtbaar.

## Elektrische siliconen gezichtsreinigingsborstel met USB-C

**Basisversie**

Cocunat gaf geen productvermeldingen. De indexzoekopdracht behield de Nederlandse samenstelling en stuurde USB-C als usbc.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| www.techradar.com | elektrische siliconen gezichtsreinigingsborstel met | ruwe indexhits niet gemeten |
| www.cocunat.com | elektrische siliconen gezichtsreinigingsborstel met usbc | 0 |
| syncee.com | elektrische siliconen gezichtsreinigingsborstel met usbc | 119 HTML-markeringen |

**Nieuwe versie**

Bronnen in de zoekopdracht — Aurgan, Aytira, Cocunat, Kumi, McGrocer, Naissance, Pureoil, Syncee, TechRadar, Veloura Beauty US.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| Cocunat | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 0 | 0 | 0 | — |
| Cocunat | electric silicone facial cleansing brush met USB-C | 0 | 0 | 0 | — |
| Cocunat | facial cleansing brush | 10 | 0 | 0 | 7 producttype, merk of model komt niet overeen, 3 categorie buiten selectie |
| Naissance | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 0 | 0 | 0 | — |
| Kumi | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 3 | 0 | 1 | 1 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| Aytira | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 0 | 0 | 0 | — |
| Pureoil | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 0 | 0 | 0 | — |
| Veloura Beauty US | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 3 | 1 | 0 | 2 producttype, merk of model komt niet overeen |
| McGrocer | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 10 | 0 | 0 | 9 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| Aurgan | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 0 | 0 | 0 | — |
| Syncee | facial cleansing brush | 59 | 0 | 0 | 39 productlink, categorie of zoekvariant past niet, 10 controlelimiet per leverancier of bron, 10 productspecificaties of levering onbevestigd |
| Cocunat | gezichtsreinigingsborstel | 6 | 0 | 0 | 5 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Naissance | electric silicone facial cleansing brush met USB-C | 0 | 0 | 0 | — |
| Kumi | electric silicone facial cleansing brush met USB-C | 5 | 0 | 1 | 3 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| Aytira | electric silicone facial cleansing brush met USB-C | 0 | 0 | 0 | — |
| Pureoil | electric silicone facial cleansing brush met USB-C | 0 | 0 | 0 | — |
| McGrocer | electric silicone facial cleansing brush met USB-C | 10 | 0 | 0 | 9 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| Naissance | facial cleansing brush | 10 | 0 | 0 | 9 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Aurgan | electric silicone facial cleansing brush met USB-C | 0 | 0 | 0 | — |
| Kumi | facial cleansing brush | 7 | 0 | 1 | 3 categorie buiten selectie, 3 producttype, merk of model komt niet overeen |
| Pureoil | facial cleansing brush | 0 | 0 | 0 | — |
| Aytira | facial cleansing brush | 1 | 0 | 0 | 1 categorie buiten selectie |
| Cocunat | silicone face brush | — | — | 0 | time-out |
| McGrocer | facial cleansing brush | 10 | 0 | 0 | 10 categorie buiten selectie |
| Naissance | gezichtsreinigingsborstel | 0 | 0 | 0 | — |
| Kumi | gezichtsreinigingsborstel | 5 | 0 | 1 | 2 producttype, merk of model komt niet overeen, 2 categorie buiten selectie |
| Aytira | gezichtsreinigingsborstel | 1 | 0 | 0 | 1 producttype, merk of model komt niet overeen |
| Syncee | Elektrische siliconen gezichtsreinigingsborstel met USB-C | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Pureoil | gezichtsreinigingsborstel | 1 | 0 | 0 | 1 producttype, merk of model komt niet overeen |
| McGrocer | gezichtsreinigingsborstel | 10 | 0 | 0 | 6 categorie buiten selectie, 4 producttype, merk of model komt niet overeen |
| Aurgan | facial cleansing brush | 0 | 0 | 0 | — |
| Naissance | silicone face brush | 0 | 0 | 0 | — |
| Kumi | silicone face brush | 6 | 0 | 1 | 3 categorie buiten selectie, 2 producttype, merk of model komt niet overeen |
| Aytira | silicone face brush | 1 | 0 | 0 | 1 categorie buiten selectie |
| Pureoil | silicone face brush | 2 | 0 | 0 | 1 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| McGrocer | silicone face brush | 10 | 0 | 0 | 5 producttype, merk of model komt niet overeen, 5 categorie buiten selectie |
| Syncee | electric silicone facial cleansing brush met USB-C | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Aurgan | gezichtsreinigingsborstel | 0 | 0 | 0 | — |
| Aurgan | silicone face brush | 0 | 0 | 0 | — |

Voorbeeld van een gematchte bronvermelding — [Sonic Silicone Facial Cleansing Brush](https://www.velourabeautyus.com/products/sonic-silicone-facial-brush).

Voor dit resultaat was in de proef geen passende leverancier met onderbouwde zakelijke of dropshippingvermelding beschikbaar. De productbron blijft zichtbaar.

## Arganolie Puur & Koudgeperst

**Basisversie**

Cocunat gaf één algemene olievermelding. De strategie probeerde geen Engelse varianten van het producttype en de extractiemethode.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| www.techradar.com | arganolie puur koudgeperst | ruwe indexhits niet gemeten |
| www.cocunat.com | arganolie puur koudgeperst | 1 |
| syncee.com | arganolie puur koudgeperst | 119 HTML-markeringen |

**Nieuwe versie**

Bronnen in de zoekopdracht — Aurgan, Aytira, Cocunat, Kumi, McGrocer, Naissance, Pureoil, Syncee, TechRadar, Veloura Beauty US.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| Cocunat | Arganolie Puur & Koudgeperst | 0 | 0 | 0 | — |
| Cocunat | argan oil pure cold pressed | 10 | 0 | 0 | 10 producttype, merk of model komt niet overeen |
| Cocunat | argan oil | 10 | 0 | 0 | 8 producttype, merk of model komt niet overeen, 2 categorie buiten selectie |
| Syncee | argan oil | 59 | 0 | 0 | 13 productlink, categorie of zoekvariant past niet, 38 controlelimiet per leverancier of bron, 8 productspecificaties of levering onbevestigd |
| Veloura Beauty US | Arganolie Puur & Koudgeperst | 0 | 0 | 0 | — |
| McGrocer | Arganolie Puur & Koudgeperst | 0 | 0 | 0 | — |
| Kumi | Arganolie Puur & Koudgeperst | 0 | 0 | 0 | — |
| Aytira | Arganolie Puur & Koudgeperst | 10 | 0 | 2 | 7 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Pureoil | Arganolie Puur & Koudgeperst | 10 | 1 | 0 | 9 producttype, merk of model komt niet overeen |
| Naissance | Arganolie Puur & Koudgeperst | 2 | 0 | 1 | 1 producttype, merk of model komt niet overeen |
| Cocunat | arganolie | 5 | 0 | 0 | 5 producttype, merk of model komt niet overeen |
| Aurgan | Arganolie Puur & Koudgeperst | 0 | 0 | 0 | — |
| Syncee | Arganolie Puur & Koudgeperst | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Veloura Beauty US | argan oil pure cold pressed | 0 | 0 | 0 | — |
| McGrocer | argan oil pure cold pressed | 10 | 2 | 7 | 1 producttype, merk of model komt niet overeen |
| Kumi | argan oil pure cold pressed | 0 | 0 | 0 | — |
| Naissance | argan oil pure cold pressed | 10 | 0 | 2 | 8 producttype, merk of model komt niet overeen |
| Aytira | argan oil pure cold pressed | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen |
| Cocunat | cosmetic argan oil | 10 | 0 | 0 | 9 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Veloura Beauty US | argan oil | 1 | 0 | 0 | 1 producttype, merk of model komt niet overeen |
| Kumi | argan oil | 0 | 0 | 0 | — |
| Aytira | argan oil | 10 | 0 | 1 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Aurgan | argan oil pure cold pressed | 0 | 0 | 0 | — |
| Naissance | argan oil | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen |
| Syncee | argan oil pure cold pressed | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Cocunat | argan olie | 10 | 0 | 0 | 9 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Veloura Beauty US | arganolie | 0 | 0 | 0 | — |
| Kumi | arganolie | 0 | 0 | 0 | — |
| Aytira | arganolie | 10 | 0 | 1 | 9 producttype, merk of model komt niet overeen |
| Naissance | arganolie | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen |
| Aurgan | argan oil | 0 | 0 | 0 | — |
| Veloura Beauty US | cosmetic argan oil | 10 | 0 | 0 | 10 producttype, merk of model komt niet overeen |
| Kumi | cosmetic argan oil | 0 | 0 | 0 | — |
| Aytira | cosmetic argan oil | 10 | 0 | 1 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Naissance | cosmetic argan oil | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen |
| Veloura Beauty US | argan olie | 0 | 0 | 0 | — |
| Kumi | argan olie | 0 | 0 | 0 | — |
| Aytira | argan olie | 10 | 0 | 1 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Naissance | argan olie | 10 | 0 | 3 | 7 producttype, merk of model komt niet overeen |
| Aurgan | arganolie | 10 | 0 | 9 | 1 producttype, merk of model komt niet overeen |
| Aurgan | cosmetic argan oil | 0 | 0 | 0 | — |
| Aurgan | argan olie | 0 | 0 | 0 | — |

Voorbeeld van een gematchte bronvermelding — [Argan Olie (100% Puur & Koudgeperst)](https://pureoil.nl/products/argan-olie).

Voor dit resultaat was in de proef geen passende leverancier met onderbouwde zakelijke of dropshippingvermelding beschikbaar. De productbron blijft zichtbaar.

## WiFi slimme stekker 16A met energiemeter

**Basisversie**

Nedis gaf tien stekkers met energiemeter. De filter zocht onder meer naar de letterlijke invoer rond 16 A en wifi. Nedis zette de nominale stroom niet in de voorspellende titel of beschrijving. Hurtel gaf een onbruikbaar antwoord.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| eu.eufy.com | wifi smart smart stekker 16a met energiemeter | 0 |
| eu.switch-bot.com | wifi smart smart stekker 16a met energiemeter | 10 |
| nedis-shop.nl | wifi smart smart stekker 16a met energiemeter | 10 |
| www.techradar.com | wifi smart smart stekker 16a met energiemeter | ruwe indexhits niet gemeten |
| www.androidcentral.com | wifi smart smart stekker 16a met energiemeter | ruwe indexhits niet gemeten |
| 9to5mac.com | — | ruwe indexhits niet gemeten |
| hurtel.com | — | ValueError |
| syncee.com | wifi smart smart stekker 16a met energiemeter | 119 HTML-markeringen |

**Nieuwe versie**

Bronnen in de zoekopdracht — 9to5Mac, Android Central, Hurtel, Nedis, OpenELAB, SwitchBot, Syncee, TechRadar, eufy.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| eufy | WiFi slimme stekker 16A met energiemeter | 0 | 0 | 0 | — |
| SwitchBot | WiFi slimme stekker 16A met energiemeter | 7 | 0 | 0 | 1 categorie buiten selectie, 6 producttype, merk of model komt niet overeen |
| Nedis | WiFi slimme stekker 16A met energiemeter | 10 | 0 | 10 | — |
| eufy | wifi smart plug 16A met energy monitoring | 2 | 0 | 0 | 1 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| SwitchBot | wifi smart plug 16A met energy monitoring | 10 | 0 | 0 | 5 categorie buiten selectie, 5 producttype, merk of model komt niet overeen |
| Nedis | wifi smart plug 16A met energy monitoring | 10 | 0 | 10 | — |
| eufy | smart plug | 10 | 0 | 0 | 10 categorie buiten selectie |
| SwitchBot | smart plug | 10 | 0 | 0 | 4 categorie buiten selectie, 6 producttype, merk of model komt niet overeen |
| OpenELAB | WiFi slimme stekker 16A met energiemeter | 3 | 1 | 1 | 1 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| SwitchBot | slimme stekker | 4 | 0 | 0 | 3 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| eufy | slimme stekker | 0 | 0 | 0 | — |
| Nedis | smart plug | 10 | 0 | 8 | 2 producttype, merk of model komt niet overeen |
| SwitchBot | wifi energy monitoring plug | 10 | 0 | 0 | 5 categorie buiten selectie, 5 producttype, merk of model komt niet overeen |
| Nedis | slimme stekker | 10 | 0 | 9 | 1 producttype, merk of model komt niet overeen |
| eufy | wifi energy monitoring plug | 10 | 0 | 0 | 3 categorie buiten selectie, 7 producttype, merk of model komt niet overeen |
| Syncee | smart plug | 59 | 0 | 0 | 45 productlink, categorie of zoekvariant past niet, 5 controlelimiet per leverancier of bron, 9 productspecificaties of levering onbevestigd |
| Nedis | wifi energy monitoring plug | 10 | 0 | 9 | 1 producttype, merk of model komt niet overeen |
| Syncee | WiFi slimme stekker 16A met energiemeter | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Syncee | wifi smart plug 16A met energy monitoring | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |

Bronbeperkingen — Hurtel (onverwacht of onbruikbaar bronantwoord).

Voorbeeld van een gematchte bronvermelding — [SONOFF iPlug Wi-Fi Smart Plug Type E/F](https://openelab.io/products/sonoff-s60tpf).

Leverancierskaarten — OpenELAB (buiten EU).

## Weerstandsbanden fitness set

**Basisversie**

Manduka gaf geen weerstandsbanden terug. De directe sportcatalogus richtte zich vooral op yoga.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| eu.manduka.com | weerstandsbanden fitness set | 0 |
| www.techradar.com | weerstandsbanden fitness set | ruwe indexhits niet gemeten |
| syncee.com | weerstandsbanden fitness set | 119 HTML-markeringen |

**Nieuwe versie**

Bronnen in de zoekopdracht — ATLETICA, GORNATION, Manduka, Syncee, TechRadar.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| Manduka | Weerstandsbanden fitness set | 0 | 0 | 0 | — |
| Manduka | resistance band fitness set | 1 | 0 | 0 | 1 categorie buiten selectie |
| Manduka | resistance bands set | 3 | 0 | 0 | 2 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| GORNATION | Weerstandsbanden fitness set | 10 | 1 | 1 | 3 producttype, merk of model komt niet overeen, 5 categorie buiten selectie |
| Manduka | weerstandsbanden set | 1 | 0 | 0 | 1 producttype, merk of model komt niet overeen |
| ATLETICA | Weerstandsbanden fitness set | 10 | 7 | 3 | — |
| Manduka | exercise bands set | — | — | 0 | time-out |
| Syncee | resistance bands | 59 | 4 | 0 | 5 productlink, categorie of zoekvariant past niet, 45 controlelimiet per leverancier of bron, 5 productspecificaties of levering onbevestigd |

Voorbeeld van een gematchte bronvermelding — [Premium Resistance Bands Set](https://www.gornation.com/products/premium-resistance-bands-set).

Leverancierskaarten — GORNATION (binnen EU), Lifebay (vestigingsland onbevestigd), Primebay (vestigingsland onbevestigd), NNE Living (buiten EU), Harmonie-Hernandez (vestigingsland onbevestigd).

## Draadloze LED tafellamp oplaadbaar USB-C

**Basisversie**

Ferm Living gaf meerdere kleurvermeldingen van Arum Portable Lamp terug. De Nederlandse term oplaadbaar en de benaming tafellamp werden niet goed verbonden aan de Engelse beschrijving van dezelfde lamp.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| fermliving.com | wireless led table lamp oplaadbaar usbc | 10 |
| www.techradar.com | wireless led table lamp oplaadbaar | ruwe indexhits niet gemeten |
| syncee.com | wireless led table lamp oplaadbaar usbc | 119 HTML-markeringen |
| fermliving.com | wireless led tafellamp oplaadbaar usbc | 10 |
| fermliving.com | wireless led desk lamp oplaadbaar usbc | 10 |

**Nieuwe versie**

Bronnen in de zoekopdracht — Ferm Living, Syncee, TechRadar.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| Ferm Living | Draadloze LED tafellamp oplaadbaar USB-C | 10 | 10 | 0 | — |
| Syncee | table lamp | 59 | 0 | 0 | 47 controlelimiet per leverancier of bron, 12 productspecificaties of levering onbevestigd |
| Syncee | Draadloze LED tafellamp oplaadbaar USB-C | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Syncee | wireless led table lamp rechargeable USB-C | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |

Voorbeeld van een gematchte bronvermelding — [Arum Portable Lamp - White](https://fermliving.com/products/arum-portable-lamp-white).

Leverancierskaarten — Ferm Living (binnen EU).

## NIVEA Soft Hydraterende Crème 200 ml

**Basisversie**

Cocunat gaf geen NIVEA-vermeldingen. Een catalogus van het eigen merk Cocunat kan het assortiment van NIVEA niet afdekken.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| www.techradar.com | nivea soft hydraterende crème | ruwe indexhits niet gemeten |
| www.cocunat.com | nivea soft hydraterende crème 200 ml | 0 |
| syncee.com | nivea soft hydraterende crème 200 ml | 119 HTML-markeringen |

**Nieuwe versie**

Bronnen in de zoekopdracht — Aurgan, Aytira, Cocunat, Kumi, McGrocer, Naissance, Pureoil, Syncee, TechRadar, Veloura Beauty US.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| Cocunat | NIVEA Soft Hydraterende Crème 200 ml | 0 | 0 | 0 | — |
| Syncee | NIVEA Soft Hydraterende Crème 200 ml | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Cocunat | nivea soft moisturizing cream 200ml | 0 | 0 | 0 | — |
| Syncee | nivea soft moisturizing cream 200ml | 59 | 0 | 0 | 59 productlink, categorie of zoekvariant past niet |
| Cocunat | nivea soft moisturizing cream | 10 | 0 | 0 | 10 producttype, merk of model komt niet overeen |
| Cocunat | nivea soft hydraterende crème | 10 | 0 | 0 | 9 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Pureoil | NIVEA Soft Hydraterende Crème 200 ml | 0 | 0 | 0 | — |
| Kumi | NIVEA Soft Hydraterende Crème 200 ml | 0 | 0 | 0 | — |
| Naissance | NIVEA Soft Hydraterende Crème 200 ml | 0 | 0 | 0 | — |
| Aytira | NIVEA Soft Hydraterende Crème 200 ml | 0 | 0 | 0 | — |
| Veloura Beauty US | NIVEA Soft Hydraterende Crème 200 ml | 0 | 0 | 0 | — |
| Cocunat | nivea soft moisturiser | 10 | 0 | 0 | 10 producttype, merk of model komt niet overeen |
| Aurgan | NIVEA Soft Hydraterende Crème 200 ml | 0 | 0 | 0 | — |
| Syncee | nivea soft moisturizing cream | 59 | 0 | 0 | 57 productlink, categorie of zoekvariant past niet, 2 productspecificaties of levering onbevestigd |
| Pureoil | nivea soft moisturizing cream 200ml | 0 | 0 | 0 | — |
| Naissance | nivea soft moisturizing cream 200ml | 0 | 0 | 0 | — |
| Aytira | nivea soft moisturizing cream 200ml | 0 | 0 | 0 | — |
| Kumi | nivea soft moisturizing cream 200ml | 0 | 0 | 0 | — |
| Veloura Beauty US | nivea soft moisturizing cream 200ml | 3 | 0 | 0 | 3 producttype, merk of model komt niet overeen |
| Pureoil | nivea soft moisturizing cream | 1 | 0 | 0 | 1 producttype, merk of model komt niet overeen |
| Kumi | nivea soft moisturizing cream | 0 | 0 | 0 | — |
| Naissance | nivea soft moisturizing cream | 10 | 0 | 0 | 6 categorie buiten selectie, 4 producttype, merk of model komt niet overeen |
| Veloura Beauty US | nivea soft moisturizing cream | 10 | 0 | 0 | 10 producttype, merk of model komt niet overeen |
| Aytira | nivea soft moisturizing cream | 6 | 0 | 0 | 5 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| Aurgan | nivea soft moisturizing cream 200ml | 0 | 0 | 0 | — |
| McGrocer | NIVEA Soft Hydraterende Crème 200 ml | 10 | 2 | 5 | 3 producttype, merk of model komt niet overeen, variantgegevens: HTTP 429 |
| Pureoil | nivea soft hydraterende crème | 0 | 0 | 0 | — |
| Kumi | nivea soft hydraterende crème | 0 | 0 | 0 | — |
| Veloura Beauty US | nivea soft hydraterende crème | 6 | 0 | 0 | 6 producttype, merk of model komt niet overeen |
| Aytira | nivea soft hydraterende crème | 1 | 0 | 0 | 1 categorie buiten selectie |
| Naissance | nivea soft hydraterende crème | 8 | 0 | 0 | 6 categorie buiten selectie, 2 producttype, merk of model komt niet overeen |
| Pureoil | nivea soft moisturiser | 0 | 0 | 0 | — |
| Aurgan | nivea soft moisturizing cream | 0 | 0 | 0 | — |
| Kumi | nivea soft moisturiser | 0 | 0 | 0 | — |
| Veloura Beauty US | nivea soft moisturiser | 6 | 0 | 0 | 6 producttype, merk of model komt niet overeen |
| Aytira | nivea soft moisturiser | 3 | 0 | 0 | 2 categorie buiten selectie, 1 producttype, merk of model komt niet overeen |
| Naissance | nivea soft moisturiser | 10 | 0 | 0 | 7 categorie buiten selectie, 3 producttype, merk of model komt niet overeen |
| Aurgan | nivea soft hydraterende crème | 0 | 0 | 0 | — |
| Aurgan | nivea soft moisturiser | 0 | 0 | 0 | — |

Voorbeeld van een gematchte bronvermelding — [Nivea Soft Moisturiser Face Body Hands Moisturising Cream 200ml](https://mcgrocer.com/products/nivea-soft-moisturiser-face-body-hands-moisturising-cream-200ml-322817).

Voor dit resultaat was in de proef geen passende leverancier met onderbouwde zakelijke of dropshippingvermelding beschikbaar. De productbron blijft zichtbaar.

## Magnetische powerbank 10.000 mAh met USB-C

**Basisversie**

De bestaande zoekvarianten voor magnetische powerbanks werkten al. De controle op capaciteit en USB-C bleef in gebruik.

| Bron | Zoekterm | Ruwe indexhits of beperking |
|---|---|---|
| www.xtorm.eu | magnetic power bank 10000mAh | 10 |
| nedis-shop.nl | magnetische powerbank | 10 |
| www.androidcentral.com | magnetic power bank | ruwe indexhits niet gemeten |
| eu.baseus.com | magnetic power bank 10000mAh | 10 |
| www.techradar.com | magnetic power bank | ruwe indexhits niet gemeten |
| eu.ugreen.com | magnetic power bank 10000mAh | 10 |
| nedis-shop.nl | magnetic power bank 10000mAh | 10 |
| syncee.com | magnetic power bank 10000mAh | 119 HTML-markeringen |
| www.hama.com | Magnetische powerbank 10000mAh met USB-C | ruwe indexhits niet gemeten |
| hurtel.com | — | ruwe indexhits niet gemeten |
| nedis-shop.nl | MagSafe power bank 10000mAh | 9 |
| www.hama.com | — | ruwe indexhits niet gemeten |
| syncee.com | — | ruwe indexhits niet gemeten |
| syncee.com | — | ruwe indexhits niet gemeten |
| 9to5mac.com | — | ruwe indexhits niet gemeten |
| ec.europa.eu | — | ruwe indexhits niet gemeten |
| ec.europa.eu | — | ruwe indexhits niet gemeten |
| ec.europa.eu | — | ruwe indexhits niet gemeten |
| ec.europa.eu | — | ruwe indexhits niet gemeten |
| ec.europa.eu | — | ruwe indexhits niet gemeten |

**Nieuwe versie**

Bronnen in de zoekopdracht — 9to5Mac, Android Central, Baseus, Hama, Hurtel, Nedis, Syncee, TechRadar, UGREEN, Xtorm.

| Bron | Geprobeerd | Ruw | Bevestigd | Vergelijkbaar | Gefilterd of beperkt |
|---|---|---:|---:|---:|---|
| Xtorm | magnetic power bank 10000mAh | 10 | 3 | 0 | 7 producttype, merk of model komt niet overeen |
| Nedis | magnetische powerbank | 10 | 0 | 0 | 7 producttype, merk of model komt niet overeen, 3 categorie buiten selectie |
| UGREEN | magnetic power bank 10000mAh | 10 | 3 | 0 | 7 producttype, merk of model komt niet overeen |
| Baseus | magnetic power bank 10000mAh | 10 | 5 | 0 | 5 producttype, merk of model komt niet overeen |
| Nedis | magnetic power bank 10000mAh | 10 | 0 | 0 | 9 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Syncee | magnetic power bank 10000mAh | 59 | 0 | 0 | 42 productlink, categorie of zoekvariant past niet, 15 controlelimiet per leverancier of bron, 2 productspecificaties of levering onbevestigd |
| Nedis | MagSafe power bank 10000mAh | 9 | 0 | 0 | 8 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Nedis | Qi2 magnetic charger | 10 | 0 | 0 | 9 producttype, merk of model komt niet overeen, 1 categorie buiten selectie |
| Syncee | MagSafe power bank 10000mAh | 59 | 1 | 0 | 58 productlink, categorie of zoekvariant past niet |

Voorbeeld van een gematchte bronvermelding — [UGREEN MagFlow Pro Magnetic Power Bank (10000mAh, Qi2 25W, 45W Built-in USB-C Cable)](https://eu.ugreen.com/products/magflow-pro-magnetic-power-bank-10000mah-qi2-25w).

Leverancierskaarten — UGREEN (buiten EU), Baseus (buiten EU), Xtorm (binnen EU), Hama B.V. (binnen EU), Hurtel (binnen EU), emegabox (vestigingsland onbevestigd).

## Beperkingen van de proef

- De uitbreiding gebruikt een Nederlandstalige en Engelstalige productwoordenschat en controleerbare zoekregels. De versie bevat geen extern taalmodel of algemene webzoek-API. Het bereik hangt af van de aangesloten openbare productcatalogi.
- De zoekindexen leverden per product een controleerbare productlink. Een aparte follow-up op acht voorbeeldlinks leverde één HTTP 200, zes HTTP 429 en één HTTP 403 op vanuit deze omgeving. De telresultaten komen uit de catalogusantwoorden. De status van rechtstreeks openen kan per moment verschillen.
- De browserproef controleerde beide schermformaten, het zoekformulier, productkaarten, de vier tabbladen en bronvermelding. De beheerzoekbalk was afwezig en er stond één inkoopprijsveld.
- De basisversie slaagde eerder voor de migratietest op Linux. De bestaande Windows-ACL-fout trad in deze lokale sessie opnieuw op. De PostgreSQL-regressies vereisen een lokale testserver.
- De ondersteunde openbare interfaces zijn gedocumenteerd door [Shopify Predictive Search](https://shopify.dev/docs/api/ajax/reference/predictive-search), de [Shopify Product API](https://shopify.dev/docs/api/ajax/reference/product) en de [WooCommerce Store API](https://developer.woocommerce.com/docs/apis/store-api/resources-endpoints/products/).
