# NUVEMIXA — lokale herstelronde, 23 november 2026

De lokale webshop is uitgebreid en getest. **Commerciële verkoop is nog geblokkeerd.** Echte leveranciers, bedrijfsgegevens, mailbezorging en een betaalprovider zijn nog niet geaccepteerd. De simulatie is bruikbaar voor een afzonderlijke functionele acceptatie; zij bewijst geen werkende productiebetaling of juridische conformiteit.

Werkmap: `C:\Users\user\NUVEMIXA-WERKKOPIE`. Geïsoleerde preview: `C:\Users\user\NUVEMIXA-LOKALE-TEST`, bereikbaar op `http://127.0.0.1:5001`. Gebruik de lokale launcher volgens `LOKAAL-GEBRUIK-EN-ACCEPTATIE.md`. De tijdelijke beheerlogin staat uitsluitend in `.repair-state/local-admin.txt` van de testmap. Geen wachtwoord is in dit rapport opgenomen.

## Behouden en afgeschermd

Herstelpunt: `herstelpunten/voor-afwerking-20261123-165244`, inclusief oorspronkelijke bestanden, manifest en oorspronkelijke Git-status. Geen commits, pushes, merges, livewijzigingen of deployments uitgevoerd. Alwaysdata, Render, Neon en Vercel zijn niet operationeel verbonden.

37 bestaande hero-/ontwerpbestanden, inclusief de originele hero-CSS en het bevestigde headerlogo, zijn met het herstelmanifest vergeleken: **geen gewijzigde hashes**. De bestaande klantdatabase, SSO-secret en SSO-noncedatabase hebben eveneens ongewijzigde hashes ten opzichte van de audit. Er zijn geen echte klantgegevens of secrets naar de testdatabase gekopieerd. Nieuwe PWA-iconen zijn afgeleid van het door de eigenaar bevestigde `static/nuvemixa-logo-test.png`; het bronlogo is behouden.

De paarse actiepreview is na afstemming compacter gemaakt. De gehele banner verwijst naar `/account#registreren`. Alleen een actieve welkomstcampagne binnen de actiedatums maakt haar openbaar zichtbaar. Het reviewgedeelte vereist daarnaast een actieve reviewcampagne. De beheerpreview activeert niets. **Beide campagnes staan uit.** De eigenaar activeert later zelf; er zijn geen echte kortingsmails verstuurd.

Het daarna goedgekeurde tweede ontwerp is lokaal toegepast: “Welkom bij NUVEMIXA”, een gele actieknop “Ontvang 15% korting” en de reviewkorting kleiner rechts. Gemeten desktophoogte circa 128 px. Aanvullend 10 campagne-/account-/coupontests geslaagd, plus NL/EN-browsercontrole op 320, 390, 768, 1366 en 1920 px zonder horizontale overloop. De klik opent de registratietab; de openbare pagina toont geen banner zolang de campagne uitstaat. Screenshot: `eindcontrole-20261123/kortingsbanner-ontwerp-2-lokaal.jpg`.

## Status NV01–NV31

“Lokaal opgelost” betreft de onderzochte lokale werking. “Voorbereid” vereist configuratie en afzonderlijke acceptatie; “geblokkeerd” betekent dat noodzakelijke gegevens of operationele techniek ontbreken.

| Bevinding | Status en resultaat | Resterende grens |
|---|---|---|
| NV01 bestel-/betaalketen | Lokaal opgelost als simulatie: orderregels, statussen, idempotentie, annulering, timeout, refunds en historie. | Echte provideradapter en providerwebhook ontbreken; liveverkoop geblokkeerd. |
| NV02 voorbeeldcatalogus | Publicatiestroom, leveranciersevidence, SKU, btw, voorraad, beelden en veiligheidsvelden voorbereid. Voorbeelden herkenbaar. | Eigenaar levert geverifieerde producten. Varianten zijn registreerbaar maar verkoop blijft geblokkeerd totdat selectie/voorraad per variant apart is gebouwd en geaccepteerd. |
| NV03 definitieve totaalprijs | Centen/Decimal, btw, korting en verzendkosten vooraf berekend in simulatie. | Werkelijke tarieven, belastinginrichting en betaalplichtige productiecheckout nog niet geaccepteerd. |
| NV04 identiteit/consumentenprocessen | Gemarkeerde juridische concepten, gast-herroeping, ontvangstregistratie en testbevestiging gebouwd. | Verkoper, KvK/btw, retouradres, voorwaarden en operationele afhandeling ontbreken. |
| NV05 mandje bij authenticatie | Lokaal opgelost: mandje behouden bij registratie en login; favorieten gekoppeld. | Geen productieclaim. |
| NV06 accountlevenscyclus | Verificatie, eenmalig herstel, sessie-intrekking, profiel/adres, private orders en testberichten gebouwd. | Externe afleverbaarheid ontbreekt. |
| NV07 review-SSO | Lokaal opgelost: afzonderlijke reviewrol; geen algemene beheerstatus. | Productie-SSO-hostingacceptatie apart. |
| NV08 dependencies | Getest met Flask 3.1.3 en Werkzeug 3.1.9; versies vastgelegd in requirements.lock. | Geen volledige transitive-CVE- of productie-infrastructuuraudit. |
| NV09 private caching | Lokaal opgelost: account/orders/beheer e.d. private/no-store en noindex. | CDN/proxy in productie apart toetsen. |
| NV10 adres/landen | Servervalidatie en native keuzelijst NL/BE. Oud overschrijvend script gecorrigeerd. | Andere EU-landen pas na echte logistieke configuratie. |
| NV11 klantmail | Lokale postbus, NL/EN-berichten en afgeschermde SMTP-adapter voorbereid. | Geen automatische dispatcher, DNS-/domein-/afleveracceptatie of externe mail uitgevoerd. Testberichten worden nooit achteraf verstuurd. |
| NV12 misbruik | Centrale SQLite-limieten voor relevante formulieren; requestgrenzen. | Gedistribueerde productiebelasting en proxyconfiguratie apart toetsen. |
| NV13 reviews | Ordergebonden uitnodiging, eenmalige beloning, dezelfde korting voor 1/5 sterren; moderatiereden vereist. | Simulatiereviews worden geen echte geverifieerde reviews. Echte aankoopbron en communicatiegrondslag ontbreken. |
| NV14 secrets/opslag | Stabiele lokale sleutel, verplichte productie-secret, private opslagpaden, backup/herstel naar nieuw bestand getest. | Hostingrechten, retentie, encryptie en bedrijfsbrede recovery nog vaststellen. |
| NV15 onbekend binair bestand | Met behoud van hash naar private quarantaine verplaatst; publieke route geblokkeerd. | Niet ontsleuteld of uitgevoerd; herkomst/inhoud niet definitief vastgesteld. |
| NV16 privacy | Conceptteksten en ontbrekende gegevens gemarkeerd; echte verzending/AI uitgeschakeld. | Verantwoordelijke, grondslagen, ontvangers, retentie en marketingtoestemming juridisch/operationeel afronden. |
| NV17 SEO | Canonical-origin, sitemap, 301, taalmetadata en absolute OG-afbeeldingen hersteld; demo-aanbodschema verwijderd. | Definitief HTTPS-domein en externe indexatieacceptatie ontbreken. |
| NV18 NL/EN | Serververtaling, metadata en één taalcontroller; publieke pagina’s en nieuwe klantflows gecontroleerd. | Geen garantie op volledige vertaling van iedere historische of externe beheer-/providertekst. |
| NV19 mobiele afbeeldingscopy | Goedgekeurde hero-afbeeldingen bewust behouden; geen nieuw mobiel ontwerp. | Volledige toegankelijkheid van tekst ín afbeeldingen blijft open voor afzonderlijke ontwerpacceptatie. |
| NV20 Escape | Lokaal opgelost: menu sluit en focus keert terug naar menu. | Fysieke hulpmiddelen apart toetsen. |
| NV21 leesbaarheid | Nieuwe formulieren/prijzen/knoppen/focus verbeterd; geen gemeten horizontale overloop. | Geen volledige WCAG 2.2 AA-, contrast-, screenreader- of browserzoomconformiteitsverklaring. |
| NV22 performance | Mobiele PNG-preloads beperkt tot mobiel; oude blokkerende constructies verwijderd. Originele hero’s behouden. | Hero-bestanden blijven zwaar; geen productie-CWV- of veldmetingen. |
| NV23 tests/CI | Werkelijke pytest-collectie en actuele regressies; lockfile voor CI-installatie. | GitHub Actions niet op afstand uitgevoerd. |
| NV24 initialisatie | Route-/hookregistratie vóór app.run; CLI/import/direct dezelfde registratie. | Productie-WSGI nog accepteren. |
| NV25 CSP | Afgedwongen scriptbeleid met nonce; inline-eventhandlers verwijderd. | Style unsafe-inline blijft tijdens deze migratie; productie-compatibiliteit apart toetsen. |
| NV26 reviewlimieten | X-Forwarded-For niet blind vertrouwd; transactionele limiter. | Vertrouwde proxylaag later expliciet configureren. |
| NV27 favorieten | Per klant opgeslagen en bij login gekoppeld; toegang gescheiden. | Geen externe accountsynchronisatie. |
| NV28 campagnes | Persoonlijke gehashte codes, datums, uitsluitingen, minimum, eenmalige atomische reservering en bannerpreview gebouwd. | Campagnes uit; e-mail en echte reviewaankopen vereisen acceptatie. |
| NV29 oude namen | Klantzichtbare merkvoering gecontroleerd, sitemapalias aangepast. Technische sleutels, redirects en historie behouden. | Geen blinde vervanging of historische opschoning. |
| NV30 AI-limieten | Zelfstandige SQLite-opslag en atomische budgetreservering met concurrentietest. | Betaalde AI uit; actuele modeltarieven, providerbudget en productiegedrag apart valideren. |
| NV31 geldberekening | Lokaal opgelost: integercenten/Decimal en grootste-restenverdeling voor korting/refunds. | Echte fiscale inrichting nog niet geverifieerd. |

## Gebouwde werking en bewijs

- **78 tests geslaagd**, laatste volledige run 75,12 s. Flask 3.1.3/Werkzeug 3.1.9. Uitgaande mail-, provider- en AI-aanroepen geblokkeerd. Na de laatste verplaatsing van alleen de beheerpreview is aanvullend de beheertoegang/preview getest.
- **264 bereikbare interne pagina-/asset-URL’s via GET gecontroleerd**, geen HTTP-fouten. Geen formuliermutaties, externe hosts of private klant-URL’s gecrawld. Daarnaast rendercontroles voor alle 100 productpagina’s en de publieke pagina’s in NL/EN.
- **144 hero-schermcontroles**: acht routes, negen breedtes van 320 tot 1920, NL/EN. Geen vastgestelde horizontale overloop of ontbrekende beelden; desktop vanaf 1024 gemeten op 400 px hoogte. **42 aanvullende Engelse schermcontroles** op 390/768/1366.
- Browserflow: Yogamat toegevoegd, vier bestaande passende aanbevelingen zichtbaar, registratie met fictief adres, mandje behouden, checkout €39,95 inclusief €6,93 gesimuleerde btw, SIM-order van pending naar paid, mandje daarna leeg. Geen geld of producten verplaatst.
- Testdekking omvat couponrace/dubbele inwisseling, persoonlijke binding, datum/uitsluitingen/minimum, herstelreplay, verkeerde ordertoegang, betaalgebeurtenisreplay, annulering/mislukking/timeout, btw/refundreconciliatie, positieve én negatieve reviewbeloning, accountfavorieten, aanbiedingen actief/verlopen, opslagherstel en private caching.
- PWA: manifest/startpagina/standalone/icons en netwerk-only serviceworker. Geen account-, prijs- of checkoutcache offline. **Geen installatie of fysieke Android/iPhone/PWA-test uitgevoerd.** Een 844×390 viewport is geen bewijs van een coarse-pointer-telefoon. De landscape-CSS is voorbereid; fysieke acceptatie blijft vereist.
- Aanbevelingen gebruiken maximaal vier bestaande, redactioneel gekoppelde aanvullende artikelen; er zijn geen verzonnen compatibiliteitsclaims. Geen geschikte relatie betekent geen willekeurige opvulling.

Bewijsbestanden staan in `docs/eindcontrole-20261123`, waaronder pytest-results.json, public-links.json, browser-matrix.json, overige-paginas.json, browser-bestelflow.json, behouden-ontwerp.json, private-integriteit.json en screenshots. Een eerdere 10-testsselectie was aanvullend; de volledige 78-testsrun is leidend.

## Aanvullend: telefoon draaien

De mobiele indeling blijft nu ook op brede liggende telefoons actief, op basis van schermformaat en aanraakmogelijkheden. Zeven logische apparaattests en 50 gesimuleerde browsercontroles zijn geslaagd, plus de volledige 78 regressietests. Desktop behoudt zijn 400 px hero. Fysieke telefoon-/PWA-acceptatie blijft open; zie MOBIEL-DRAAIEN-20261123.md voor methode en beperkingen.

## Leidende bron en activering

De bestaande JSON-catalogus blijft de bron van 100 voorbeeldartikelen en blijvende URL’s. `nv_store.py` met private SQLite is de leidende lokale bron voor productoverrides, publicatie, prijzen/aanbiedingen, campagnecodes, orders en aanvullende accountstatus. Credentials blijven in de klantdatabase. Een later extern dashboard moet deze services gebruiken; er is geen werkende externe dashboardsynchronisatie voorgesteld.

15%-keten: actieve campagne → gehele banner naar registratie → e-mailverificatie → één persoonlijke code → privébericht in testpostbus → servervalidatie in simulatiecheckout. De voorbereide SMTP-adapter mag pas na afzonderlijke mailacceptatie nieuwe berichten verzenden. De reviewkorting geldt onafhankelijk van sterren en uitsluitend volgens aankoop-/campagnevoorwaarden. Bij verlopen campagne verdwijnt de banner; een reeds geopende pagina wordt ook op de eindtijd bijgewerkt. Er is geen campagne geactiveerd.

Nog nodig van de eigenaar: definitieve verkoper-/contact-/KvK-/btwgegevens, retouradres en juridisch beoordeelde voorwaarden; echte leveranciers, voorraad, beelden/rechten en productveiligheid; verzendtarieven, landen en btwbeleid; hosting, private opslag, domein, secrets/backups; maildomein/SMTP en afleveracceptatie; gekozen betaalprovider met aparte adapter-/sandboxacceptatie. Varianten, fysieke apparaten, hulpmiddelen en productieperformance blijven afzonderlijke technische acceptatiepunten.

## Juridische en operationele grenzen

De identiteit, totale kosten, levering en voorwaarden moeten vóór echte verkoop kloppen volgens de [ACM-informatiechecklist](https://www.acm.nl/nl/verkoop-aan-consumenten/online-verkoop/checklist-online-verkoop). De online herroepingsfunctie is lokaal voorbereid; de operationele keten en de [regels over bedenktijd/herroeping](https://www.acm.nl/nl/verkoop-aan-consumenten/klantenservice/bedenktijd) moeten op de echte organisatie worden toegepast. Een lokale ontvangstregistratie is geen extern afgeleverde bevestiging.

Reviewverificatie en beloning vereisen transparantie en eerlijke behandeling van negatieve ervaringen volgens [ACM over reviews](https://www.acm.nl/nl/verkoop-aan-consumenten/reclame-en-verleiden/online-beinvloeden/reviews-en-beoordelingen-gebruiken). Verwerking, bewaartermijnen en niet-noodzakelijke cookies moeten overeenkomen met de werkelijkheid; zie [AP over cookies](https://autoriteitpersoonsgegevens.nl/nl/onderwerpen/internet-telefoon-en-tv/cookies). Registratie geldt niet als algemene marketingtoestemming.

Veiligheids-/GPSR-/CE-verplichtingen hangen af van het echte artikel en de rol van verkoper, fabrikant of importeur; zie [Europese Commissie: verplichtingen voor bedrijven](https://ec.europa.eu/safety-gate/screen/pages/obligationsForBusinesses). De eigen webshop is niet automatisch een online marktplaats. Er is geen certificering verzonnen. De toepasselijkheid van toegankelijkheidsregels en eventuele uitzondering moet worden vastgesteld; zie [ACM over e-handelsdiensten](https://www.acm.nl/nl/toegankelijkheid/toegankelijkheid-van-e-handelsdiensten-en-elektronische-communicatiediensten).

De lokale functionele demonstratie staat klaar. **Productieacceptatie kan pas worden afgerond nadat de genoemde gegevens, integraties en fysieke/juridische controles beschikbaar zijn. Geen commerciële vrijgave of livepublicatie.**
