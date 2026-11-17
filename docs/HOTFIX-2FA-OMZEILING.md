# Hotfix: medewerkers-admin kon 2FA omzeilen

Basis: `41fad63` (Live-commit volgens Render Events, bevestigd door de eigenaar; hoofd van `integration/nuvemixa-dashboard-20261114`).

## Risico
Een medewerkersaccount met rol `admin` logde in met alleen e-mailadres en wachtwoord, ging direct naar `/dashboard` en werd door `admin_is_authenticated()` als beheerder gezien. De 2FA-stap geldt alleen voor het eigenaarsaccount. Gevolg: toegang tot Accountbeheer (nieuwe accounts maken), Instellingen, Monitoring en andere beheeronderdelen zonder 2FA.
Gereproduceerd op `41fad63` in een tijdelijke kopie met testdatabase. Voorwaarde: zo'n account moet bestaan. Alleen de ingelogde eigenaar kan het aanmaken; er is geen openbare registratie. Of het in productie bestaat, is niet gecontroleerd.
Ernst: hoog als zo'n account bestaat, laag als er geen is.

## Aanpassingen (4 bestanden, +23/−2, plus tests en dit document)
1. `app.py`: `admin_is_authenticated()` geeft voor medewerkers altijd `False`. Onvoorwaardelijk, dus niet afhankelijk van een omgevingsvariabele.
2. `nv_dashboard_manager.py`: medewerkerslogin staat standaard uit (fail-closed). Alleen de exacte waarde `NUVEMIXA_STAFF_LOGIN=on` zet hem aan; een ontbrekende of verkeerde waarde laat hem uit. `staff_auth()` en `staff_current()` negeren medewerkers dan, en nieuwe medewerkers aanmaken, bewerken, resetten of inschakelen wordt geweigerd. Uitschakelen blijft mogelijk.
3. `templates/_dashboard_team.html`: melding dat medewerkerstoegang uit staat.
4. `tests/test_supplier_workspace.py`: bestaande Postgres-test zet de schakelaar expliciet aan.

## Wat niet verandert
Eigenaarslogin, 2FA (inclusief herstelmogelijkheden), de 2FA-database, alle accounts en gegevens (niets verwijderd of gewijzigd), webshopklanten, Render-instellingen. Er is geen migratie.

## Tests (`tests/test_staff_access.py`, 17 tests + bestaande suite)
- Negatief: staff-login uit standaard; bestaande medewerkerssessie genegeerd; medewerker-admin is geen eigenaar (Accountbeheer, Instellingen, Monitoring, WooCommerce, accountaanmaak, integraties geweigerd); klantsessie geeft geen dashboardtoegang; schakelaar blijft dicht bij lege of foute waarden (`off`, `0`, `false`, `yes`, `1`, `true`, `onn`, `aan`).
- Positief: eigenaar behoudt toegang, eigenaarslogin loopt nog via 2FA, verkeerd wachtwoord geweigerd, accounts blijven in de tabel, uitschakelen blijft mogelijk.
- Routeaudit: alle `/admin` en `/dashboard` routes zonder parameters voor anoniem, medewerker en medewerker-admin, met schakelaar uit en aan: geen 200 op eigenaarsroutes en nooit een 5xx.
- Reproductie na hotfix: schakelaar uit geeft geen login; schakelaar aan geeft wel login maar 403 op alle beheerdersonderdelen.
- Volledige suite: 347 geslaagd, 1 overgeslagen met lokale Postgres; 306 geslaagd, **42 overgeslagen** zonder Postgres (die tellen niet als geslaagd).

## Resterende risico's
- Staat `NUVEMIXA_STAFF_LOGIN=on`, dan hebben medewerkers alleen een wachtwoord (geen 2FA), met uitsluitend hun eigen rechten (geen beheeronderdelen). Aanbevolen: variabele niet instellen.
- Bestaande medewerkersaccounts blijven in de database en kunnen later weer inloggen als iemand de schakelaar aanzet.
- Beperking van loginpogingen is per IP-adres en in het geheugen; dat is niet gewijzigd.
- Niet gecontroleerd: of er in productie een admin-medewerker bestaat.

## Uitrol (alleen na jouw toestemming)
Merge in de integratiebranch en deploy via Render. Geen variabele nodig voor de veilige uitkomst. Terugdraaien is een revert van deze commit.
