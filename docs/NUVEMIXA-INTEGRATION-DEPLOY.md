# NUVEMIXA — veilige integratie en uitrol (5 november 2026)

Deze branch hoort bij **NUVEMIXA** op Alwaysdata, niet bij Luvyza. De vijf categorieën, categorie-hero's, talen, winkelwagen en bestaande bestanden blijven behouden.

## Wat daadwerkelijk is gebouwd

- Beveiligd dashboard: `/admin/login`, `/admin/logout`, `/dashboard`; zonder `SECRET_KEY` en `NUVEMIXA_ADMIN_PASSWORD_HASH` is het dashboard afgesloten.
- Dashboard toont het goedgekeurde logo **alleen wanneer** `static/nuvemixa-logo.png` aanwezig is. Anders valt het afbeeldings-element terug op `static/logo.svg`.
- Leesbare interne controles (na login): `/admin/merchant-preview`, `/admin/research-preview`, `/admin/integrations`. Deze routes publiceren niets naar Google en maken geen bestellingen aan.
- Google Merchant-status: producten worden niet als gereed behandeld zonder expliciet bevestigde leverancier, productgegevens, prijs, voorraad, afbeelding, verzending en merk/identificatie.
- Onderzoek toont catalogusfeiten, geen geschatte zoekvolumes of verzonnen marges.
- Bestaande WooCommerce-/AI-koppelingen blijven standaard in testmodus.

## Wat nog niet klaar is

Echte **database, betaalprovider, orderwebhooks, leveranciersfeed, Merchant Center-account, Google Ads, RankFix API-koppeling en marktdata** vereisen implementatie en geldige accounts. Het toevoegen van API-sleutels is op zichzelf niet voldoende: webhooks, validatie, rechten en volledige integratietests zijn nodig. De shop is **niet** klaar voor echte bestellingen.

## Kritieke serverinstellingen vóór de update

1. Back-up van webshopbestanden én de eventuele externe database, met een hersteltest.
2. Maak een stabiele `SECRET_KEY` (lange random waarde) en een **hash** van het gekozen beheerderswachtwoord. Gebruik bijvoorbeeld op de NUVEMIXA-server (wachtwoord niet in GitHub of chat plaatsen):

   ```bash
   cd /home/nuvemixa/www/nuvemixa
   .venv/bin/python -c 'import secrets; print(secrets.token_hex(48))'
   .venv/bin/python -c 'import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass.getpass("Nieuw beheerderswachtwoord: ")))'
   ```

3. Configureer de twee uitkomsten in **de Alwaysdata-omgeving voor de NUVEMIXA WSGI-app**, als `SECRET_KEY` en `NUVEMIXA_ADMIN_PASSWORD_HASH`. Deel ze niet openbaar. Zet `NUVEMIXA_COOKIE_SECURE=true` bij HTTPS.
4. Het exacte, door de eigenaar goedgekeurde logo moet eerst worden opgeslagen als `/home/nuvemixa/www/nuvemixa/static/nuvemixa-logo.png` (PNG). Het afbeeldingsbestand is niet meegecommit via de tekst-connector. Controleer `ls -lh static/nuvemixa-logo.png`.
5. Draai de regressietests in de juiste Python-omgeving en stop bij fouten:

   ```bash
   .venv/bin/python -m unittest discover -s tests -p 'test_nuvemixa_admin.py'
   .venv/bin/python -c "from wsgi import application; print('WSGI OK')"
   ```

6. Pas na back-up, serverconfiguratie, juiste asset en geslaagde tests de code op Alwaysdata bij met `git pull --ff-only origin design/pixel-polish-responsive-20261027`. **Let op:** voor de tests heb je de nieuwe code al nodig; voer daarom pull uit na bevestiging van back-up en env-instellingen, maar herstart de site pas na geslaagde tests.
7. Herstart de WSGI-app en controleer `/`, de vijf categorieën, `/shop`, `/winkelwagen`, `/admin/login`, `/dashboard`, alle taalkeuzes, mobiele weergave en footerlogo. Bevestig dat `/dashboard` anoniem een redirect geeft en dat inloggen, uitloggen en CSRF werken.

**Rollback:** houd de geteste back-up en de vorige Git-commit bij de hand. Herstel niet blind een externe database; controleer eerst de actuele gegevens.

## Niet wijzigen zonder aparte besluitvorming

- Hero-bestanden en categorie-ID's/URLs.
- Huidige taalfunctionaliteit.
- Luvyza-hosting en database.
- `TRENDMIX_LIVE_ORDERS`: blijft uit totdat echte order- en betaaltests geslaagd zijn.

## Testcases

- Anoniem dashboard/toegangspunten: redirect naar login.
- Login zonder ingestelde env: HTTP 503 zonder informatielek.
- Verkeerd wachtwoord: geen toegang.
- Juist wachtwoord + logout + CSRF.
- Merchant/testproducten: geen automatisch gepubliceerde feed.
- Productresearch: geen gefingeerde marktdata.


## Toegevoegd na de integratiecontrole van 5 november

- `nuvemixa_admin_store.py` beheert een **eigen SQLite-database** voor leverancierscontacten en onderzoeksnotities. Standaard is de database uitgeschakeld; er worden geen klantgegevens of orders automatisch in opgeslagen.
- Stel `NUVEMIXA_ADMIN_DB` in op een **schrijfbare locatie buiten het Git-repository**, bijvoorbeeld `/home/nuvemixa/private/nuvemixa-admin.sqlite3`. De bovenliggende map moet bestaan, mag niet via HTTP worden geserveerd en moet alleen voor de NUVEMIXA-gebruiker toegankelijk zijn. Neem deze database na ingebruikname op in versleutelde back-ups.
- Administratie na veilige login:
  - `/dashboard?section=leveranciers`: leverancierscontacten toevoegen en bekijken.
  - `/dashboard?section=onderzoek`: eigen onderzoeksnotities toevoegen en bekijken.
  - `/dashboard?section=bestellingen`: uitsluitend **lezen** van de nieuwste WooCommerce-orders wanneer bestaande WooCommerce-instellingen werken; anders een eerlijke foutmelding.
  - `/dashboard?section=google-shopping`: product-per-product overzicht van ontbrekende bevestigingen. Geen productfeed naar Google gepubliceerd.
- Nieuwe tests: `tests/test_nuvemixa_admin_store.py`, `tests/test_nuvemixa_admin.py`.
- Nieuwe GitHub Actions workflow: `.github/workflows/nuvemixa-integration.yml`. Een workflowbestand in GitHub **bewijst niet dat CI geslaagd is**. Controleer de feitelijke workflow-uitvoer vóór livegang.
- De volledige live-integratie met Mollie/betalingen, echte WooCommerce-orderacties, Dropshipping-API, RankFix API, Google Merchant Center en marktdata is **nog niet geactiveerd**. Deze functies vereisen afzonderlijke connectorinstellingen en integratietests.
- `static/nuvemixa-logo.png` moet op de Alwaysdata-server worden geplaatst; de GitHub-textconnector heeft het door de gebruiker aangeleverde PNG-bestand niet meegecommit.

### Extra QA vóór productie

```bash
cd /home/nuvemixa/www/nuvemixa
.venv/bin/python -m unittest discover -s tests -p 'test_nuvemixa_admin*.py' -v
.venv/bin/python -m compileall -q app.py nuvemixa_admin_store.py
.venv/bin/python -c 'from wsgi import application; print("NUVEMIXA WSGI OK")'
```

Verifieer dat een anonieme GET naar `/dashboard` omleidt naar `/admin/login`; dat de adminlogin na het instellen van de vereiste geheime variabelen werkt; en dat het adminformulier voor leveranciers veilig opslaat zonder automatisch producten te publiceren.


## Vier integraties en moderne knoppen — 5 november 2026

**Beschikbaar op deze ontwikkelbranch, nog niet live gedeployed:**

- **RankFix:** `/admin/rankfix/open` opent de bestaande RankFix-scanner met `https://nuvemixa.alwaysdata.net/` vooringevuld. De RankFix-app beheert zelf authenticatie. `RANKFIX_BASE_URL` moet naar de vertrouwde HTTPS-host verwijzen (standaard `https://rankfix-app.onrender.com`); `RANKFIX_TRUSTED_HOST` is standaard `rankfix-app.onrender.com`. Er worden **geen** API-tokens in URLs meegegeven. Dit is een echte scanner-handoff, geen scanresultaten-API of automatische scan.
- **Mollie:** `/admin/mollie/check` doet uitsluitend een GET naar Mollie voor de beschikbare betaalmethoden. De sleutel staat alleen server-side in `MOLLIE_API_KEY`. Er wordt geen payment/order gemaakt of bevestigd. Werkelijke betaalverwerking, webhooks en terugbetalingen blijven openstaand.
- **Google Merchant:** `/admin/merchant-feed-preview.xml` geeft alleen voor ingelogde beheerders een interne XML-preview. Een product moet expliciet `merchant_verified=true` hebben plus alle vastgestelde basisvelden. Geen feedpublicatie, accountverificatie of Google-synchronisatie.
- **Leveranciers:** `/dashboard?section=leveranciers` biedt een CSV-uploadvoorvertoning. Vereiste velden: `sku,name,price,stock`; maximaal 60 KB en 150 rijen. Er worden **geen** producten toegevoegd, prijzen gewijzigd of bestellingen naar leveranciers gestuurd.
- **Buttons:** donkerblauwe/oranje actiekleuren in de bestaande NUVEMIXA-template met contrast, focusranden, hover en grotere aanraakvlakken op mobiel.
- Regressietests in `tests/test_nuvemixa_integrations.py`, meegenomen via de workflow `test_nuvemixa_*.py`.

### Veiligheidscontrole vóór live-uitrol

1. Controleer eerst of RankFix werkt vanaf de gekozen `RANKFIX_BASE_URL` en dat het eigen login/scanpad bereikbaar is.
2. Zet `SECRET_KEY`, `NUVEMIXA_ADMIN_PASSWORD_HASH` en `NUVEMIXA_ADMIN_DB` op de **NUVEMIXA Alwaysdata-app**. Niet in GitHub zetten.
3. Voeg de door de eigenaar goedgekeurde PNG `static/nuvemixa-logo.png` toe en verifieer de bestandsgrootte. Dit binaire bestand ontbreekt nog in GitHub.
4. Draai `.venv/bin/python -m unittest discover -s tests -p 'test_nuvemixa_*.py' -v`, daarna WSGI-import en browsertests.
5. Kies pas na goedgekeurde testresultaten of op **NUVEMIXA** op Alwaysdata gepusht mag worden. Luvyza blijft buiten scope.

**Niet gereed:** live Mollie-betalingen, Google Shopping-publicatie, automatisch productfeedbeheer, RankFix API-responsen die in NUVEMIXA worden opgeslagen. Voor die functies zijn geverifieerde accounts, provider API's, webhooks en contracten nodig.
