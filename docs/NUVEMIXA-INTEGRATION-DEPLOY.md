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
