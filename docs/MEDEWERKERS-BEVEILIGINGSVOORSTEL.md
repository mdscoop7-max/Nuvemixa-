# Beveiligingsvoorstel: toegang voor anderen veilig uitschakelen

Status: alleen onderzoek en voorstel. Er is **niets** gewijzigd, geblokkeerd of verwijderd.

## Bevindingen (uit de code gelezen, `app.py` en `nv_dashboard_manager.py`)

1. Naast het eigenaarsaccount (`NUVEMIXA_ADMIN_EMAIL` + wachtwoordhash uit de omgeving) bestaat een tabel `staff`. Accounts worden alleen aangemaakt via `/admin/nv/team`, en die route vereist een ingelogde beheerder.
2. Medewerkers loggen in op dezelfde pagina (`/admin/login`) met e-mailadres of gebruikersnaam. Zij krijgen sessiegegevens `nv_staff_id` en gaan direct naar `/dashboard`.
3. **Zwakke plek:** de tweestapsverificatie geldt alleen voor het eigenaarsaccount. Een medewerkersaccount met de rol `admin` wordt door `admin_is_authenticated()` als beheerder herkend zonder 2FA. Alleen een wachtwoord is dan genoeg.
4. Medewerkers met beperkte rechten zien alleen de onderdelen waarvoor ze rechten hebben; Accountbeheer, Administratie en andere beheeronderdelen blijven voor hen dicht.
5. Er is geen openbare registratie voor het dashboard. De route `/account/register` is voor webshopklanten en geeft geen dashboardtoegang (los sessiesleutelpaar `nv_admin` / `nv_staff_id`).
6. In de testomgeving is niet te zien of er in productie medewerkersaccounts bestaan; de database daar is niet gelezen.

## Voorstel (in volgorde van voorzichtigheid)

**Stap A (aanbevolen, omkeerbaar, geen data wijzigen):** een schakelaar `NUVEMIXA_STAFF_LOGIN=off` (standaard uit). Met die schakelaar:
- `staff_auth()` geeft altijd `None` terug, dus niemand behalve de eigenaar kan inloggen;
- `staff_current()` negeert bestaande medewerkerssessies;
- het formulier voor nieuwe medewerkers in Accountbeheer wordt verborgen.

Het eigenaarsaccount, de bestaande login en de 2FA-database worden niet aangeraakt. De accounts in de tabel blijven bewaard. Terugzetten kan door de schakelaar weg te halen.

**Stap B (alleen na jouw akkoord, na stap A):** bestaande medewerkersaccounts controleren en eventueel op inactief zetten (`active=0`). Dit wijzigt data en gebeurt dus pas na afzonderlijke toestemming en na een back-up.

**Stap C (later, optioneel):** de medewerkerscode verwijderen als je zeker weet dat je die nooit nodig hebt.

## Wat ik niet doe zonder jouw toestemming

Geen accounts blokkeren of verwijderen, geen omgevingsvariabelen in Render wijzigen, niets aan de 2FA-database, niets live zetten.

## Testplan voor stap A

- Test: met de schakelaar uit kan een bestaand medewerkersaccount niet meer inloggen en geldt een oude medewerkerssessie niet meer.
- Test: eigenaarslogin en 2FA-pad blijven ongewijzigd.
- Test: alle 24 menuonderdelen blijven laden voor de eigenaar.

## Uitvoering op de ontwikkelbranch (17 november 2026)

- `NUVEMIXA_STAFF_LOGIN` (standaard `off`): zonder deze variabele kan geen enkel medewerkersaccount inloggen en wordt een bestaande medewerkerssessie genegeerd. Accounts blijven in de tabel bewaard; uitschakelen blijft mogelijk, aanmaken, bewerken, resetten en inschakelen niet.
- 2FA-omzeiling gedicht: een medewerker met rol `admin` wordt nooit meer als eigenaar gezien (`admin_is_authenticated()`), ook niet als de schakelaar aan staat.
- Eigenaarslogin en 2FA zijn niet gewijzigd en getest (`tests/test_staff_access.py`).

## Productierisico (onderzoek, niets gewijzigd)

Het probleem is **gereproduceerd op de huidige Live-code** (commit `41fad63`) in een tijdelijke kopie met testdatabase: een medewerkersaccount met rol `admin` logt met alleen e-mailadres en wachtwoord in, gaat direct naar `/dashboard` en krijgt Accountbeheer, Instellingen en Monitoring te zien. Er is geen 2FA-stap.

- Voorwaarde: er moet een medewerkersaccount met rol `admin` bestaan. Die kan alleen door de ingelogde eigenaar worden aangemaakt; er is geen openbare registratie. Of zo'n account in productie bestaat, is niet gecontroleerd (productiegegevens niet gelezen).
- Ernst: **hoog als zo'n account bestaat** (volledige beheerderstoegang met alleen een wachtwoord, en die toegang kan nieuwe accounts maken). **Laag als er geen is** (niet te misbruiken zonder bestaand account). Tegen wachtwoord raden geldt de bestaande poging-beperking per IP-adres.
- Voorgestelde hotfix (apart, niet toegepast): een kleine branch vanaf `41fad63` met alleen de twee wijzigingen in `nv_dashboard_manager.py` en `app.py` plus de tests. Zolang die niet live staat is het directe, tijdelijke alternatief in Accountbeheer alle medewerkersaccounts uit te schakelen (dat verwijdert niets).
