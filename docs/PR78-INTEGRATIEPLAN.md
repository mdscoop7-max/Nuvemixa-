# PR #78 afzonderlijk afronden en daarna de modernisering aansluiten

**Status: voorbereiding. PR #78 is niet gemerged, niet gesloten, niet aangepast en niet uitgerold. Er is niets gedeployed.** Elke stap hieronder met "[AKKOORD]" vraagt eerst jouw afzonderlijke, uitdrukkelijke toestemming.

## Vooraf gecontroleerd (17-11-2026)
- Integratiebranch `integration/nuvemixa-dashboard-20261114` staat op `41fad63` = de Live-versie. PR #78 (`hotfix/nuvemixa-2fa-omzeiling-20261117`, `b786026`) is daarop gebaseerd, dus er is geen achterstand en de PR kan zonder conflicten op de integratiebranch.
- De moderniseringsbranch heeft dezelfde basis; die komt pas na de hotfix.
- De actuele Render-deployment kan ik niet zien (geen toegang tot het Render-dashboard en de Live-URL is voor mij niet bereikbaar). **Jij controleert in Render → Deploys dat de laatste geslaagde deploy `41fad63` is.**
- Herstelplan: zie `VOORSTELLEN-20261117.md` punt 7. Belangrijk: een Render-rollback via het dashboard zet auto-deploy uit en zet omgevingsvariabelen van de oude deploy terug.

## Conflicten bij het samenvoegen van de moderniseringsbranch met PR #78
Proefsamenvoeging in een losse, niet-gepushte kopie (daarna weggegooid):

| Bestand | Conflict | Oplossing |
|---|---|---|
| `app.py` | één blok in de sjablooncontext; dezelfde regel `staff_login_enabled=...` staat aan beide kanten, de moderniseringsbranch voegt daar de regels voor talen/administratie bij | de versie van de moderniseringsbranch behouden (bevat de PR #78-regel al) |
| `nv_dashboard_manager.py` | `staff_login_enabled()`: PR #78 accepteert alleen exact `on`; de moderniseringsbranch ook `1`, `true`, `yes` | **de PR #78-versie** (alleen `on`, standaard dicht) |
| `tests/test_staff_access.py` | beide kanten maakten het bestand | **de PR #78-versie**; de tests van de moderniseringsbranch zijn daar een deelverzameling van (geen enkele test gaat verloren) |

Resultaat van de proef: **337 geslaagd, 42 overgeslagen (Postgres), 0 mislukt.** De strenge regel is dus als definitieve standaard doorgevoerd. Eigenaarslogin en 2FA-bestanden zijn niet aangeraakt en staan niet in de conflicten.

## Stappenplan
1. **Controle vooraf (jij):** Render → Deploys: laatste geslaagde deploy is `41fad63`; noteer de huidige variabelen (niet delen). Controleer of er in Accountbeheer medewerkersaccounts bestaan die nu worden gebruikt. Na PR #78 staat medewerkerslogin uit en verliezen zij toegang.
2. **PR #78 beoordelen en uit concept halen [AKKOORD]:** diff nalopen (6 bestanden, +209/−2), tests (306 zonder Postgres) draaien.
3. **PR #78 mergen naar de integratiebranch [AKKOORD].** Render deployt automatisch (auto-deploy staat aan op deze branch). Er wordt geen andere wijziging meegenomen.
4. **Na de deploy controleren (jij, met mij als checklist):**
   - Inloggen als eigenaar met wachtwoord + Google Authenticator werkt.
   - Zonder 2FA-code kom je niet binnen.
   - Een medewerker (indien aanwezig) kan niet inloggen en ziet de melding "Medewerkerstoegang staat uit".
   - `/dashboard?section=accountbeheer` toont de melding.
5. **Medewerkerslogin geblokkeerd houden:** `NUVEMIXA_STAFF_LOGIN` niet zetten (of iets anders dan exact `on`). Dat is de veilige toestand.
6. **Terugdraaien bij een fout:** Render-rollback naar `41fad63` of GitHub-revert van de merge-commit (zie herstelplan).
7. **Moderniseringsbranch aansluiten [AKKOORD]:** `integration` in `dev/nuvemixa-dashboard-modern-20261117` samenvoegen; conflicten volgens de tabel hierboven oplossen.
8. **Alle beveiligingstests opnieuw:** volledige suite plus `tests/test_staff_access.py` (17 tests) en routeaudit; 42 Postgres-tests blijven apart gerapporteerd tot er een goedgekeurde, geïsoleerde testdatabase is.
9. **Pas daarna** de modernisering ter goedkeuring voorleggen.
