# NUVEMIXA — VOLLEDIGE KWALITEITSAUDIT EN VERBETERPLAN

Datum: 23 november 2026 (Europe/Amsterdam). Status: uitsluitend audit; geen reparaties of commerciële vrijgave.

Onderzochte bronmap: `C:\Users\user\NUVEMIXA-WERKKOPIE`. Vergeleken met `C:\Users\user\NUVEMIXA-LOKALE-TEST`. Functionele mutaties uitsluitend in een aparte kopie met fictieve data onder de Codex-werkmap; browser op `127.0.0.1:5001`, niet op de gebruikerssessie van poort 5000. Externe mail-, betaal-, Woo- en AI-aanroepen geblokkeerd. Alwaysdata, Render, Neon, Vercel en GitHub zijn niet gewijzigd of verbonden voor operationele tests.

## A. Samenvatting

**NUVEMIXA is een verzorgde lokale testwebshop, maar nog niet klaar om echte bestellingen en betalingen te accepteren.** De belangrijkste blokkades zijn de onvoltooide bestel-/betaalketen, voorlopige productdata, niet-definitieve totaalkosten en ontbrekende operationele bedrijfs-/retourinrichting. Dat de meeste pagina’s renderen is waardevol, maar bewijst geen werkende verkooporganisatie. Accounts zijn basaal bruikbaar; wachtwoordherstel, verificatie, orderhistorie en accountgebonden favorieten zijn niet compleet. Inloggen wist bovendien het mandje.

De recent goedgekeurde desktophero’s zijn behouden en onafhankelijk nagelopen: overal 400 px hoogte en de beschikbare hoofdvlakbreedte, zonder lege zijstrook **binnen** de hero. De template heeft op een breed 1920-scherm nog buitenmarges door een hoofdvlak van maximaal 1460 px. Dit is apart te onderscheiden van de eerdere lege plekken ín de hero. Mobiel is uitsluitend onderzocht en niet aangepast.

| Onderzoek | Resultaat |
| --- | --- |
| Bronbestanden vooraf gehasht | 179 werk / 252 test (zonder git/venv/cache) |
| Runtime routekaart | 52 routeregels inclusief static, aliases en dynamische routes |
| HTTP-crawl | 143 URL’s: 127×200, 12 redirects, 1×503 (niet ingestelde adminlogin), 3×404 (bewuste negatieve/ontbrekende routes) |
| Lokale links/assets | 257 unieke URL’s: geen 4xx/5xx in de gecontroleerde set; adminacties en externe bestemmingen niet doorgelopen |
| Catalogus | 100 producten: vijf actieve categorieën met ieder 20; alle voorraadstatussen onbekend |
| Bestaande pytesttests | 42 uitgevoerd: 34 geslaagd, 8 mislukt |
| Extra checks | 19 aanvullende checks: 18 geslaagd, 1 bevinding (accountcache) |
| Browserheroes | 144 waarnemingen: 8 pagina’s × 9 breedtes × NL/EN |
| Overige browsers | 43 waarnemingen over 15 paginatypen, deels op 390/768/1366; checkout apart met testmandje |
| Bronintegriteit | Broncode, data en assets ongewijzigd; één bestaand runtimelog is aangevuld (zie integriteitsbijlage). |
| Productiezekerheid | Geen productieperformance-, TLS-, mailbezorg-, betaal- of disaster-recoveryvrijgave |

Lees P0 als blokkade vóór commerciële opening, P1 als noodzakelijk voor betrouwbaarheid, P2 als belangrijke kwaliteit en P3 als verfijning. Dit zijn geen CVSS-scores. “Niet aanwezig” betekent niet automatisch een foutieve bestaande route; bijvoorbeeld /afrekenen is de bedoelde checkout en het ontbreken van de Engelse alias /checkout is op zichzelf geen bug. Juridische conclusies zijn aandachtspunten: **juridische controle vereist**.

## B. Wat al goed is

- Consistente vijf categorieën, 100 unieke producten en functionerende productdetail-URL’s; alle 100 details renderen in de crawl.
- Goede visuele basis en herkenbare NUVEMIXA-merknaam op onderzochte actieve schermen; gedeelde header/footer en werkende NL/EN-keuze.
- Desktophero’s sluiten aan op de laatst afgesproken uitvoering; geen aangetroffen horizontale pagina-overflow of kapotte `<img>` in de browsermetingen.
- Geen verzonnen actieprijzen op Aanbiedingen: de pagina meldt dat er nog geen gecontroleerde deals zijn.
- Wachtwoorden met scrypt, parameterized SQL, minimale wachtwoordlengte en dubbele e-mailblokkade. Loginlimiet grijpt aantoonbaar in.
- CSRF en vreemde Origin worden tegengehouden. Cartcookie bevat alleen product-ID en aantal; prijs komt opnieuw uit de servercatalogus. Checkout-PII wordt niet in die leesbare cookie bewaard.
- Privé/cart/adminroutes hebben grotendeels no-store; nosniff, framebescherming, Referrer-/Permissions-Policy aanwezig bij de onderzochte importstart. Debug staat uit.
- Adminroutes verwijzen anoniem naar login; bij ontbrekende configuratie wordt niet stilzwijgend een open dashboard aangeboden.
- Reviews vereisen consent en moderatie; negatieve beoordelingen zijn mogelijk, pending is niet publiek en gepubliceerde HTML wordt ge-escaped.
- SSO heeft HMAC, korte geldigheid en eenmalige nonces; replay wordt geblokkeerd. De te brede scope blijft wel NV07.
- Merchant-feedpreview publiceert geen ongeverifieerde producten; CSVcontrole schrijft geen voorraad/producten weg. Molliecheck is bewust alleen-lezen.
- Juridische teksten bespreken al bedenktijd, garantie, terugbetaling en de ontbindingsfunctie. Behoud deze basis en vul feitelijke operationele gegevens aan.

## C. Kritieke fouten

### NV01 — P0 — Commerciële bestel- en betaalstraat ontbreekt

**Locatie:** app.py:281–330, 1130–1175; nuvemixa_integrations.py:mollie_readonly_check

**Wat misgaat:** Checkout levert in testmodus alleen order-id TEST op. De optionele Woo-tak maakt een onbetaalde order; een Mollie-controle verifieert alleen een sleutel. Geen complete betaalredirect, gevalideerde webhook, betaalstatusmachine of idempotente orderafhandeling aangetroffen.

**Bewijs:** Geïsoleerde checkout geeft 200 met testbevestiging. Alle 100 producten missen woocommerce_product_id. De functie create_woo_order weigert ontbrekende mapping. Geen echte API-aanvraag uitgevoerd.

**Klantimpact:** Er kan nog geen betrouwbare aankoop worden afgerond. Alleen de live-vlag aanzetten maakt dit geen verkoopklare shop.

**Aanbevolen oplossing:** Ontwerp één orderbron, koppel gevalideerde producten en voorraad, voeg provider-testmodus, idempotentie, betaling/cancel/timeout/webhook en reconciliatie toe; pas daarna gecontroleerde commerciële vrijgave.

**Wijzigingsrisico:** Hoog: order-, betaal- en klantdata; terugvalplan en expliciete release nodig.

**Complexiteit:** Groot

**Latere verificatie:** Provider-sandbox: betaald/geannuleerd/mislukt/verlopen, dubbele webhook/dubbele klik, voorraadconcurrentie en terugbetaling; geen tweede order of afschrijving.

### NV02 — P0 — Catalogus is een voorlopige demonstratie

**Locatie:** app.py:64–172; products/*/products.json; content/product-names-en.json

**Wat misgaat:** Voor alle 100 producten ontbreken merk, gekoppeld Woo-product, bevestigde voorraad en leveranciersverificatie. Beschrijvingen zijn generiek; varianten, definitieve specificaties en aantoonbaar correcte productfoto’s ontbreken.

**Bewijs:** catalog-enriched.json: 100 producten, vijf maal 20; stock_status overal unknown, specificaties van het onderzochte product leeg. Productafbeeldingen gebruiken gegenereerde /img/product/...svg illustraties.

**Klantimpact:** Klanten kunnen eigenschappen, levertijd en echte beschikbaarheid niet beoordelen. Sfeerbeelden zijn geen bewijs dat een artikel wordt geleverd.

**Aanbevolen oplossing:** Per SKU leverancier, prijs/btw, voorraad, merk/model, varianten, foto-/merkrechten, levertermijn, veiligheid en EU-productinformatie verifiëren; alleen gecontroleerde SKU’s verkoopbaar maken.

**Wijzigingsrisico:** Hoog voor catalogusmapping en bestaande URL’s.

**Complexiteit:** Groot

**Latere verificatie:** Steekproef én complete publicatiecheck op alle verkoopbare SKU’s; variantselectie, totaalprijs en voorraad moeten dezelfde bron gebruiken.

### NV03 — P0 — Totale verkoopprijs en rechtsgeldige bestelstap zijn niet gereed

**Locatie:** templates/checkout.html:24–36; app.py:1130–1175; content/information/bestellen.json en voorwaarden.json:1

**Wat misgaat:** Verzending staat op “Wordt later bepaald”, de btw-uitsplitsing en definitieve betaal-/levercondities ontbreken. De knop “Bestelling plaatsen” moet bij een toekomstige betaalplicht ondubbelzinnig worden beoordeeld.

**Bewijs:** Browsercheckout toont producttotaal €24,95, verzending later en hetzelfde totaal. Testflow vraagt al volledige adresgegevens.

**Klantimpact:** Een klant kan vóór een echte overeenkomst geen volledige financiële verplichting overzien. Juridische controle vereist.

**Aanbevolen oplossing:** Bereken bevestigde verzending en belastingen vóór definitieve bevestiging; toon duidelijke betaalplicht, verkoper en voorwaarden. Houd testdata-invoer herkenbaar en beperk onnodige persoonsgegevens.

**Wijzigingsrisico:** Hoog: berekeningen en contractsluiting.

**Complexiteit:** Groot

**Latere verificatie:** NL/EN en elk bezorgland: prijs inclusief toepasselijke btw, alle verplichte kosten, geen onverwachte toeslagen; juridische eindcontrole van de knop en bevestiging.

### NV04 — P0 — Bedrijfsidentiteit en operationele consumentenprocessen ontbreken

**Locatie:** content/information/{voorwaarden,bestellen,retouren,over-trendmix}.json:1; templates/_footer.html

**Wat misgaat:** De teksten beschrijven toekomstige publicatie van bedrijfsgegevens, retouradres en processen. Een operationele herroepingsfunctie en het definitieve modelformulier zijn niet aangetroffen.

**Bewijs:** Retourtekst belooft de online ontbindingsfunctie vóór echte bestellingen. Route-inventaris heeft geen retour-/herroepingsindiening of bevestigingsafhandeling.

**Klantimpact:** Geen complete aanspreekbare verkoper of uitvoerbaar retourproces voor een echte klant. Juridische controle vereist.

**Aanbevolen oplossing:** Vul werkelijke handelsnaam, vestigings-/contactgegevens, registraties en toepasselijke btw-informatie aan; regel klachten, garantie, retouradres, formulier, herroepingsfunctie en duurzame ontvangstbevestiging.

**Wijzigingsrisico:** Middel technisch, hoog juridisch/commercieel.

**Complexiteit:** Groot

**Latere verificatie:** Alle informatie zichtbaar vóór koop; gast en account kunnen binnen de termijn herroepen; bewijs van tijdige melding en ontvangstbevestiging. Laat de definitieve stukken beoordelen.

## D. Belangrijke verbeteringen

Onderstaande dossiers bevatten per punt locatie, feit, bewijs, klantimpact, oplossing, wijzigingsrisico, complexiteit en hertest. Dezelfde ID’s komen terug in de vakspecifieke secties en het geordende plan; daar worden ze niet als nieuwe extra fouten geteld.

### NV05 — P1 — Inloggen en registreren wissen winkelwagen en favorieten

**Locatie:** app.py:449–494; session.clear()

**Wat misgaat:** Bij registratie, succesvolle login en logout wordt de hele sessie geleegd. Winkelwagen en wishlist zitten in diezelfde sessie.

**Bewijs:** Geïsoleerde test “cart survives customer login” faalt: gevuld mandje verdwijnt na succesvolle login.

**Klantimpact:** Een klant verliest de selectie vlak voor afrekenen; verhoogt uitval.

**Aanbevolen oplossing:** Roteer authenticatiestatus met een expliciet beleid voor behoud/merge van veilige cart- en wishlist-ID’s; bepaal apart gewenst gedrag bij logout.

**Wijzigingsrisico:** Middel: geen oude privilegevelden behouden.

**Complexiteit:** Middel

**Latere verificatie:** Mandje en favorieten vóór login/registratie behouden; andere gebruiker ziet geen persoonsgegevens; adminstatus en CSRF worden veilig vernieuwd.

### NV06 — P1 — Accountlevenscyclus en orderkoppeling onvolledig

**Locatie:** app.py:425–494, 311–330; templates/account.html

**Wat misgaat:** Alleen naam, e-mail, wachtwoordhash en aanmaaktijd worden bewaard. Wachtwoordherstel, e-mailverificatie, adresbeheer en orderhistorie ontbreken; Woo-payload bevat geen customer_id-koppeling.

**Bewijs:** Reset-/verify-/account-ordersroutes geven 404; schema en routekaart bevestigen ontbrekende flows. Gewone registratie en login werken met fictieve data.

**Klantimpact:** Vergeten wachtwoord blokkeert toegang; eigenaar van het e-mailadres is niet bevestigd; bestellingen zijn niet aantoonbaar aan het juiste account gekoppeld.

**Aanbevolen oplossing:** Voeg eenmalige, kort geldige en gehashte herstel-/verificatietokens toe, bind orders aan een stabiele klant-ID en controleer objectrechten. Verifieer e-mail vóór persoonlijke kortingscodes.

**Wijzigingsrisico:** Hoog: identiteit en gegevensisolatie.

**Complexiteit:** Groot

**Latere verificatie:** Verlopen/hergebruikte tokens afgewezen; account A kan order B niet openen; gastbestelling alleen na eigendomsbewijs koppelen; geen accountenumeratie.

### NV07 — P1 — Review-SSO geeft algemene beheerstatus

**Locatie:** nv_reviews_sso.py:registreer_ontvanger; app.py:540–545, 1405–1436

**Wat misgaat:** Een geldige reviewlink zet nv_admin=True. Die vlag wordt ook gebruikt voor andere beheerpagina’s; de link is dus niet op reviewbeheer begrensd als adminconfiguratie aanwezig is.

**Bewijs:** Met uitsluitend synthetische sleutel en adminhash: SSO geldig, replay 403; daarna /control 200. Dit bewijst het autorisatiemodel, geen productie-inbraak.

**Klantimpact:** Een bevoegdheid voor reviewmoderatie kan bredere beheertoegang geven dan bedoeld. URL-token kan bovendien in geschiedenis/logs terechtkomen.

**Aanbevolen oplossing:** Gebruik aparte reviewrol/scopes, audience-binding en gecontroleerde dashboardtoegang; redigeer tokens uit logs. Behoud HMAC, korte TTL, eenmalige nonce en no-referrer.

**Wijzigingsrisico:** Hoog: legitieme beheerlogin kan worden geraakt.

**Complexiteit:** Middel

**Latere verificatie:** Reviewrol kan alleen bedoelde reviewhandelingen uitvoeren; normale beheerder blijft werken; verlopen, gemanipuleerde, herhaalde en verkeerde-audience-token geweigerd.

### NV08 — P1 — Afhankelijkheden vallen binnen actuele beveiligingsmeldingen

**Locatie:** requirements.txt:1–2; lokaal Flask 3.1.2, Werkzeug 3.1.8, Gunicorn 23.0.0

**Wat misgaat:** Flask 3.1.2 valt onder GHSA-68rp-wp8r-4726 (<3.1.3, cache/Vary). Werkzeug 3.1.8 valt onder GHSA-g6x2-hccm-hh4m (<3.1.9, Windows/NTFS device-namen). De transitieve versie is niet vastgelegd.

**Bewijs:** Versies lokaal gelezen; primaire Pallets-advisories gecontroleerd op 23-11-2026. Geen schadelijke device-URL of belastingtest uitgevoerd.

**Klantimpact:** Potentieel cachelek onder specifieke proxy/sessievoorwaarden; op Windows kan betreffende bestandspadbehandeling requests laten hangen. Linuxproductie is hiermee niet als kwetsbaar bewezen.

**Aanbevolen oplossing:** Kies ondersteunde gepatchte versies, leg transitieve afhankelijkheden reproduceerbaar vast en voer een dependency-audit uit op de daadwerkelijke productieomgeving.

**Wijzigingsrisico:** Middel: framework-/cookie-/routingregressie.

**Complexiteit:** Klein tot middel

**Latere verificatie:** Pakketlijst/advisory-scan, volledige regressiesuite en cache-/sessietests; exploitvoorwaarden per hostingplatform beoordelen.

### NV09 — P1 — Accountpagina mist expliciete private caching

**Locatie:** app.py:1354–1375; /account

**Wat misgaat:** De no-store-lijst bevat de accountpagina niet. Dat is ongewenst voor een scherm dat na login persoonlijke informatie toont.

**Bewijs:** extra-checks: /account 200, Cache-Control ontbreekt, Vary: Cookie aanwezig. Dit is een hardeningbevinding; er is geen gedeeld-cachelek aangetoond.

**Klantimpact:** Afhankelijk van browser/proxy kan persoonlijke inhoud onnodig worden bewaard.

**Aanbevolen oplossing:** Zet voor account en alle gepersonaliseerde schermen expliciet private/no-store en bewaak Vary. Verifieer ook de echte hostingcache.

**Wijzigingsrisico:** Laag.

**Complexiteit:** Klein

**Latere verificatie:** Ingelogd/uitgelogd, backknop en twee verschillende clients achter cache; geen privé-inhoud van een ander of na logout.

### NV10 — P1 — Adresvalidatie wijkt af van EU-bezorgbelofte

**Locatie:** app.py:1139–1160; templates/checkout.html:29–36

**Wat misgaat:** Land is vrije tekst die alleen uppercase krijgt; postcode en adres hoeven alleen niet leeg te zijn. Er is geen serverallowlist voor bezorglanden of landafhankelijk adresformaat.

**Bewijs:** Geïsoleerde POST met niet-EU/ongeldige postcode geeft 200 en succesvolle testbevestiging, terwijl UI alleen EU-levering belooft.

**Klantimpact:** Later onbezorgbare orders, verkeerde verzending/btw en klantteleurstelling.

**Aanbevolen oplossing:** Gebruik stabiele ISO-landcodes, toegestane leverlanden, lengtebegrenzing en landafhankelijke adresvalidatie; foutmelding behoudt veilige ingevulde waarden.

**Wijzigingsrisico:** Middel: internationale adressen niet onterecht afwijzen.

**Complexiteit:** Middel

**Latere verificatie:** NL/BE en overige ondersteunde landen, ontbrekend/huisnummer-/unicodeadres, ongeldige landen en extreme lengtes serverzijdig testen.

### NV11 — P1 — E-mailketen is geen bevestigde klantcommunicatie

**Locatie:** app.py:1194–1288, 1158–1169; trendmix_assistant.py:general_answer

**Wat misgaat:** Registratie verstuurt geen verificatie/welkomstmail; checkout bevat hoogstens een beheerbericht. Klantorderbevestiging en templates ontbreken. Contact werkt alleen bij juiste SMTP/Resendconfiguratie; de assistent stelt onafhankelijk van de configuratie dat mail niet is gekoppeld.

**Bewijs:** Zonder credentials geeft contact eerlijk 503; er is niets verzonden. Fallback-afzender/contact is een Gmail-adres. De daadwerkelijke bezorgbaarheid/DNS zijn niet getest.

**Klantimpact:** Klant mist betrouwbare bevestiging en hulp; helptekst kan na latere koppeling onjuist zijn.

**Aanbevolen oplossing:** Maak NL/EN transactionele templates, merkafzender, queue/retry en afleverlogging; stem supportstatus op echte configuratie af. Controleer SPF/DKIM/DMARC en afmelding voor marketing.

**Wijzigingsrisico:** Hoog: onbedoelde externe mail voorkomen.

**Complexiteit:** Groot

**Latere verificatie:** Mail-sink eerst: registratie, herstel, order, herroeping en foutpad; pas apart geautoriseerde afleverproef en DNS-check op echte domein.

### NV12 — P1 — Registratie-, contact- en loginmisbruik onvoldoende centraal beheerst

**Locatie:** app.py:426, 449–489, 548–574, 1225; trendmix_assistant.py:register_trendmix_assistant

**Wat misgaat:** Loginlimieten staan per proces/IP in geheugen; registratie en contact hebben geen aantoonbare centrale throttle. Assistentlimiet is gekoppeld aan de ondertekende clientcookie en kan met een nieuwe sessie opnieuw beginnen.

**Bewijs:** Klantlogin: acht keer 401, negende 429; assistent: twaalf keer 200, dertiende 429 per cookie. Geen productiebelasting uitgevoerd.

**Klantimpact:** Accountspam, mailmisbruik, gedeelde-IPblokkades en kostenrisico bij ingeschakelde AI.

**Aanbevolen oplossing:** Voeg begrensde centrale limieten op geschikte combinaties van account/IP/sessie toe, met vertrouwde proxyconfiguratie, monitoring en geleidelijke blokkade. Houd foutmeldingen neutraal.

**Wijzigingsrisico:** Middel: echte klanten achter gedeeld netwerk niet blokkeren.

**Complexiteit:** Middel

**Latere verificatie:** Meerdere workers, nieuwe cookie, gedeelde IP, herstart en korte piek; limieten blijven consistent zonder legitiem herstel te verhinderen.

### NV13 — P1 — Reviewverificatie en toekomstige beloning hebben geen aankoopbewijs

**Locatie:** nv_reviews.py; app.py:1385–1436; templates/_reviews.html

**Wat misgaat:** Iedere bezoeker kan een review indienen. “verified” kan door beheer worden gezet zonder technisch orderbewijs. Positieve en negatieve reviews zijn beide mogelijk, maar beloningsregistratie en transparante incentivevermelding ontbreken.

**Bewijs:** Correcte review-POST 303 bedankt, negatieve 1-ster-review blijft wachtend. Publicatie en escaping getest; verified is een losse adminboolean.

**Klantimpact:** Label “geverifieerd” en kortingsactie kunnen meer zekerheid suggereren dan het systeem onderbouwt. Juridische controle vereist.

**Aanbevolen oplossing:** Koppel uitnodiging aan echte afgeronde aankoop met eenmalig token; beloon onafhankelijk van score of publicatiekeuze; vermeld incentive en moderatieregels; voorkom dubbele beloning.

**Wijzigingsrisico:** Middel tot hoog: reviewdata en vertrouwen.

**Complexiteit:** Groot

**Latere verificatie:** 1- en 5-sterren krijgen dezelfde beloning; alleen geldige aankoop; replay/concurrentie afgewezen; controleer openbare toelichting en persoonsgegevens.

### NV14 — P1 — Sessiesleutel en opslag vereisen een bewezen productieconfiguratie

**Locatie:** app.py:16–23, 425; nv_reviews.py:16–18; nuvemixa_admin_store.py:14–25; nv_reviews_sso.py:20

**Wat misgaat:** Zonder vaste SECRET_KEY wordt per proces een nieuwe sleutel gemaakt. Klantdatabase staat onder de bronmap; reviewpad is standaard Linux-specifiek. Back-up, herstel, rechten en retentie zijn lokaal niet operationeel bewezen.

**Bewijs:** Werk-/testcode gelijk, maar werkmap bevat klant- en SSO-database plus sleutelbestand; geen inhoud uit echte klanttabellen gelezen. Een Windowsomgeving zonder review-envpad kan de defaultdirectory niet gebruiken.

**Klantimpact:** Uitloggen na restart/meerdere workers, verlies of onnodige verspreiding van persoonsgegevens en opslagfouten.

**Aanbevolen oplossing:** Beheer vaste secrets buiten broncode; configureer persistente afgeschermde opslag, migraties, beperkte rechten en geteste back-up/herstel/retentie. SQLite kan passend zijn bij beperkte schaal, na operationele toets.

**Wijzigingsrisico:** Hoog: verkeerde pad-/sleutelwijziging verbreekt toegang.

**Complexiteit:** Middel

**Latere verificatie:** Restart/multiworkerlogin, restore naar aparte omgeving, toegangsrechten en foutmelding bij ontbrekende opslag; nooit liveklantdata in test kopiëren.

### NV15 — P1 — Publiek bereikbaar ondoorzichtig binair bestand

**Locatie:** static/nvx-7a7e6c734b67c602e78fabce.bin

**Wat misgaat:** Een bestand van 5.203.456 bytes staat in de publieke staticmap zonder aangetroffen template/CSS/JS-verwijzing. De header begint met Salted__, passend bij een versleutelde container; inhoud en doel zijn onbekend.

**Bewijs:** Alleen formaat/omvang en verwijzingen onderzocht; geen ontsleuteling of uitvoering. Flask heeft een publieke /static/<path:filename>-route.

**Klantimpact:** Onbedoelde publicatie of distributie van onbekende inhoud; dit is geen bewijs van malware of datalek.

**Aanbevolen oplossing:** Laat de eigenaar doel en herkomst vaststellen. Als het geen publiek webasset is, plaats het bij een latere goedgekeurde wijziging buiten de webroot en controleer deploymentselectie.

**Wijzigingsrisico:** Middel: onbekende afhankelijkheid.

**Complexiteit:** Klein voor onderzoek, vervolg afhankelijk van inhoud

**Latere verificatie:** Documenteer eigenaar/doel en publicatiebesluit; controleer dat alleen bedoelde publieke bestanden bereikbaar zijn. Niets automatisch verwijderen.

### NV16 — P1 — Privacytekst en feitelijke verwerking moeten worden afgestemd

**Locatie:** content/information/privacy.json:1, cookies.json:1; app.py:425–432; nv_reviews.py; trendmix_assistant.py

**Wat misgaat:** De uitleg is grotendeels toekomstgericht, terwijl accounts, reviews en chat al invoer aannemen. Definitieve verantwoordelijke, bewaartermijnen, ontvangers/verwerkers, rechtenprocedure en doorgiften moeten op de echte configuratie aansluiten.

**Bewijs:** Accounts slaan naam/e-mail/hash op; reviews naam/e-mail/tekst/clienthash; optionele AI kan vraaginhoud naar een provider sturen. Geen productiecontracten/DPA’s of trackinginventaris beschikbaar.

**Klantimpact:** Gebruikers kunnen onvoldoende worden geïnformeerd over de actuele verwerking. Juridische controle vereist.

**Aanbevolen oplossing:** Maak een gegevensstroomregister en actuele AVG-informatie per doel/grondslag/termijn; scheid marketingtoestemming. Voor functionele opslag is niet automatisch een cookiebanner nodig; inventariseer tracking vóór consentontwerp.

**Wijzigingsrisico:** Middel juridisch en technisch.

**Complexiteit:** Middel

**Latere verificatie:** Privacytoelichting vóór invoer; inzage/verwijdering en uitzonderingen uitvoerbaar; geen tracking vóór noodzakelijke toestemming, intrekken even gemakkelijk.

### NV17 — P2 — Canonical-, sitemap- en taalstrategie inconsistent

**Locatie:** app.py:1336–1350; templates/base.html, category.html, index.html, product.html; content/information/over-trendmix.json

**Wat misgaat:** Crawl bevat acht canonicals op Alwaysdata en 115 op requesthost localhost. Sitemap bevat de oude over-trendmix-URL die 301 doorstuurt; shop/deals ontbreken in de expliciete sitemapbasis. Taalwissel gebeurt vooral clientzijdig op dezelfde URL.

**Bewijs:** page-crawl.json en broncode: productcanonical gebruikt request.url_root, andere templates hardcoded domein. NL/EN zijn geen apart aangetoonde crawlbare hreflangpagina’s.

**Klantimpact:** Zoekmachines kunnen staging/oud domein of dubbele/omgeleide URL’s ontvangen; Engelse vindbaarheid blijft beperkt.

**Aanbevolen oplossing:** Gebruik één geverifieerde SITE_URL-bron, canonicale 200-URL’s in sitemap, bewuste indexstrategie voor zoekresultaten/privépagina’s en een gekozen serverzijdige taal-/hreflangstrategie.

**Wijzigingsrisico:** Middel tot hoog voor bestaande SEO.

**Complexiteit:** Middel

**Latere verificatie:** Crawl staging én later productie: sitemap naar 200, consistente host, correcte canonical/OG/hreflang, geen localhost in publiek document; staging afschermen.

### NV18 — P2 — Engels is niet volledig en metadata wisselt niet overal mee

**Locatie:** templates/account.html; templates/shop.html; static/app.js, languages.js, nv-polish-20261122.js

**Wat misgaat:** In Engels blijven onder meer “Herhaal wachtwoord”, zoekresultatenkop en geen-resultaattekst Nederlands. Accounttitel blijft “Mijn account | NUVEMIXA” terwijl de inhoud Engels is.

**Bewijs:** Browser: Engelse selector actief; registratieherhaling Nederlands; /shop?q=lamp geeft 8 producten maar Nederlandse kop; geen-resultaatflow toont Nederlandse uitleg.

**Klantimpact:** Onrustige internationale ervaring en inconsistente toegankelijkheids-/SEOtaal.

**Aanbevolen oplossing:** Maak één gecontroleerde NL/EN-bron voor zichtbare tekst, foutmeldingen, aria-labels, titels, meta en transactional mail; beperk gestapelde vertalers.

**Wijzigingsrisico:** Middel: scripts overschrijven nu gedeelde teksten.

**Complexiteit:** Middel

**Latere verificatie:** Volledige klantreis en foutpaden in beide talen, direct laden en herladen met opgeslagen voorkeur; geen gemengde taal.

### NV19 — P2 — Mobiele hero-informatie zit vooral in een afbeelding

**Locatie:** static/nv-hero-2026.css:6–50; templates/_nv_desktop_hero.html

**Wat misgaat:** Onder 992 px is de volledige bannerillustratie zichtbaar en desktop-HTMLcopy verborgen. Ingebakken koppen/knoptekst worden op smalle schermen klein en zijn niet als echte tekst aanpasbaar.

**Bewijs:** 320–844 px: 5:2-frame zonder overflow. AX toont een generieke linknaam naar de collectie, niet alle afgebeelde copy. Dit is de huidige door gebruiker behouden mobiele uitvoering.

**Klantimpact:** Beperkt leesbaar bij kleine breedte, tekstzoom of gebruik met screenreader.

**Aanbevolen oplossing:** Alleen na aparte afstemming over mobiel: toets noodzakelijke tekstalternatieven en overweeg echte mobiele tekst. Nu geen mobiele aanpassing uitvoeren.

**Wijzigingsrisico:** Hoog visueel: gebruiker wil huidige mobiele resultaat behouden.

**Complexiteit:** Middel

**Latere verificatie:** Vergelijk goedgekeurde screenshots; 200% tekstzoom, screenreader en 320 px; geen clipping of verdwenen CTA. Onderbouw WCAG-uitzonderingen waar van toepassing.

### NV20 — P2 — Menu sluit in gemeten mobiele flow niet met Escape

**Locatie:** templates/_header.html; static/trendmix-ui-2026.js en headeraanpassingen in gedeelde partials

**Wat misgaat:** De categorieknop opent en kondigt expanded aan, maar Escape liet het menu in de uitgevoerde flow open.

**Bewijs:** 390 px, Engelse Smart Home-pagina: AX click opent categorieën; daarna Escape geeft geen boomwijziging en focus blijft op expanded knop.

**Klantimpact:** Minder voorspelbare toetsenbordbediening; een formele WCAG-overtreding is hiermee niet afzonderlijk vastgesteld.

**Aanbevolen oplossing:** Bepaal het bedoelde disclosure-/drawermodel; sluit logisch met Escape en stuur focus veilig terug. Test focusvolgorde en achtergrondinteractie.

**Wijzigingsrisico:** Middel: meerdere menuscripts kunnen tegelijk reageren.

**Complexiteit:** Klein tot middel

**Latere verificatie:** Tab/Shift+Tab, Enter/Space, Escape en buitenklik op mobiel/desktop; aria-expanded en zichtbaarheid blijven synchroon.

### NV21 — P2 — Kleine actietekst en contrast vragen gerichte toegankelijkheidscontrole

**Locatie:** templates/checkout.html; static/ux.css en overige commerce-overrides

**Wat misgaat:** De desktopcheckoutknop wordt in de gemeten stijl als 10 px/900 weergegeven. HeroCTA’s en gekleurde actieknoppen vragen een volledige contrast-/zoom-/targetcontrole; geen volledige WCAG-certificering uitgevoerd.

**Bewijs:** DOM-stijl knop: wit op rgb(8,102,245), 10 px. Geen ongeëtiketteerde zichtbare inputs of paginabrede overflow in 43 overige-pagewaarnemingen.

**Klantimpact:** Leesbaarheid en aanraakbediening kunnen vooral voor slechtziende klanten minder goed zijn.

**Aanbevolen oplossing:** Maak actiehiërarchie en lettergroottes consistent, bereken contrastratio per echte achtergrondtoestand en toets targetafmetingen met de WCAG-uitzonderingen. Toets wettelijke toepasselijkheid apart.

**Wijzigingsrisico:** Laag tot middel visueel.

**Complexiteit:** Middel

**Latere verificatie:** WCAG-audit met toetsenbord/screenreader, contrast, 200%/400% zoom en focus; 24×24 is de 2.2-minimumrichtlijn met uitzonderingen, niet automatisch 44×44 vereist.

### NV22 — P2 — Zware hero-preload en veel gestapelde assets

**Locatie:** templates/shop.html:20; static/images/hero/*.png; gedeelde templates en CSS/JS

**Wat misgaat:** Shop prelaadt de originele PNG van circa 1,96 MB ook wanneer de desktopfoto in CSS de zichtbare hero vormt. Veel afzonderlijke CSS-/JS- en inline-overrides vergroten onderhoud en kunnen onnodige downloads/renderwerk veroorzaken.

**Bewijs:** Assetinventaris en browserassetlijst. Heroafbeeldingen zijn vaak 1–2 MB; lokale responstijden zijn geen mobiele internetsnelheid.

**Klantimpact:** Onnodige data en mogelijk slechtere LCP op echte mobiele verbindingen.

**Aanbevolen oplossing:** Na visuele regressietests responsive preload/source-selectie, passende WebP/AVIF en een geordende gedeelde stylesheetstructuur; behoud goedgekeurde uitsnede en mobiele weergave.

**Wijzigingsrisico:** Middel tot hoog: hero’s zijn recent zorgvuldig afgestemd.

**Complexiteit:** Middel

**Latere verificatie:** Cold-cache netwerk met desktop/mobielprofielen: gedownloade bytes en zichtbare LCPbron; vergelijk alle 144 combinaties en origineelbeeldhashes.

### NV23 — P2 — Tests en CI sluiten niet meer volledig aan op huidige shop

**Locatie:** tests/test_control.py; tests/test_performance.py; .github/workflows/*.yml

**Wat misgaat:** Acht bestaande pytesttests falen, grotendeels door oude merk-, menu-, taal-, redirect- en testmodusverwachtingen. De integrationworkflow zoekt unittestbestanden test_nuvemixa_*.py die niet in deze werkmap aanwezig zijn.

**Bewijs:** 42 tests: 34 pass, 8 fail. /control hoort nu afgeschermd; over-trendmix hoort 301. Legacytest verwacht “AI TrendMix”; checkout verwacht verdwenen “Testmodus”.

**Klantimpact:** CI is geen betrouwbaar vrijgavebewijs zolang relevante checks ontbreken of verouderd zijn.

**Aanbevolen oplossing:** Herformuleer tests naar de afgesproken huidige functies; behoud securitychecks en voeg betekenisvolle klantreis/account/coupon/provider-sandboxtests toe. Laat ontbrekende testcollectie falen.

**Wijzigingsrisico:** Middel: niet eenvoudig slechte uitkomsten wegasserten.

**Complexiteit:** Middel

**Latere verificatie:** Volledige suite groen met aantoonbaar verzamelde tests; echte defecten blijven rood totdat opgelost; Pythonversies en isolated env gelijk aan release.

### NV24 — P2 — Registratie van routes hangt af van startmethode

**Locatie:** app.py:1439–1486

**Wat misgaat:** app.run staat vóór de laatste after_request-hooks, SSOregistratie en oude-URLredirect. Bij direct python app.py blokkeert de server voordat die regels worden uitgevoerd.

**Bewijs:** Bronvolgorde vastgesteld; audit importeert app zoals Flask CLI/WSGI en ziet 52 regels. Directe launch is niet gestart om de bestaande server niet te beïnvloeden.

**Klantimpact:** Verschillend lokaal/hostinggedrag en mogelijk ontbrekende veiligheidsheaders of redirects bij verkeerde startinstructie.

**Aanbevolen oplossing:** Plaats app.run later in een goedgekeurde wijziging na alle registraties, of gebruik een duidelijke factory/WSGIentrypoint; documenteer ondersteunde startwijze.

**Wijzigingsrisico:** Middel.

**Complexiteit:** Klein

**Latere verificatie:** Startmethodevergelijking in aparte processen: routekaart, securityheaders en redirects gelijk; geen debugserver als productieserver.

### NV25 — P2 — CSP is alleen rapporterend; inline-uitvoering blijft breed

**Locatie:** app.py:1443–1459; templates/base.html:46 en vergelijkbare headblokken

**Wat misgaat:** Er staat Content-Security-Policy-Report-Only met unsafe-inline. De localStorage-headerstijl wordt als CSS ingevoegd. Report-Only blokkeert geen XSS; dit is een hardeningtekort, geen aangetoonde XSS-exploit.

**Bewijs:** Responseheaders en headbron. Geïsoleerde gepubliceerde review wordt wel correct ge-escaped; SQL-injectiestring logt niet in.

**Klantimpact:** Beperkte extra bescherming als elders later HTML-/scriptinjectie ontstaat.

**Aanbevolen oplossing:** Inventariseer inlinehandlers en styles, beperk dynamische stijlwaarden en werk naar een geteste nonce/hash-CSP met rapportage; schakel handhaving pas na compatibiliteitscontrole in.

**Wijzigingsrisico:** Hoog voor bestaande scripts/vertalers als direct streng ingesteld.

**Complexiteit:** Middel

**Latere verificatie:** Report-onlymeldingen analyseren, vervolgens enforced staging-CSP; account, menu, talen, checkout en chat blijven werken; geen ongewenste externe verbindingen.

### NV26 — P2 — Reviewlimieten vertrouwen ongefilterde proxyheader en losse transacties

**Locatie:** app.py:1395; nv_reviews.py:submit_review

**Wat misgaat:** Clientidentiteit gebruikt rechtstreeks de eerste X-Forwarded-For-waarde. Daglimietcontrole en insert vormen geen aantoonbare atomische quotumreservering.

**Bewijs:** Broncontrole; geen proxyspoof- of raceaanval op productie uitgevoerd.

**Klantimpact:** Bij onbetrouwbare proxyheaders of gelijktijdige requests kan reviewspam moeilijker te beperken zijn.

**Aanbevolen oplossing:** Vertrouw alleen geconfigureerde reverse proxies en gebruik centrale, atomische throttling. Onderzoek actuele hostingheaderketen vóór aanpassing.

**Wijzigingsrisico:** Middel.

**Complexiteit:** Middel

**Latere verificatie:** Geïsoleerde gelijktijdigheid, vervalste header buiten vertrouwde proxy en legitieme proxychain; limieten zijn niet te omzeilen en echte klant-IP’s blijven correct.

### NV27 — P2 — Favorieten zijn browsergebonden en geen accountfunctie

**Locatie:** app.py:497–516; session[trendmix_wishlist]

**Wat misgaat:** Wishlist bewaart product-ID’s alleen in de clientsessie, niet per klant in de database. Een ander apparaat of gewiste cookie heeft de lijst niet.

**Bewijs:** Toggle werkt lokaal; databaseschema heeft geen wishlisttabel; sessieclear wist de lijst.

**Klantimpact:** Een account suggereert mogelijk meer continuïteit dan de huidige functie biedt.

**Aanbevolen oplossing:** Bepaal gewenste gast-/accountwishlist, voeg zo nodig klantgebonden opslag en veilig mergebeleid toe; communiceer anders browsergebonden aard.

**Wijzigingsrisico:** Middel bij samenvoegen van lijsten.

**Complexiteit:** Middel

**Latere verificatie:** Twee apparaten, gastnaaraccountmerge en accountwisseling; geen gedeelde of verloren favorieten.

### NV28 — P2 — Kortingscampagnes ontbreken als functionele keten

**Locatie:** app.py; nuvemixa_admin_store.py; beheer- en checkouttemplates

**Wat misgaat:** Er is geen couponmodel, checkoutvalidatie, persoonlijke uitgifte, redemptionledger, campagnedatums of beheerde kortingsbanner aangetroffen. Aanbiedingen en CSS “campaign” zijn geen couponinfrastructuur.

**Bewijs:** Gerichte bronzoekactie, routes en schemas: geen couponroute of campagnedatabase; 15%/20% niet functioneel aanwezig.

**Klantimpact:** Acties kunnen nu niet eerlijk, eenmalig of boekhoudkundig correct worden uitgevoerd.

**Aanbevolen oplossing:** Werk eerst NV01/02/03/06/11/13 af; ontwerp daarna campagnemodel en serverberekening volgens sectie J, zonder marketingclaim vóór beschikbaarheid.

**Wijzigingsrisico:** Hoog: marge, btw, fraude en klantverwachtingen.

**Complexiteit:** Groot

**Latere verificatie:** Start/eindgrens, klantbinding, minimum, exclusions, stacking, hergebruik/concurrentie, refund en e-mailretry; eerlijke negatieve review gelijk behandelen.

### NV29 — P3 — Interne oude merknamen en historische bestanden vragen gecontroleerd onderhoud

**Locatie:** Zie volledige TrendMix-tabel in sectie E

**Wat misgaat:** Legacybenamingen zitten in assets, templates, tests, envnamen en sessie-/localStoragekeys. Niet iedere string is klantzichtbaar of veilig te hernoemen.

**Bewijs:** Volledige bestand-/regellijst bijgevoegd; geen TrendMix in de onderzochte gerenderde klantbody’s, wel de oude URL in sitemap.

**Klantimpact:** Onderhoudsverwarring en regressierisico bij een blinde zoek/vervangactie.

**Aanbevolen oplossing:** Vervang alleen zichtbare copy direct bij latere opdracht; migreer functionele keys/aliassen met fallback. Houd oude URLredirects en historische herkomst aantoonbaar intact.

**Wijzigingsrisico:** Hoog bij blind vervangen, laag bij gefaseerde migratie.

**Complexiteit:** Middel

**Latere verificatie:** Zoek bron én render NL/EN opnieuw; bestaande carts/talen/configs en redirects werken nog; geen historische auditinformatie vernietigen.

### NV30 — P2 — AI-verbruiksopslag is niet zelfstandig reproduceerbaar in deze checkout

**Locatie:** nv_openai.py:103–125; ontbrekende nv_dashboard_postgres.py

**Wat misgaat:** Het optionele persistpad importeert nv_dashboard_postgres, dat niet in deze geïnventariseerde checkout staat. De uitzondering wordt afgevangen en de code valt terug op strengere geheugenlimieten; multiworkerbudget blijft zo geen bewezen centrale harde grens.

**Bewijs:** Bron- en bestandsinventaris. Geen echte AI-aanroep of betaald providergebruik; implementatie bevat wel eigen threadlock, fallbacklimiet en async verbruiksadministratie.

**Klantimpact:** Bij activering zonder de bedoelde dashboardomgeving is budget-/gebruiksrapportage mogelijk onvolledig.

**Aanbevolen oplossing:** Maak benodigde runtimeafhankelijkheden expliciet, test de persistente teller in de bedoelde omgeving en stel providerbudgetten/alerts onafhankelijk in.

**Wijzigingsrisico:** Middel voor kosten en beschikbaarheid.

**Complexiteit:** Middel

**Latere verificatie:** Ontbrekende database/module, herstart, meerdere workers en gelijktijdige requests; kostenregistratie en limieten aantoonbaar, zonder echte betaalde proef in deze audit.

### NV31 — P3 — Valutaberekening gebruikt floats

**Locatie:** app.py:1117, 1136; format_eur; toekomstige kortingsberekening

**Wat misgaat:** Subtotaal en totaal worden met float berekend. Een fout centbedrag is in de huidige testvoorbeelden niet aangetoond, maar het is een zwakke basis voor procentkorting, btw en refunds.

**Bewijs:** Bron: sum(float(price)*qty). Huidige éénartikeltest €24,95 correct.

**Klantimpact:** Toekomstige afrondingsverschillen tussen shop, factuur en betaalprovider.

**Aanbevolen oplossing:** Kies integercenten of Decimal en expliciet afrondings-/allocatiebeleid, inclusief korting per regel en btw.

**Wijzigingsrisico:** Middel financieel.

**Complexiteit:** Middel

**Latere verificatie:** Meerdere aantallen, 15%/20%, .005-grenzen, belastingtarieven, verzending en gedeeltelijke refund; som regels exact gelijk aan betaalbedrag.

## E. TrendMix-controle

De hoofdzoekactie leverde 301 bestand-/regelregistraties met 310 vermeldingen op. Inclusief aanvullend geïnventariseerde bestandsnamen bevat de bijlage hieronder **301 registraties**. Een regel kan meerdere matches bevatten; minified regels bevatten beperkte context rondom matches. Regel 0 betekent een bestandsnaam, geen tekstregel. De losse CSV bevat dezelfde volledige lijst. Zoekpatroon: hoofdletterongevoelig `trend[ -]?mix`, in bronbestanden en namen binnen de geïnventariseerde werkmap. Geen gitgeschiedenis, virtuele omgevingen, databases, versleutelde inhoud of OCR van alle oude binaire beelden doorgelicht; daarom geen garantie dat elders nooit een oude merknaam staat.

**Klantzichtbaar:** in de onderzochte actieve HTML-body’s en browserweergaven geen TrendMix gevonden. De sitemap noemt nog de oude URL `/over-trendmix`; die route geeft correct 301 naar `/over-nuvemixa`. **Functioneel:** sessiekeys, localStorage, APIpad, envnamen en Python/CSS/JSidentifiers moeten compatibel blijven of worden gemigreerd. **Interne bestandsnamen:** naam alleen is geen zichtbare merkfout. **Historisch:** backups behouden als herkomst, buiten actieve deployment houden. Voer geen globale zoek/vervang uit. Algemene verbeterdossier NV29; sitemapaanpassing NV17.

| Bestand | Regel | Aantal | Soort | Context | Aanbevolen actie |
| --- | --- | --- | --- | --- | --- |
| .github\workflows\nuvemixa-integration.yml | 19 | 1 | functional_identifier | TRENDMIX_LIVE_ORDERS: "false" | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| .github\workflows\nuvemixa-integration.yml | 29 | 1 | functional_identifier | leall -q app.py nuvemixa_admin_store.py nuvemixa_integrations.py trendmix_assistant.py tests | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| .github\workflows\trendmix-tests.yml | 0 | 1 | internal_filename | .github\workflows\trendmix-tests.yml | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| .github\workflows\trendmix-tests.yml | 1 | 1 | review_required | name: TrendMix regressietests | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| app.py | 180 | 1 | functional_identifier | for item in session.get("trendmix_cart", []): | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 283 | 1 | functional_identifier | return woo_configured() and os.getenv("TRENDMIX_LIVE_ORDERS", "").lower() == "true" | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 356 | 1 | functional_identifier | if request.endpoint == "trendmix_assistant": | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 372 | 1 | functional_identifier | nt(), "format_eur": format_eur, "wishlist_ids": set(session.get("trendmix_wishlist", [])), "csrf_token": csrf_token} | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 499 | 1 | functional_identifier | saved = session.get("trendmix_wishlist", []) | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 510 | 1 | functional_identifier | session["trendmix_wishlist"] = saved | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 909 | 1 | review_required | "over-trendmix": {"title": "Over NUVEMIXA", "description": "Ontdek het verhaal achter NUVEMIXA, onze vijf pro | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| app.py | 1113 | 1 | functional_identifier | session["trendmix_cart"] = [{"id": item["id"], "qty": item["qty"]} for item in cart] | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 1167 | 1 | functional_identifier | session.pop("trendmix_cart", None) | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 1172 | 1 | functional_identifier | session.pop("trendmix_test_checkout", None) | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 1294 | 1 | review_required | @app.route("/over-trendmix") | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| app.py | 1295 | 1 | review_required | def over_trendmix(): | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| app.py | 1296 | 1 | review_required | return render_info_page("over-trendmix") | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| app.py | 1355 | 1 | functional_identifier | def trendmix_security_headers(response): | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 1380 | 2 | functional_identifier | from trendmix_assistant import register_trendmix_assistant … from trendmix_assistant import register_trendmix_assistant | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 1381 | 1 | functional_identifier | register_trendmix_assistant(app, products, CATEGORIES, live_orders_enabled) | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 1465 | 1 | review_required | # NUVEMIXA herstel 2 (22-11-2026): /over-trendmix permanent naar /over-nuvemixa en juiste canonical. | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| app.py | 1470 | 1 | functional_identifier | def _nv2_over_trendmix_redirect(): | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| app.py | 1471 | 1 | review_required | if _nv2_request.path.rstrip("/") == "/over-trendmix": | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| app.py | 1481 | 1 | review_required | fixed = re.sub(r'(<link rel="canonical" href="[^"]*?)/over-trendmix"', r'\1/over-nuvemixa"', body) | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| app_backup.py | 583 | 1 | historical | print("TRENDMIX DATABASEVALIDATIE GESLAAGD") | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| build_catalog.py | 34 | 2 | review_required | {"name": "TrendMix Gaming Combo", "price": 699.00, "old_price": 899.00, "brand": "TrendMix", "badge": "Hot"}, … x Gaming Combo", "price": 699.00, "old_price": 899.00, "brand": "TrendMix", "badge": "Hot"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 35 | 1 | review_required | e Starter Pack", "price": 179.00, "old_price": 249.00, "brand": "TrendMix", "badge": "Deal"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 36 | 1 | review_required | a RGB Desk Set", "price": 149.00, "old_price": 219.00, "brand": "TrendMix", "badge": "New"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 37 | 1 | review_required | lean Beauty Kit", "price": 89.00, "old_price": 119.00, "brand": "TrendMix", "badge": "Promo"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 38 | 1 | review_required | e Gaming Kit", "price": 1299.00, "old_price": 1599.00, "brand": "TrendMix", "badge": "Best"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 39 | 1 | review_required | sk Flex Bundle", "price": 199.00, "old_price": 269.00, "brand": "TrendMix", "badge": "Hot"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 40 | 1 | review_required | Recovery Pack", "price": 159.00, "old_price": 219.00, "brand": "TrendMix", "badge": "Top"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 41 | 1 | review_required | yle Essentials", "price": 119.00, "old_price": 169.00, "brand": "TrendMix", "badge": "Deal"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 42 | 1 | review_required | ojector Bundle", "price": 249.00, "old_price": 329.00, "brand": "TrendMix", "badge": "New"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 43 | 1 | review_required | ness Setup Pro", "price": 229.00, "old_price": 299.00, "brand": "TrendMix", "badge": "Hot"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 44 | 1 | review_required | eauty Care Week", "price": 79.00, "old_price": 109.00, "brand": "TrendMix", "badge": "Promo"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 45 | 1 | review_required | B Air Flow Kit", "price": 109.00, "old_price": 159.00, "brand": "TrendMix", "badge": "Deal"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 46 | 1 | review_required | e Work Station", "price": 349.00, "old_price": 449.00, "brand": "TrendMix", "badge": "Best"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 47 | 1 | review_required | Lock & Sensor", "price": 219.00, "old_price": 289.00, "brand": "TrendMix", "badge": "New"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 48 | 1 | review_required | very Massage Set", "price": 69.00, "old_price": 99.00, "brand": "TrendMix", "badge": "Hot"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 49 | 1 | review_required | B Strip Lighting", "price": 59.00, "old_price": 81.00, "brand": "TrendMix", "badge": "Deal"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 50 | 1 | review_required | l Tech Organizer", "price": 45.00, "old_price": 69.00, "brand": "TrendMix", "badge": "Top"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 51 | 1 | review_required | e Wellness Kit", "price": 189.00, "old_price": 249.00, "brand": "TrendMix", "badge": "New"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 52 | 1 | review_required | t Comfort Pack", "price": 139.00, "old_price": 179.00, "brand": "TrendMix", "badge": "Promo"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 53 | 1 | review_required | Accessory Pack", "price": 119.00, "old_price": 159.00, "brand": "TrendMix", "badge": "Hot"}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 197 | 1 | review_required | "brand": product.get("brand", "TrendMix"), | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 201 | 1 | review_required | "description": f"{product['name']} van {product.get('brand', 'TrendMix')} – perfect voor {category_name.lower()} en dagelijks gebruik.", | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 205 | 1 | review_required | "affiliate_network": "TrendMix", | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| build_catalog.py | 208 | 1 | review_required | "supplier": "TrendMix Supplier", | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| content\information\over-trendmix.json | 0 | 1 | internal_filename | content\information\over-trendmix.json | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| content\information\over-trendmix.json | 1 | 1 | review_required | {"slug":"over-trendmix","nl":{"title":"Over NUVEMIXA","description":"Ontdek de visie achter NUVEMIXA, onze productcol | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| docs\NUVEMIXA-FINAL-QA-20261105.md | 5 | 1 | review_required | Repository: `mdscoop7-max/Trendmix`; branch: `design/pixel-polish-responsive-20261027`. | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| docs\NUVEMIXA-INTEGRATION-DEPLOY.md | 48 | 1 | functional_identifier | - `TRENDMIX_LIVE_ORDERS`: blijft uit totdat echte order- en betaaltests geslaagd zijn. | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| integrations\sell_the_trend.json | 5 | 1 | review_required | "customer_checkout": "TrendMix", | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| integrations\sell_the_trend.json | 8 | 1 | review_required | "customer_orders_on_trendmix", | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| integrations\sell_the_trend.json | 21 | 1 | review_required | "Connect TrendMix to WooCommerce or Shopify before enabling live payment and automated fulfillment." | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| nv_openai.py | 70 | 1 | functional_identifier | return (os.getenv("NUVEMIXA_AI_MODEL", "").strip() or os.getenv("TRENDMIX_AI_MODEL", "").strip() | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| product_art.py | 1 | 1 | review_required | """TrendMix productillustraties. | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| SITE-CONTROL.md | 1 | 1 | review_required | # TrendMix — site control | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| SITE-CONTROL.md | 6 | 1 | review_required | - [x] Render URL is the canonical site: https://trendmix.onrender.com | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| SITE-CONTROL.md | 15 | 1 | review_required | - [x] Over TrendMix | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| SITE-CONTROL.md | 42 | 1 | review_required | - [ ] Replace catalog image URLs when the final TrendMix product photos are supplied/committed | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\app.js | 35 | 1 | functional_identifier | localStorage.setItem('trendmix-language',lang); | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\app.js | 56 | 1 | internal_identifier | const select=document.getElementById('trendmixLanguage') \|\| document.getElementById('languageSelect') \|\| document.getElementById('tmGlobalLan | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\app.js | 57 | 1 | functional_identifier | const saved=localStorage.getItem('trendmix-language')\|\|detectNUVEMIXALanguage(); | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\app.js | 186 | 1 | internal_identifier | set('.tm-footer .footer-column a[href="/over-trendmix"]',t.about); | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| static\app.js | 215 | 1 | internal_identifier | function trendMixLanguageSelfTest(){ | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\app.js | 216 | 1 | internal_identifier | const select=document.getElementById('trendmixLanguage')\|\|document.getElementById('languageSelect')\|\|document.getElementById('tmGlobalLanguag | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\app.js | 227 | 1 | internal_identifier | trendMixLanguageSelfTest(); | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\app.js | 228 | 1 | internal_identifier | const select=document.getElementById('trendmixLanguage')\|\|document.getElementById('languageSelect')\|\|document.getElementById('tmGlobalLanguag | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\app.js | 247 | 1 | internal_identifier | const root=document.getElementById('trendmixAi'); if(!root)return; | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\category-cards.css | 1 | 1 | internal_identifier | /* TrendMix collection cards: compact photo-led layout. */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\language-sticky.css | 1 | 1 | internal_identifier | /* TrendMix language control: stays visible while scrolling */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\languages.js | 163 | 6 | internal_identifier | const infoContent={nl:{'over-trendmix':{title:"Over NUVEMIXA",desc:"NUVEMIXA wordt ontwikkeld als moderne webshop met vijf duidelijk … aan de diensten die werkelijk worden gebruikt.</p>'}},en:{'over-trendmix':{title:"About NUVEMIXA",desc:"NUVEMIXA is being developed as a modern online store with five … he services actually used at commercial launch.</p>'}},fr:{'over-trendmix':{title:"À propos de NUVEMIXA",desc:"NUVEMIXA est développé comme une boutique en ligne modern … les services réellement utilisés au lancement.</p>'}},de:{'over-trendmix':{title:"Über NUVEMIXA",desc:"NUVEMIXA wird als moderner Onlineshop mit fünf klaren Kategorien … iellen Start tatsächlich eingesetzten Diensten.</p>'}}, | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\languages.js | 177 | 1 | internal_identifier | if(select.dataset.trendmixBound==='1') return; | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\languages.js | 178 | 1 | internal_identifier | select.dataset.trendmixBound='1'; | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\languages.js | 181 | 1 | functional_identifier | const current=localStorage.getItem('trendmix-language')\|\|detectNUVEMIXALanguage(); | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\nv-fix-20261120e.js | 21 | 1 | functional_identifier | try { v = localStorage.getItem('trendmix-language'); } catch (e) {} | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\nv-polish-20261122.js | 19 | 1 | functional_identifier | try { l = localStorage.getItem('trendmix-language') \|\| ''; } catch (e) {} | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\nv-polish-20261122.js | 177 | 1 | functional_identifier | window.addEventListener('storage', function (e) { if (e.key === 'trendmix-language') run(); }); | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\storefront-v2.css | 7 | 1 | internal_identifier | /* TrendMix footer */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\storefront-v2.css | 10 | 1 | internal_identifier | /* TrendMix mobile navigation refresh: accessible floating five-action dock */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\storefront-v2.css | 28 | 1 | internal_identifier | /* TrendMix responsive polish — 2026-10-27. | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 4 | 1 | internal_identifier | /* TrendMix footer contact form + compact mobile app navigation */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 18 | 1 | internal_identifier | /* TrendMix basislayout v1 — donker gamingthema */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 65 | 1 | internal_identifier | /* TrendMix v2: language bar, professional footer and product UX */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 118 | 1 | internal_identifier | /* TrendMix catalog cleanup: keep the current dark theme, simplify mobile header. */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 130 | 1 | internal_identifier | /* Improve hero text contrast on the current dark TrendMix theme. */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 135 | 1 | internal_identifier | /* TrendMix 2026 light editorial storefront */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 142 | 1 | internal_identifier | /* Approved TrendMix reference - exact compact storefront composition */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 154 | 1 | internal_identifier | /* TrendMix reference storefront v2 — desktop + mobile app */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 173 | 1 | internal_identifier | /* TrendMix complete footer v2 */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 179 | 1 | internal_identifier | /* TrendMix final product interaction polish */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 189 | 1 | internal_identifier | /* TrendMix mobile shopping-app experience */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\style.css | 200 | 1 | internal_identifier | /* TrendMix 2026 storefront redesign — overrides previous homepage layout */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-english-labels.js | 0 | 1 | internal_filename | static\trendmix-english-labels.js | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| static\trendmix-english-labels.js | 1 | 1 | internal_identifier | window.TrendMixEnglishLabels={ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-english-labels.js | 221 | 2 | internal_identifier | "TRENDMIX SHOP": "TRENDMIX SHOP", … "TRENDMIX SHOP": "TRENDMIX SHOP", | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-english-labels.js | 239 | 2 | internal_identifier | "TRENDMIX ACCOUNT": "TRENDMIX ACCOUNT", … "TRENDMIX ACCOUNT": "TRENDMIX ACCOUNT", | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-footer-unified.css | 0 | 1 | internal_filename | static\trendmix-footer-unified.css | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| static\trendmix-footer-unified.css | 1 | 1 | internal_identifier | /* TrendMix shared footer. Based on the exact cart-page footer rules from style.css. | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-footer-unified.css | 18 | 1 | internal_identifier | /* TrendMix complete footer v2 */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-hero-fix.css | 0 | 1 | internal_filename | static\trendmix-hero-fix.css | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| static\trendmix-info.css | 0 | 1 | internal_filename | static\trendmix-info.css | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| static\trendmix-info.css | 2 | 1 | internal_identifier | /* TrendMix information and consumer-rights pages — editorial layout */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-ui-2026.css | 0 | 1 | internal_filename | static\trendmix-ui-2026.css | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| static\trendmix-ui-2026.css | 2 | 1 | internal_identifier | /* TrendMix UI 2026: one navy/blue system for navigation, commerce and help. | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-ui-2026.css | 279 | 1 | internal_identifier | /* AI TrendMix floating button: distinct indigo-blue accent, regular shop buttons unchanged. */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-ui-2026.css | 537 | 1 | internal_identifier | /* TrendMix final bright pixel polish: restrained, sharp, legible surfaces. */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\trendmix-ui-2026.js | 0 | 1 | internal_filename | static\trendmix-ui-2026.js | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| static\trendmix-ui-2026.js | 5 | 1 | functional_identifier | const storageKey='trendmix-language'; | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\trendmix-ui-2026.js | 164 | 1 | internal_identifier | const picker=$('#trendmixLanguage')\|\|$('#languageSelect'); | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\trendmix-ui-2026.js | 244 | 1 | functional_identifier | const res=await fetch('/api/trendmix-assistant',{ | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\trendmix-ui-2026.js | 305 | 1 | internal_identifier | const picker=$('#trendmixLanguage')\|\|$('#languageSelect'); | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| static\ux.css | 3 | 1 | internal_identifier | /* TrendMix UX polish layer: keeps the core theme intact while adding clearer hierarchy and controls. */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\ux.css | 67 | 1 | internal_identifier | /* TrendMix mobile fixes: header/cart/language/contact */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\ux.css | 556 | 1 | internal_identifier | /* TrendMix Assistent */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\ux.css | 588 | 1 | internal_identifier | /* Final storefront polish: approved TrendMix light desktop + app-like mobile UI */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| static\ux.css | 596 | 1 | internal_identifier | /* TrendMix 2026 mobile polish - legacy/information pages */ | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| templates-backup-encoding\account.html | 4 | 1 | historical | Account - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\account.html | 14 | 1 | historical | TRENDMIX ACCOUNT | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\account.html | 22 | 1 | historical | Beheer je account en je TrendMix-gegevens. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\account.html | 42 | 1 | historical | Welkom bij TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 7 | 1 | historical | <title>{% block title %}TrendMix{% endblock %}</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 10 | 1 | historical | content="{% block description %}TrendMix - ontdek trending tech, gadgets, smart home, beauty en lifestyle producten.{% endblock %}"> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 29 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 155 | 1 | historical | alt="TrendMix" | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 184 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 228 | 1 | historical | <h3>TrendMix</h3> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 254 | 1 | historical | © 2026 TrendMix — Alle rechten voorbehouden. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\base.html | 349 | 1 | historical | "trendmix-language", | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\cart.html | 4 | 1 | historical | Winkelwagen - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\cart.html | 14 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 7 | 1 | historical | <title>{{ category_name }} \| TrendMix</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 11 | 1 | historical | content="Ontdek populaire en handige producten bij TrendMix." | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 100 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 219 | 1 | historical | TrendMix collectie | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 398 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 403 | 1 | historical | voor iedere dag. TrendMix brengt | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 476 | 1 | historical | Ontdek TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\category.html | 534 | 1 | historical | © 2026 TrendMix. Alle rechten voorbehouden. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\checkout.html | 3 | 1 | historical | {% block title %}Afrekenen \| TrendMix{% endblock %} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-backup.html | 8 | 1 | historical | <title>TrendMix</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-backup.html | 108 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-backup.html | 157 | 1 | historical | Stap 3 â€” TrendMix header | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 1 | 1 | historical | Gebruik deze bestaande TrendMix "index stap 3 backup" als VISUELE BASIS voor de header. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 4 | 1 | historical | BEHOUD HET BESTAANDE TRENDMIX-DESIGN. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 21 | 1 | historical | bestaande header technisch geschikt te maken voor de definitieve TrendMix affiliate-website. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 59 | 1 | historical | Maar verwijder claims die suggereren dat TrendMix zelf verzending, retouren of klantenservice verzorgt. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 67 | 1 | historical | bij de externe webshop/affiliate-partner en niet automatisch bij TrendMix. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 69 | 1 | historical | Vervang deze eventueel door neutrale TrendMix-informatie, bijvoorbeeld: | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 75 | 1 | historical | Gebruik alleen claims die TrendMix daadwerkelijk kan waarmaken. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 116 | 1 | historical | TrendMix-logo | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 145 | 1 | historical | TrendMix is een affiliate-platform. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 147 | 1 | historical | Daarom mag de header NIET suggereren dat TrendMix zelf een webshop met checkout is. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 181 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 190 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 199 | 1 | historical | TrendMix verkoopt geen producten rechtstreeks. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 221 | 1 | historical | Verzending door TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 222 | 1 | historical | Retourneren door TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 240 | 1 | historical | De bestaande TrendMix-header moet visueel hetzelfde blijven. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index-stap3-backup.html | 281 | 1 | historical | 12. Bestaande TrendMix styling blijft behouden | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index.html | 6 | 1 | historical | WAAROM TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index.html | 11 | 1 | historical | <span class="section-label">TRENDMIX</span> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index.html | 13 | 1 | historical | <h1>Waarom TrendMix?</h1> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index.html | 329 | 1 | historical | <span class="section-label">TRENDMIX SHOP</span> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\index.html | 336 | 1 | historical | Bekijk de volledige collectie van TrendMix. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\order_success.html | 3 | 1 | historical | {% block title %}Bestelling Geplaatst \| TrendMix{% endblock %} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\pc-componenten.html | 8 | 1 | historical | <title>{{ category }} \| TrendMix</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\product.html | 5 | 1 | historical | {{ product.name }} - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\product.html | 7 | 1 | historical | Product - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\product.html | 59 | 1 | historical | {{ product.category\|default('TrendMix') }} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\product.html | 77 | 1 | historical | 'Ontdek dit product bij TrendMix.' | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\shop.html | 5 | 1 | historical | {{ category }} - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\shop.html | 7 | 1 | historical | Shop - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\shop.html | 17 | 1 | historical | TRENDMIX SHOP | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\account.html | 4 | 1 | historical | Account - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\account.html | 14 | 1 | historical | TRENDMIX ACCOUNT | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\account.html | 22 | 1 | historical | Beheer je account en je TrendMix-gegevens. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\account.html | 42 | 1 | historical | Welkom bij TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 7 | 1 | historical | <title>{% block title %}TrendMix{% endblock %}</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 10 | 1 | historical | content="{% block description %}TrendMix - ontdek trending tech, gadgets, smart home, beauty en lifestyle producten.{% endblock %}"> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 29 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 155 | 1 | historical | alt="TrendMix" | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 184 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 228 | 1 | historical | <h3>TrendMix</h3> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 254 | 1 | historical | © 2026 TrendMix — Alle rechten voorbehouden. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\base.html | 349 | 1 | historical | "trendmix-language", | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\cart.html | 4 | 1 | historical | Winkelwagen - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\cart.html | 14 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 7 | 1 | historical | <title>{{ category_name }} \| TrendMix</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 11 | 1 | historical | content="Ontdek populaire en handige producten bij TrendMix." | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 100 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 219 | 1 | historical | TrendMix collectie | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 398 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 403 | 1 | historical | voor iedere dag. TrendMix brengt | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 476 | 1 | historical | Ontdek TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\category.html | 534 | 1 | historical | © 2026 TrendMix. Alle rechten voorbehouden. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\checkout.html | 3 | 1 | historical | {% block title %}Afrekenen \| TrendMix{% endblock %} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-backup.html | 8 | 1 | historical | <title>TrendMix</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-backup.html | 108 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-backup.html | 157 | 1 | historical | Stap 3 â€” TrendMix header | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 1 | 1 | historical | Gebruik deze bestaande TrendMix "index stap 3 backup" als VISUELE BASIS voor de header. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 4 | 1 | historical | BEHOUD HET BESTAANDE TRENDMIX-DESIGN. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 21 | 1 | historical | bestaande header technisch geschikt te maken voor de definitieve TrendMix affiliate-website. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 59 | 1 | historical | Maar verwijder claims die suggereren dat TrendMix zelf verzending, retouren of klantenservice verzorgt. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 67 | 1 | historical | bij de externe webshop/affiliate-partner en niet automatisch bij TrendMix. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 69 | 1 | historical | Vervang deze eventueel door neutrale TrendMix-informatie, bijvoorbeeld: | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 75 | 1 | historical | Gebruik alleen claims die TrendMix daadwerkelijk kan waarmaken. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 116 | 1 | historical | TrendMix-logo | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 145 | 1 | historical | TrendMix is een affiliate-platform. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 147 | 1 | historical | Daarom mag de header NIET suggereren dat TrendMix zelf een webshop met checkout is. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 181 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 190 | 1 | historical | TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 199 | 1 | historical | TrendMix verkoopt geen producten rechtstreeks. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 221 | 1 | historical | Verzending door TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 222 | 1 | historical | Retourneren door TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 240 | 1 | historical | De bestaande TrendMix-header moet visueel hetzelfde blijven. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index-stap3-backup.html | 281 | 1 | historical | 12. Bestaande TrendMix styling blijft behouden | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index.html | 6 | 1 | historical | WAAROM TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index.html | 11 | 1 | historical | <span class="section-label">TRENDMIX</span> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index.html | 13 | 1 | historical | <h1>Waarom TrendMix?</h1> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index.html | 329 | 1 | historical | <span class="section-label">TRENDMIX SHOP</span> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\index.html | 336 | 1 | historical | Bekijk de volledige collectie van TrendMix. | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\order_success.html | 3 | 1 | historical | {% block title %}Bestelling Geplaatst \| TrendMix{% endblock %} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\pc-componenten.html | 8 | 1 | historical | <title>{{ category }} \| TrendMix</title> | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\product.html | 5 | 1 | historical | {{ product.name }} - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\product.html | 7 | 1 | historical | Product - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\product.html | 59 | 1 | historical | {{ product.category\|default('TrendMix') }} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\product.html | 77 | 1 | historical | 'Ontdek dit product bij TrendMix.' | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\shop.html | 5 | 1 | historical | {{ category }} - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\shop.html | 7 | 1 | historical | Shop - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\shop.html | 17 | 1 | historical | TRENDMIX SHOP | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\wishlist.html | 4 | 1 | historical | Verlanglijst - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\wishlist.html | 14 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\templates\wishlist.html | 62 | 1 | historical | {{ product.category\|default('TrendMix') }} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\wishlist.html | 4 | 1 | historical | Verlanglijst - TrendMix | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\wishlist.html | 14 | 1 | historical | TRENDMIX | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates-backup-encoding\wishlist.html | 62 | 1 | historical | {{ product.category\|default('TrendMix') }} | Historisch: behouden als herkomst; niet publiceren/uitvoeren; geen blinde hernoeming. |
| templates\_bottomnav.html | 333 | 1 | functional_identifier | <script defer src="{{ url_for('static',filename='trendmix-english-labels.js',v='20261120w') }}"></script> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\_bottomnav.html | 334 | 1 | functional_identifier | <script defer src="{{ url_for('static',filename='trendmix-ui-2026.js',v='20261120w') }}"></script> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\_bottomnav.html | 386 | 1 | functional_identifier | 26-en.jpg'};function lang(){var l='';try{l=localStorage.getItem('trendmix-language')\|\|''}catch(e){}return (l\|\|document.documentElement.lang\|\|'nl').slice(0,2).toLowerCas | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\_bottomnav.html | 388 | 1 | functional_identifier | w WeakMap();function lang(){var l="";try{l=localStorage.getItem("trendmix-language")\|\|""}catch(e){}return (l\|\|document.documentElement.lang\|\|"nl").slice(0,2).toLowerCas | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\admin_reviews.html | 27 | 1 | review_required | <div><a href="https://trendmix.onrender.com/dashboard?section=klanten">&larr; Terug naar dashboard</a></div></div> | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| templates\base.html | 10 | 1 | functional_identifier | 3cbb"><link rel="stylesheet" href="{{ url_for('static',filename='trendmix-footer-unified.css',v='20261105-footer-clean2') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\base.html | 12 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\cart.html | 5 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\cart.html | 7 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\category.html | 11 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\category.html | 13 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\checkout.html | 6 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\checkout.html | 8 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\contact.html | 12 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\contact.html | 13 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\faq.html | 11 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\faq.html | 13 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\faq.html | 24 | 1 | review_required | <a class="back-link" href="/" data-i18n="backToTrendmix">← Terug naar NUVEMIXA</a> | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| templates\index.html | 18 | 1 | functional_identifier | 3cbb"><link rel="stylesheet" href="{{ url_for('static',filename='trendmix-footer-unified.css',v='20261105-footer-clean2') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\index.html | 20 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\info.html | 11 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static',filename='trendmix-info.css',v='20261019-1') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\info.html | 12 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\info.html | 14 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\info.html | 25 | 1 | review_required | <a class="back-link" href="/" data-i18n="backToTrendmix">← Terug naar NUVEMIXA</a> | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| templates\meer.html | 45 | 1 | review_required | ('/over-trendmix','#d97706','#fbbf24','<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><path d="M12 7.5h.01" | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| templates\meer.html | 57 | 1 | functional_identifier | g');if(!b)return;function cur(){try{return localStorage.getItem('trendmix-language')==='en'?'en':'nl'}catch(e){return'nl'}} | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\meer.html | 59 | 1 | functional_identifier | unction(){var n=cur()==='en'?'nl':'en';try{localStorage.setItem('trendmix-language',n)}catch(e){}document.documentElement.setAttribute('lang',n);location.reload()});})( | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\offers.html | 2 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\offers.html | 4 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\product.html | 61 | 1 | functional_identifier | cbb"><link rel="stylesheet" href="{{ url_for('static', filename='trendmix-footer-unified.css', v='20261110-footer-allpages') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| templates\product.html | 63 | 1 | functional_identifier | <link rel="stylesheet" href="{{ url_for('static', filename='trendmix-ui-2026.css', v='20261110-flitsfix') }}"> | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| tests\test_control.py | 19 | 1 | internal_identifier | assert b"TrendMix Control" in response.data or b"Controle" in response.data | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 46 | 1 | internal_identifier | for path in ("/", "/faq", "/contact", "/over-trendmix", "/bestellen", "/retouren", "/voorwaarden", "/privacy", "/cookies", "/robots.txt", "/sitemap. | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| tests\test_control.py | 177 | 1 | internal_identifier | for path in ("/shop", "/contact", "/privacy", "/over-trendmix", "/aanbiedingen"): | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| tests\test_control.py | 203 | 1 | functional_identifier | assert "trendmix-ui-2026.css" in html | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 204 | 1 | functional_identifier | assert "trendmix-ui-2026.js" in html | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 217 | 1 | functional_identifier | cart = data.get("trendmix_cart", []) | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 223 | 1 | functional_identifier | assert not data.get("trendmix_cart") | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 244 | 1 | functional_identifier | monkeypatch.delenv("TRENDMIX_LIVE_ORDERS", raising=False) | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 252 | 1 | internal_identifier | "/over-trendmix", "/account", "/aanbiedingen", | Legacy-URL/contentbron: 301 behouden; sitemap/canonical naar NUVEMIXA; zichtbare merkcopy apart toetsen. |
| tests\test_control.py | 277 | 1 | functional_identifier | css = Path("static/trendmix-ui-2026.css").read_text(encoding="utf-8") | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 297 | 1 | internal_identifier | "over-trendmix": 7, | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 324 | 1 | functional_identifier | assert "trendmix-info.css" in html, slug | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 329 | 1 | functional_identifier | script = Path("static/trendmix-ui-2026.js").read_text(encoding="utf-8") | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 365 | 1 | functional_identifier | source = Path("static/trendmix-ui-2026.js").read_text(encoding="utf-8") | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 372 | 1 | functional_identifier | script = Path("static/trendmix-english-labels.js").read_text(encoding="utf-8") | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 373 | 1 | internal_identifier | assert "TrendMixEnglishLabels" in script | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 376 | 1 | functional_identifier | translator = Path("static/trendmix-ui-2026.js").read_text(encoding="utf-8") | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_control.py | 384 | 1 | functional_identifier | assert "trendmix-english-labels.js" in response.get_data(as_text=True) | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_performance.py | 22 | 1 | functional_identifier | unversioned = client.get("/static/trendmix-hero-fix.css") | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_performance.py | 31 | 1 | functional_identifier | for path in ("/", "/winkelwagen", "/api/trendmix-assistant"): | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_performance.py | 50 | 1 | functional_identifier | def test_shared_cart_footer_and_ai_trendmix_remain_everywhere(): | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_performance.py | 60 | 1 | internal_identifier | assert 'AI TrendMix' in html, path | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_performance.py | 70 | 1 | internal_identifier | assert 'AI TrendMix' in html | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_security.py | 1 | 1 | internal_identifier | """Regression tests for TrendMix application boundary security.""" | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_security.py | 60 | 1 | functional_identifier | monkeypatch.delenv("TRENDMIX_LIVE_ORDERS", raising=False) | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| tests\test_security.py | 75 | 1 | functional_identifier | assert "trendmix_test_checkout" not in saved | Interne test/CI: gewenste NUVEMIXA-uitkomst actualiseren; geen functionele string blind vervangen. |
| trendmix_assistant.py | 0 | 1 | internal_filename | trendmix_assistant.py | Interne bestandsnaam: alleen later gefaseerd hernoemen met alle verwijzingen/URL-compatibiliteit. |
| trendmix_assistant.py | 12 | 1 | review_required | u","have","price","are","this","about","with","product","order","trendmix","hello","hoi","hallo"} | Brontekst/commentaar of mogelijke copy: klantzichtbaarheid beoordelen; zichtbare naam NUVEMIXA, interne compatibiliteit behouden. |
| trendmix_assistant.py | 157 | 1 | functional_identifier | def register_trendmix_assistant(app,catalog,categories,live_orders_enabled): | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| trendmix_assistant.py | 158 | 1 | functional_identifier | @app.route("/api/trendmix-assistant",methods=["GET","POST"]) | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |
| trendmix_assistant.py | 159 | 1 | functional_identifier | def trendmix_assistant(): | Functioneel identifier/key/asset: afhankelijkheden inventariseren; migratie/fallback voor sessie, taal, env en URL. |

## F. Juridische controle

Dit is een inhoudelijke en technische voorcontrole, geen definitieve juridische goedkeuring. De daadwerkelijk verkopende entiteit, landen, productrollen (importeur/fabrikant), omvang van de onderneming en leverancierscontracten zijn niet vastgesteld. **Juridische controle vereist** voor alle onderstaande definitieve stukken en uitzonderingen.

| Onderdeel | Huidige toestand | Voor commerciële opening |
| --- | --- | --- |
| Identiteit/voorwaarden | Toekomstige bedrijfsvermelding en algemene uitleg; geen complete feitelijke identiteit. NV04. | Handelsnaam, rechtsvorm indien relevant, vestigings-/klachtadres, bereikbare contactgegevens, handelsregister en btwgegevens waar verplicht. |
| Prijzen/btw/betaling | Indicatieve catalogusbedragen en verzending later. NV01/NV03. | Totale prijs inclusief verplichte kosten en toepasselijke belasting vóór definitieve bestelling; duidelijke betaalplicht. |
| Levering | Termijn/landen/kosten leverancier nog te bevestigen. NV02/NV10. | Werkelijke levertermijnen, landselectie, kosten, risico en niet-leveringsprocedure; stem UI en backend af. |
| Bedenktijd/herroeping | Veel uitleg over 14 dagen en uitzonderingen; operationele functie beloofd. NV04. | Juiste informatie + modelformulier + eenvoudig toegankelijke online ontbindingsfunctie en ontvangstbevestiging; geen verplicht account voor de functie. |
| Retourkosten/terugbetaling | Uitleg algemeen, retouradres/methode nog niet vastgesteld. | Maak vooraf duidelijk wie kosten draagt en hoe terugbetaling werkt; geen algemene categorie-uitsluiting zonder wettelijke grond. |
| Garantie/klachten | Geen vaste allesomvattende garantieduur beloofd; praktische afhandeling nog in voorbereiding. | Werkend aanspreekpunt, redelijke klachtenprocedure en wettelijke conformiteitsrechten; fabrikantgarantie mag die niet beperken. |
| Privacy/AVG | Brede voorbereidende tekst tegenover al aanwezige accounts/reviews/chat. NV16. | Actuele verantwoordelijke, doelen/grondslagen, gegevens, ontvangers, doorgiften, termijnen, rechten en klachtmogelijkheid. Geen marketingopt-in afleiden uit accountregistratie. |
| Cookies/opslag | Functionele sessie-/taal-/UIopslag aanwezig; geen volledige productietrackerinventaris. | Noodzaak per opslag aantonen; voorafgaande toestemming voor tracking waar vereist en eenvoudige intrekking. Geen onnodige cookiewall ontwerpen. |
| Reviews | Moderatie mogelijk, verified handmatig. NV13. | Leg verificatie en moderatie uit; alleen echte ervaringen, herkenbare incentives, ook negatieve ervaringen eerlijk behandelen. |
| Kortingsvoorwaarden | Niet gebouwd. NV28. | Duidelijke duur, persoonlijke binding, minimum, uitsluitingen, stacking, retour-/refundbeleid en bewijs van reële referentieprijzen waar vereist. |
| Marketing/e-mails | Geen bewezen consentledger of klantuitnodigingsketen. NV11/NV16. | Onderscheid transactioneel bericht en reclame; beoordeel opt-in/bestaandeklantuitzondering en afmelding; consent aantoonbaar. |
| Productveiligheid | Test-SKU’s en generieke beelden. NV02. | Per artikel toepasselijke GPSR/CE/elektronica/batterij/cosmetica-/gezondheidsclaims en importeursinformatie laten vaststellen; geen categoriebrede juridische zekerheid. |
| Toegankelijkheid | Visuele/DOMsteekproef; geen volledige conformiteitsverklaring. NV19–21. | Toepasselijkheid e-commerceregels en eventuele micro-ondernemingsuitzondering laten toetsen; werkende login/checkout voor klanten met beperkingen. |

Bronnen, geraadpleegd op 23-11-2026: [ACM checklist online verkoop](https://www.acm.nl/nl/verkoop-aan-consumenten/online-verkoop/checklist-online-verkoop) en [verplichte informatie](https://www.acm.nl/nl/verkoop-aan-consumenten/consumenten-informeren/verplichte-informatie-voor-en-na-de-koop) ondersteunen de controle op verkoper, kosten en koopinformatie. De actuele [ACM-pagina over bedenktijd](https://www.acm.nl/nl/verkoop-aan-consumenten/klantenservice/bedenktijd) noemt de herroepingsknop vanaf **25 juni 2026**; een eerdere ACM-aankondiging noemt 19 juni. Gebruik daarom de actuele uitleg en laat de precieze toepasselijkheid juridisch bevestigen. De [implementatiewet](https://zoek.officielebekendmakingen.nl/stb-2026-153.html) bevat de online ontbindingsfunctie. De huidige webshoptekst spreekt alleen van “sinds juni 2026”.

Voor privacy/consent: [Autoriteit Persoonsgegevens over cookies](https://autoriteitpersoonsgegevens.nl/nl/onderwerpen/internet-telefoon-en-tv/cookies) en [normuitleg intrekken toestemming](https://www.autoriteitpersoonsgegevens.nl/uploads/2024-03/Normuitleg%20AP%20intrekken%20toestemming%20cookiebanners.pdf). Voor incentives: [ACM over reviews](https://www.acm.nl/nl/verkoop-aan-consumenten/reclame-en-verleiden/online-beinvloeden/reviews-en-beoordelingen-gebruiken): echte ervaringen, transparantie over een beloning, geen beloning uitsluitend voor een positief verhaal. Voor prijsacties: [Ondernemersplein prijsvermelding](https://ondernemersplein.overheid.nl/wetten-en-regels/prijs-vermelden-op-een-product/); beoordeel het verschil tussen openbare prijsverlaging en een werkelijk persoonlijke coupon, zonder automatisch aan te nemen dat elke kortingsvorm dezelfde referentieprijsregel heeft. [ACM toegankelijkheid e-handelsdiensten](https://www.acm.nl/nl/toegankelijkheid/toegankelijkheid-van-e-handelsdiensten-en-elektronische-communicatiediensten) beschrijft ook uitzonderingen; de ondernemingsomvang is hier niet geverifieerd.

## G. Design en mobiel

De actuele afspraak is leidend: desktop vanaf 992 px gebruikt de beschikbare breedte en 400 px hoogte; mobiel blijft de bestaande 5:2-presentatie. Een eerdere 1000×400-wens is niet als nieuwe vaste desktopbreedte toegepast. Geen CSS, HTML of beeldbestand is tijdens deze audit veranderd.

| Viewport px | Waarnemingen NL+EN | Herobreedte px | Herohoogte px | Overflow | Kapotte img |
| --- | --- | --- | --- | --- | --- |
| 320 | 16 | 300.0–300.0 | 120.0–120.0 | 0 | 0 |
| 375 | 16 | 340.0–340.0 | 136.0–136.0 | 0 | 0 |
| 390 | 16 | 347.2–347.2 | 138.9–138.9 | 0 | 0 |
| 430 | 16 | 387.2–387.2 | 154.9–154.9 | 0 | 0 |
| 768 | 16 | 712.8–712.8 | 285.1–285.1 | 0 | 0 |
| 844 | 16 | 788.8–788.8 | 315.5–315.5 | 0 | 0 |
| 1024 | 16 | 968.8–968.8 | 400.0–400.0 | 0 | 0 |
| 1366 | 16 | 1303.2–1303.2 | 400.0–400.0 | 0 | 0 |
| 1920 | 16 | 1460.0–1460.0 | 400.0–400.0 | 0 | 0 |

Geteste hero’s: Home, Smart Home, Beauty & Care, Home & Living, Lifestyle & Sport, Gadgets, Shop en Aanbiedingen. De extra 844×390-test is een landschapsviewport; 768 px dekt tabletportrait, 1024 px een tablet/kleine desktop. Dit is browseremulatie op dezelfde Chromiumomgeving, geen test op fysieke iOS-/Android-/Safariapparaten. Browserzoom 200%/400% en OStekstvergroting zijn niet systematisch uitgevoerd.

Op 1366 px bedraagt de hoofdvlak-/herobreedte ongeveer 1303 px; op 1920 px 1460 px. De hero vult dit vlak: de resterende buitenruimte op zeer brede schermen komt uit de template-maxbreedte, niet uit witte/zwart opgevulde heroafbeeldingen. Als later echt rand-tot-rand voor 1920 wordt gewenst, is dat een aparte ontwerpbeslissing met gevolgen voor alle inhoud. Nu is niets aangepast.

| Pagina/type | Bevinding | Vervolg |
| --- | --- | --- |
| Home + categorieën | Leesbare native desktopcopy en eigen sfeerbeeld; vijf categorieën aanwezig. Mobiele afbeeldingscopy klein. | Behouden; NV19 alleen na aparte afstemming mobiel. |
| Shop | 100 producten, categorie-ingangen, zoekfunctie. Engelse zoekkop/emptytext onvolledig. | NV18; zoek-/filterstate consistent houden. |
| Aanbiedingen | Correcte lege toestand, geen verzonnen geverifieerde deals; heroCTA naar sectie. | Behoud eerlijkheid; pas NV28 later toe. |
| Productdetail | Titel, prijs, voorraaduitleg en gerelateerde producten aanwezig; voorlopige data en illustratie. | NV02; echte varianten/beelden en logistieke gegevens. |
| Account | Login-/registertabs schakelen; wachtwoordzichtbaarheid aanwezig. Engelse herhaaltekst Nederlands. | NV05/NV06/NV18; nog geen order-/adresdashboard. |
| Wishlist/cart | Toggles en aantallen werken; veilige ID/qty-cookie. Browsergebonden favorieten. | NV05/NV27; duidelijke voortgang naar echte checkout. |
| Checkout | Formlabels aanwezig; teststatus duidelijk; verzending later en kleine actietekst. | NV01/03/10/21. |
| Contact/FAQ/Meer | Renderen zonder horizontale overflow; contact blijft afhankelijk van mailconfiguratie. | NV11 en juridische contactgegevens. |
| Info/legal | NL/EN documentstructuur aanwezig; praktische gegevens zijn voorbereidende uitleg. | NV04/NV16. |
| Admin | Alleen anoniem visueel gezien (503 bij ontbrekende hash); ingelogde routes met synthetische testclient 200. | Geen visuele volledige adminconformiteit claimen; NV07 en dashboardcampagnes later. |

Bewijsbeelden staan naast dit rapport: `audit-desktop-smart-home.jpg`, `audit-desktop-shop.jpg`, `audit-mobile-390.jpg`, `audit-checkout-engels.jpg` en `audit-menu-mobile.jpg`. Het mobiele beeld is een lokale auditopname, geen wijzigingsvoorstel. In het screenshot kunnen alleen fictieve auditgegevens staan. Toegankelijkheidsrichting: [WCAG 2.2](https://www.w3.org/TR/2023/REC-WCAG22-20231005/) voor tekst, focus en bediening; [targetminimum en uitzonderingen](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum). Geen volledig WCAG-oordeel op basis van alleen een overflow-/labelcheck.

## H. Accounts, checkout en betalingen

| Flow | Uitgevoerd resultaat | Beperking/ID |
| --- | --- | --- |
| Registratie | Fictieve klant aangemaakt, 303, sessie gekoppeld; dubbele e-mail 400; wachtwoordbevestiging afgedwongen. | Alleen geïsoleerde SQLite; geen echte mail. NV06. |
| Inloggen/uitloggen | Succesvol; andere client ziet geen naam; SQLstring authenticeert niet; 9e mislukte poging 429. | Mandje verdwijnt na login. NV05/NV12. |
| Herstel/verificatie | Functies/routes niet aanwezig. | Niet als geslaagd beschouwen; NV06. |
| Zoeken | Browserzoekterm lamp geeft 8 resultaten; onbekende term geeft 0 en lege toestand. | Gemengde taal in EN, NV18; geen relevantie-/synoniemgarantie. |
| Product → mandje | Browserknop voegt één item toe, €24,95. Testclient add/change geslaagd. | Catalogusprijzen voorlopig, NV02. |
| Mandje → checkout | Browserformulier bekeken; testclient checkout geeft testbevestiging 200. | Geen echte order/betaling/klantbevestiging. NV01/03. |
| Validatie | E-mail en consent afgedwongen, ontbrekende/foute CSRF en vreemde Origin geblokkeerd. | Land/postcode onvoldoende. NV10. |
| Reviews | Correcte consent-POST 303, pending verborgen; 1 ster mogelijk; HTMLescaping; SSOreplay 403. | Eerste helper gebruikte verkeerde consentwaarde en kreeg ongeldig; gecorrigeerde extra test is leidend. NV07/13/26. |
| Contact | 503 zonder mailconfiguratie, geen vals succes. | Geen bezorgbaarheidstest of extern bericht. NV11. |
| Beheer | Synthetische adminlogin geslaagd; acht adminleesroutes 200. | Geen echte beheercredentials, supplier-/payment-/providerwijziging. NV07. |
| Betaling/terugbetaling | Niet uitgevoerd. | Productie-API’s, provider-dashboard en transacties bewust niet benaderd. NV01. |

E-mailverificatie is niet in alle webshopmodellen op zichzelf een wettelijke vereiste; zij is hier wel een betrouwbaarheids- en fraudevoorwaarde voor persoonlijke uitgifte. Een registratieprivacytoelichting is nodig; een verplichte algemene “AVGtoestemming” is geen universele vervanging voor een passende grondslag. Er is geen automatisch bewijs van account-orderisolatie zolang de orderfunctie ontbreekt.

## I. SEO, performance en beveiliging

### Reikwijdte en meetresultaten

De 143 requests zijn met Flask test_client tegen de bronkopie gedaan, met externe I/O geblokkeerd. Mediaan serverrendering: 16.73 ms; maximum 389.44 ms, inclusief lokale initialisatie/caches. Dit meet geen internet-TTFB, DNS, TLS, mobiele CPU of echte hosting. Geen Lighthouse-score, veld-LCP/INP/CLS of Core Web Vitals verzonnen; die moeten later op de gekozen deployment en echte bezoekersgegevens worden gemeten. Ook geen volledige crossbrowser- of loadtest.

Alle succesvolle HTMLdocumenten in de crawl hebben één H1. Alle actieve `.html`templates compileren; historische backups zijn geen actieve bewijsbasis. Van 257 gecontroleerde lokale link-/assetURL’s gaf geen één 4xx/5xx. Bewust onbestaande routes en oningestelde adminlogin zijn apart gecategoriseerd. Externe domeinlinks/afbeeldingen zijn niet live doorgelopen. De browserconsole gaf in de opgevraagde reeks geen errors; dit is geen onbeperkte netwerk-/consoletrace voor iedere route.

### SEO

Titels, descriptions, canonicals, robots en sitemap bestaan. Productdetail bevat Product/Offer en BreadcrumbList JSON-LD; onbekende voorraad wordt niet als InStock ingevuld, wat goed is. De catalogus blijft inhoudelijk voorlopig en de schemawaarden zijn daarom geen Merchantvrijgave. Product-OGafbeelding kan relatief zijn terwijl een openbare crawler een absolute URL nodig heeft; normaliseer en valideer op de uiteindelijke host. Productmeta is vooral NL, terwijl clienttaal EN kan worden. Domein-/sitemap-/taalstrategie: NV17/NV18. Privébeheer heeft noindex; /account is als gepersonaliseerd scherm ook expliciet op indexatie/caching te beoordelen. Robots is geen toegangsbeveiliging. Geen Search Console/Googlecrawlstatus gecontroleerd.

### Veiligheid

Positief getest: CSRF, Origincheck, scrypt, SQLparameterbinding, loginlimiet, bodylimiet (70 KB → 413), anonieme beheermutaties geweigerd of route/methode niet beschikbaar, reviewescaping, eenmalige SSO en geen klantadres in de sessiecookie. Geen algemene “geen XSS/SQLi mogelijk”-garantie. Uploadmogelijkheid is een UTF-8 CSVpreview met 60 KB/150-regelgrens en formaatvalidatie; deze publiceert niets. De controle is geen antivirus-, volledige fuzz- of productveiligheidscontrole.

Prioriteiten: NV07–09, NV12–16, NV24–26 en NV30. Secure/HttpOnly/SameSite staan in de bron; Secure is alleen voor de geïsoleerde HTTPaudit uitgeschakeld. De echte TLSterminatie, proxytrust, secretrotatie en livecookieheaders zijn niet operationeel geverifieerd. Geen wachtwoorden, tokens of geheime waarden opgenomen. Een beperkte credentialpatroonscan vond geen hardcoded sleutelmatches; dit sluit geheimen in gitgeschiedenis, ondoorzichtige bestanden, omgevingen of andere patronen niet uit.

Versiebronnen: [Pallets Flask GHSA-68rp-wp8r-4726](https://github.com/pallets/flask/security/advisories/GHSA-68rp-wp8r-4726) meldt een Vary:Cookie-probleem vóór 3.1.3 met specifieke cachevoorwaarden; lokaal 3.1.2. [Pallets Werkzeug GHSA-g6x2-hccm-hh4m](https://github.com/pallets/werkzeug/security/advisories/GHSA-g6x2-hccm-hh4m) meldt het Windows/NTFS device-nameprobleem vóór 3.1.9; lokaal 3.1.8. Niet exploiteren: update en test gecontroleerd. Voor Gunicorn 23.0.0 is in deze audit geen volledige machineleesbare CVEscan van alle transitieven uitgevoerd; een lege advisoriesweergave bewijst geen afwezigheid van risico.

Tijdens het afsluiten van de geïsoleerde auditserver waren in diens requestlog herhaalde GET-aanvragen voor `/products.json` met 404 zichtbaar. Die URL is ook als 404 in de negatieve crawlset opgenomen. De initiator van deze browser-/scriptrequests is niet definitief vastgesteld; de zichtbare servergerenderde catalogus werkte wel. Neem een toekomstige DevTools-networktrace met initiator op voordat een oorzaak of reparatie wordt gekozen. Een lege console-opvraag sluit deze netwerkfouten dus niet uit.

### Bestaande testfouten precies duiden

| Mislukte test | Beoordeling |
| --- | --- |
| tests/test_control.py::test_control_page_exists | Verouderd: verwacht 200 op beschermd /control; gemeten 302 is de bedoelde bescherming. |
| tests/test_control.py::test_core_customer_pages_render | Verouderd: over-trendmix hoort nu 301 naar over-nuvemixa. |
| tests/test_control.py::test_cart_and_checkout_test_flow | Verouderde literal “Testmodus”; huidige teststatus wordt anders uitgelegd. Deze test stopt vóór latere assertions. |
| tests/test_control.py::test_rankfix_audit_canonicals_and_meta_descriptions | Canonicalverwachting en gemengde hoststrategie toetsen; deels echte consistentiebevinding NV17. |
| tests/test_control.py::test_global_language_dropdown_is_present_across_storefront | Verwachting van oude taal-/dropdownstructuur; huidige UI biedt NL/EN. Niet automatisch talen terugbouwen. |
| tests/test_control.py::test_original_category_menu_and_svg_icons_survive_redesign | Verwacht oude markup; actuele menubediening afzonderlijk browsergetest, Escapebevinding NV20. |
| tests/test_control.py::test_information_pages_have_professional_bilingual_content | Stopt bij oude over-trendmix status200; informatie bestaat en redirect is gewenst. |
| tests/test_performance.py::test_shared_cart_footer_and_ai_trendmix_remain_everywhere | Verouderde merkverwachting “AI TrendMix”; NUVEMIXA is gewenst. |

De 37 eerste functionele helperchecks bevatten ook capabilityprobes (bijvoorbeeld ontbrekende accountfuncties), geen 37 gegarandeerde producteisen. Een eerste reviewhelperpost gebruikte een verkeerde consentwaarde; de gecorrigeerde extra check bewijst het normale submitpad. De aanvullende scriptverwachtingen zijn gecontroleerd: 403 is een geldige CSRFafwijzing en 405 een methodeafwijzing. Alleen de ontbrekende account-no-store bleef van de 19 extra checks als bevinding over. De bestaande pytestbestanden zelf zijn ongewijzigd uitgevoerd, in dezelfde geïsoleerde suite na synthetische beheerconfiguratie; dit is geen exacte productie-envreproductie.

## J. Kortingscampagne

**Nog niets gebouwd of geactiveerd.** Aanwezig als bouwstenen: klant-ID/e-mail, servercart met catalogusprijzen, beheerlogin, reviewmoderatie, optionele SMTP/Resend en read-only Woo/Mollievoorbereiding. Niet aanwezig: coupons, campaign-/redemptiontabellen, e-mailuitgifte, aankoopgebonden reviewuitnodiging, actieve-datumlogica, dashboardcampagnebeheer of een gedeelde databron tussen extern dashboard en deze shop. De review-SSO bewijst alleen een loginverbinding; geen gesynchroniseerde kortingsconfiguratie.

| Wens | Benodigde definitie en techniek | Acceptatiecriterium |
| --- | --- | --- |
| 15% welkom | Na e-mailverificatie unieke onvoorspelbare code, gehashte opslag, klant-ID, campagne-ID en status. Mail via outbox met retries/idempotentie. Geen algemeen herbruikbare WELKOM15. | Één uitgifte per daarvoor in aanmerking komende klant; retry verstuurt geen extra coupon; alleen eigenaar gebruikt code. |
| 20% eerlijke review | Uitnodiging na echte geschikte afgeronde aankoop; token aan order/klant; beloning los van sterren en publicatiebeslissing; incentive herkenbaar. | 1 ster en 5 sterren dezelfde voorwaarden; dubbele review/token levert nooit een tweede code; geen aankoop geeft geen beloning. |
| Dashboard | Campagne start_at/end_at, tijdzone, percentage, minimum, maximumkorting indien gewenst, uitsluitingen, doelpubliek, status, banner-NL/EN en auditlog. | Bevoegde beheerder ziet preview en historie; shop en dashboard lezen dezelfde gevalideerde versie. Geen alleen localStoragebeheer. |
| Tijdgebonden banner | Compact gedeeld component op relevante klantpagina’s, serverzijdig actieve campagne; cache houdt rekening met einddatum. | Automatisch onzichtbaar bij eindtijd, ook cache-/herlaad-/taal-/mobielscenario; geen permanente verlopen claim. |
| Eenmaligheid | Atomische reservering/redemption bij ordercreatie of betaling met expliciete timeout-/cancelregels en unieke databaseconstraints. | Twee gelijktijdige checkouts met dezelfde code kunnen niet beide afrekenen met korting. |
| Minimum/uitsluitingen | Definieer inclusief/exclusief btw, vóór/na korting, wel/geen verzending, categorie/SKU/actieprijsuitsluiting en stapelbeleid. | Exact dezelfde serverregels in mandje, checkout, order, mail en betaalprovider; clientwijziging heeft geen invloed. |
| Btw/refund | Centen/Decimal, consistente verdeling per orderregel en btwgroep, gedeeltelijke retour en kortingscodeherstelbeleid. | Orderregels en providerbedrag gelijk; refund nooit boven betaald bedrag; beleid vooraf duidelijk. |
| Misbruik | Klantbinding, geverifieerd e-mailadres, centrale limieten en auditlog; proportionele controles op dubbele accounts. | Geen onnodige gevoelige data verzamelen; blokkades uitlegbaar en herstelbaar. |
| E-mail/voorwaarden | Transactionele uitgifte versus marketing juridisch beoordelen; duidelijke geldigheid en afmelding waar toepasselijk. | Consent-/grondslagbewijs en voorwaardenversie beschikbaar; geen belofte van positieve review of verplichte publicatie. |

Voorgesteld gegevensmodel voor latere bespreking: campaigns, coupons, coupon_redemptions, orders/order_lines, review_invitations en mail_outbox met gedeelde klant-/order-ID’s. Dit is een ontwerpaanbeveling, geen uitgevoerde migratie. Beslis eerst of WooCommerce of een eigen orderdienst de leidende bron wordt; dubbele onafhankelijke couponadministraties zijn een risico. Een aparte externe dashboard-API vereist scopecontrole, authenticatie, versiebeheer, foutafhandeling en een aantoonbare synchronisatiebron. Niet automatisch verbinding maken met Render/Neon/Alwaysdata.

## K. Verbeterplan

Voorgestelde volgorde: (1) commerciële grenzen en bron van orders/producten vastleggen, (2) P0-keten in sandbox uitwerken, (3) identiteit/privacy/security en accountcontinuïteit, (4) betrouwbare e-mails/retouren en pas daarna campagnes, (5) SEO/i18n/performance/toegankelijkheid en CI. Alle wijzigingen horen in een volgende expliciete reparatieopdracht; deze audit stopt bij het plan.

Complexiteit is relatief: klein = beperkt bestand/beleid, middel = meerdere componenten en regressiechecks, groot = nieuwe keten met data/externe afhankelijkheden. Geen ongefundeerde uren- of kostenbelofte. Exacte locatie, risico en hertest staan per ID in C/D.

| Prioriteit | ID | Werkpakket | Complexiteit |
| --- | --- | --- | --- |
| P0 | NV01 | Commerciële bestel- en betaalstraat ontbreekt | Groot |
| P0 | NV02 | Catalogus is een voorlopige demonstratie | Groot |
| P0 | NV03 | Totale verkoopprijs en rechtsgeldige bestelstap zijn niet gereed | Groot |
| P0 | NV04 | Bedrijfsidentiteit en operationele consumentenprocessen ontbreken | Groot |
| P1 | NV05 | Inloggen en registreren wissen winkelwagen en favorieten | Middel |
| P1 | NV06 | Accountlevenscyclus en orderkoppeling onvolledig | Groot |
| P1 | NV07 | Review-SSO geeft algemene beheerstatus | Middel |
| P1 | NV08 | Afhankelijkheden vallen binnen actuele beveiligingsmeldingen | Klein tot middel |
| P1 | NV09 | Accountpagina mist expliciete private caching | Klein |
| P1 | NV10 | Adresvalidatie wijkt af van EU-bezorgbelofte | Middel |
| P1 | NV11 | E-mailketen is geen bevestigde klantcommunicatie | Groot |
| P1 | NV12 | Registratie-, contact- en loginmisbruik onvoldoende centraal beheerst | Middel |
| P1 | NV13 | Reviewverificatie en toekomstige beloning hebben geen aankoopbewijs | Groot |
| P1 | NV14 | Sessiesleutel en opslag vereisen een bewezen productieconfiguratie | Middel |
| P1 | NV15 | Publiek bereikbaar ondoorzichtig binair bestand | Klein voor onderzoek, vervolg afhankelijk van inhoud |
| P1 | NV16 | Privacytekst en feitelijke verwerking moeten worden afgestemd | Middel |
| P2 | NV17 | Canonical-, sitemap- en taalstrategie inconsistent | Middel |
| P2 | NV18 | Engels is niet volledig en metadata wisselt niet overal mee | Middel |
| P2 | NV19 | Mobiele hero-informatie zit vooral in een afbeelding | Middel |
| P2 | NV20 | Menu sluit in gemeten mobiele flow niet met Escape | Klein tot middel |
| P2 | NV21 | Kleine actietekst en contrast vragen gerichte toegankelijkheidscontrole | Middel |
| P2 | NV22 | Zware hero-preload en veel gestapelde assets | Middel |
| P2 | NV23 | Tests en CI sluiten niet meer volledig aan op huidige shop | Middel |
| P2 | NV24 | Registratie van routes hangt af van startmethode | Klein |
| P2 | NV25 | CSP is alleen rapporterend; inline-uitvoering blijft breed | Middel |
| P2 | NV26 | Reviewlimieten vertrouwen ongefilterde proxyheader en losse transacties | Middel |
| P2 | NV27 | Favorieten zijn browsergebonden en geen accountfunctie | Middel |
| P2 | NV28 | Kortingscampagnes ontbreken als functionele keten | Groot |
| P2 | NV30 | AI-verbruiksopslag is niet zelfstandig reproduceerbaar in deze checkout | Middel |
| P3 | NV29 | Interne oude merknamen en historische bestanden vragen gecontroleerd onderhoud | Middel |
| P3 | NV31 | Valutaberekening gebruikt floats | Middel |

## L. Definitieve checklist

- [ ] Verkoper, scope, verkooplanden en leidende product-/orderbron vastgesteld.
- [ ] Alle te verkopen SKU’s geverifieerd op echte data, beelden, veiligheid, prijs/btw, voorraad en levertermijn.
- [ ] Volledige order-/provider-sandboxketen inclusief annuleren, mislukken, dubbele events, retour en refund geslaagd.
- [ ] Totale prijs vóór koop bekend; definitieve betaalplicht en orderbevestiging juridisch gecontroleerd.
- [ ] Identiteit, voorwaarden, privacy/cookies, levering, garantie en klachten definitief en actueel; juridische controle afgerond.
- [ ] Modelformulier, online ontbindingsfunctie, retouradres en ontvangstbevestiging operationeel en gasttoegankelijk.
- [ ] Login behoudt bedoelde cart/wishlist; herstel/verificatie en klant-orderisolatie bewezen.
- [ ] Review-SSO op juiste scope, keys afgeschermd, centrale misbruikpreventie en adminrollen getest.
- [ ] Flask/Werkzeug en transitieve packages gecontroleerd/gepatcht; private caching en CSPtraject getoetst.
- [ ] Onbekend staticbestand onderzocht en publicatiebesluit gedocumenteerd.
- [ ] Mailafzender/DNS, templates, foutafhandeling en retries getest zonder ongewenste liveberichten.
- [ ] Consistente canonicals/sitemap/OG/taalindexatie; staging afgeschermd en geen localhost in productie-uitvoer.
- [ ] NL/EN-klantreis inclusief fouten, registratie en zoek-emptytext volledig.
- [ ] Hero’s opnieuw vergeleken met goedgekeurde huidige desktop én mobiel; geen ongewenste mobiele wijziging.
- [ ] Toetsenbord, Escape/focus, contrast, tekstzoom en relevante fysieke browsers/devices gecontroleerd.
- [ ] Productieperformance gemeten op echte deployment/netwerkprofielen; Core Web Vitals alleen met geldig meetbewijs.
- [ ] Tests bijgewerkt naar actuele eisen, geen lege testcollectie; alle betekenisvolle checks groen.
- [ ] Persistente opslag, migraties, retentie, back-up, herstel en monitoring aantoonbaar operationeel.
- [ ] 15%/20% alleen na goedgekeurd ontwerp, eerlijke reviewvoorwaarden, serverberekening en eenmalige uitgifte/redemption.
- [ ] Beperkte, expliciet geautoriseerde productievrijgave met rollbackplan; geen automatische deployment vanuit deze audit.

### Bijlage 1 — Alle runtime-routeregels

Dynamische routes zijn als patronen opgenomen; de 100 concrete productdetails staan in de afzonderlijke crawl. Een routespecifieke POST betekent geen toestemming die op productie uit te voeren. GET/HEAD/OPTIONS zijn uit het Flaskregister overgenomen; administratieacties met externe effecten zijn alleen in bron of met fakeconfiguratie onderzocht.

| Route | Methoden | Endpoint |
| --- | --- | --- |
| /static/<path:filename> | GET, HEAD, OPTIONS | static |
| / | GET, HEAD, OPTIONS | home |
| /shop | GET, HEAD, OPTIONS | shop |
| /aanbiedingen | GET, HEAD, OPTIONS | deals |
| /products | GET, HEAD, OPTIONS | products_page |
| /account | GET, HEAD, OPTIONS | account |
| /account/register | OPTIONS, POST | customer_register |
| /account/login | OPTIONS, POST | customer_login |
| /account/logout | OPTIONS, POST | customer_logout |
| /wishlist | GET, HEAD, OPTIONS, POST | wishlist |
| /cart | GET, HEAD, OPTIONS | cart |
| /product/<int:product_id> | GET, HEAD, OPTIONS | product |
| /admin/login | GET, HEAD, OPTIONS, POST | admin_login |
| /admin/logout | OPTIONS, POST | admin_logout |
| /admin/merchant-preview | GET, HEAD, OPTIONS | admin_merchant_preview |
| /admin/research-preview | GET, HEAD, OPTIONS | admin_research_preview |
| /admin/integrations | GET, HEAD, OPTIONS | admin_integrations |
| /admin/suppliers | OPTIONS, POST | admin_add_supplier |
| /admin/research | OPTIONS, POST | admin_add_research_note |
| /admin/rankfix/open | GET, HEAD, OPTIONS | admin_rankfix_open |
| /admin/mollie/check | GET, HEAD, OPTIONS | admin_mollie_check |
| /admin/merchant-feed-preview.xml | GET, HEAD, OPTIONS | admin_merchant_feed_preview |
| /admin/supplier-feed-preview | OPTIONS, POST | admin_supplier_feed_preview |
| /catalogus-overzicht | GET, HEAD, OPTIONS | control |
| /dashboard | GET, HEAD, OPTIONS | control |
| /control | GET, HEAD, OPTIONS | control |
| /<category_slug> | GET, HEAD, OPTIONS | category_page |
| /<category_slug>/<subcategory_slug>/ | GET, HEAD, OPTIONS | subcategory_page |
| /product/<category_slug>/<int:product_index> | GET, HEAD, OPTIONS | legacy_product_detail |
| /<category_slug>/<product_slug> | GET, HEAD, OPTIONS | product_detail |
| /<category_slug>/<subcategory_slug>/<product_slug> | GET, HEAD, OPTIONS | legacy_product_url |
| /winkelwagen | GET, HEAD, OPTIONS, POST | winkelwagen |
| /afrekenen | GET, HEAD, OPTIONS, POST | afrekenen |
| /faq | GET, HEAD, OPTIONS | faq |
| /meer | GET, HEAD, OPTIONS | nuvemixa_more |
| /contact | GET, HEAD, OPTIONS | contact_page |
| /contact | OPTIONS, POST | contact |
| /over-trendmix | GET, HEAD, OPTIONS | over_trendmix |
| /over-nuvemixa | GET, HEAD, OPTIONS | over_trendmix |
| /bestellen | GET, HEAD, OPTIONS | bestellen |
| /privacy | GET, HEAD, OPTIONS | privacy |
| /retouren | GET, HEAD, OPTIONS | retouren |
| /voorwaarden | GET, HEAD, OPTIONS | voorwaarden |
| /cookies | GET, HEAD, OPTIONS | cookies |
| /img/product/<category_slug>/<product_slug>.svg | GET, HEAD, OPTIONS | product_art |
| /robots.txt | GET, HEAD, OPTIONS | robots |
| /sitemap.xml | GET, HEAD, OPTIONS | sitemap |
| /api/trendmix-assistant | GET, HEAD, OPTIONS, POST | trendmix_assistant |
| /reviews | OPTIONS, POST | submit_customer_review |
| /admin/reviews | GET, HEAD, OPTIONS | admin_reviews |
| /admin/reviews/<int:review_id> | OPTIONS, POST | admin_update_review |
| /admin/reviews/sso | GET, HEAD, OPTIONS | nv_reviews_sso_ontvang |

### Bijlage 2 — Informatiedocumenten

| Document | NLtitel | ENtitel | Aantal secties NL/EN |
| --- | --- | --- | --- |
| bestellen.json | Bestellen & levering | Ordering & Delivery | 9/9 |
| cookies.json | Cookies en privacyvoorkeuren | Cookies and Privacy Preferences | 9/9 |
| over-trendmix.json | Over NUVEMIXA | About NUVEMIXA | 7/7 |
| privacy.json | Privacyverklaring — verwerking en bescherming van gegevens | Privacy Policy — Personal Data and Security | 11/11 |
| retouren.json | Consumentenrechten, retourneren & herroeping | Consumer Rights, Returns & Withdrawal | 9/9 |
| voorwaarden.json | Algemene voorwaarden — informatie en voorbereiding | Terms and Conditions — Information and Preparation | 12/12 |

### Bijlage 3 — Testbewijs en integriteit

Bij de eindvergelijking is één verschil aangetroffen buiten broncode/data: het reeds draaiende lokale proces heeft tekst toegevoegd aan `NUVEMIXA-LOKALE-TEST/hero-desktop-fullwidth-backup-20261123/server-error.log`. De bestaande logprefix heeft dezelfde hash; het betreft uitsluitend aangevulde runtime-uitvoer. Deze audit heeft het log niet bewerkt of teruggezet. Alle overige gehashte bestanden, inclusief code, templates, beelden, klantdatabase en SSOopslag, zijn identiek gebleven. Het gevraagde nieuwe rapport is apart uitgesloten van de bronvergelijking.

Naast dit rapport staat `NUVEMIXA-auditbewijs.json` met de gestructureerde resultaten en `NUVEMIXA-TrendMix-inventaris.csv` met de volledige merkzoeklijst. Bronhashes zijn intern vóór/na vergeleken; geheime sleutelinhoud en echte klanttabellen zijn niet in de deliverables opgenomen. Geen bestand verwijderd. Geen commit, push, merge, deploy of productiebetaling uitgevoerd. Alleen het gevraagde auditrapport wordt in de werkmap toegevoegd; de kopie en bewijsbestanden staan in de Codex-outputsmap. De auditserver gebruikt uitsluitend de aparte kopie en fictieve database. Bestaande gebruikerswijzigingen zijn niet teruggedraaid.

Audit afgerond. Geen webshopbestanden gewijzigd. Klaar om samen het verbeterplan te bespreken.

