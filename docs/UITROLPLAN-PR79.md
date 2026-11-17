# Definitief uitrolplan PR #79 (alleen na afzonderlijk akkoord van de eigenaar)

Stand: Live = `d31c816` (PR #78). PR #79 bevat de moderniseringsbranch bovenop `d31c816`.
Er is niets gemerged of uitgerold. Dit plan beschrijft hoe dat later veilig kan.

## 1. Wat kan meteen Live (geen nieuwe koppeling nodig)
- Modern ontwerp, menu en alle 26 pagina's; toegankelijkheid en mobiele tikvlakken.
- WooCommerce-pagina met vier statussen en handmatige knoppen (zonder sleutels: "Niet ingesteld").
- Pagina's Bestellingen, Administratie en Publicatie doen **geen** externe aanroep meer bij openen.
- Monitoring-tabbladen, productpublicatie als **concept-controle** (verzendt niets zonder schrijfkoppeling).
- Beveiliging van PR #78 ongewijzigd (`NUVEMIXA_STAFF_LOGIN=on` is de enige manier om medewerkers toe te laten).

## 2. Wat later geactiveerd moet worden (elk afzonderlijk akkoord)
| Koppeling | Variabele(n) | Kosten |
|---|---|---|
| WooCommerce alleen-lezen (bestellingen/producten) | `NUVEMIXA_WOO_URL/KEY/SECRET/HOST` (leessleutel) | geen |
| WooCommerce publiceren (concept) | `NUVEMIXA_WOO_WRITE` + schrijfsleutel | geen |
| AI-leveranciers- en productonderzoek | `OPENAI_API_KEY`, `NUVEMIXA_SUPPLIER_SEARCH_MODEL`, `NUVEMIXA_RESEARCH_AI=true` | betaald per zoekopdracht; standaardlimiet 10 per dag / 60 per maand |
| Bezoekers per land | `NUVEMIXA_WEBSHOP_TRACKING=true` | geen |
| Permanente dashboarddatabase | `NUVEMIXA_DASHBOARD_DATABASE_URL`, `NUVEMIXA_DASHBOARD_BACKEND=postgres` | databasekosten |
| Sell The Trend, boekhoudkoppeling | nog niet gebouwd | abonnement / nader te bepalen |

## 3. Uitrolstappen
1. Eigenaar geeft akkoord (schriftelijk in de chat).
2. Controle voor de merge: PR #79 open, `mergeable`, GitHub-check `test` groen op de laatste commit, integratiebranch nog `d31c816`.
3. Reguliere merge-commit van PR #79 in `integration/nuvemixa-dashboard-20261114` (geen squash, zodat terugdraaien één commit is). Noteer de SHA van de merge-commit.
4. Render deployt automatisch. Wacht tot de nieuwe deploy "Live" is; geen tweede deploy starten.
5. Eigenaar logt in met wachtwoord en Google Authenticator (geen codes delen). Controleer: dashboard laadt, Accountbeheer toont "Medewerkerstoegang staat uit", alle menu's openen, WooCommerce toont "Niet ingesteld".
6. Geen Render-variabelen wijzigen tijdens de uitrol.

## 4. Herstelprocedure (geen automatische rollback)
Bij een fout: stoppen, niets aan 2FA, accounts, Neon of variabelen veranderen en eerst toestemming vragen.
- **Scenario A (voorkeur): GitHub-revert.** `git revert -m 1 <merge-commit-van-PR-79>` op de integratiebranch; dit levert exact de boom van `d31c816` op. Render deployt die automatisch. Getest in proefkopie voor PR #78 (zelfde methode).
- **Scenario B: Render Manual Deploy** van commit `d31c816`, indien beschikbaar. Dit zet automatisch deployen uit; daarna handmatig opnieuw inschakelen.
- Uitgebreide stappen: branch `docs/noodplan-pr78-20261117`.
- Let op: op Render Free is SQLite tijdelijk; elke deploy of herstart wist die data. De eigenaar bevestigde dat alles testdata is. 2FA staat in Neon en wordt door PR #79 niet aangeraakt (geen 2FA-bestand gewijzigd; tests bewijzen dat dashboardvariabelen de 2FA-opslag niet beïnvloeden).

## 5. Permanente database zonder 2FA-risico
- 2FA gebruikt het schema `nuvemixa_auth` met eigen variabelen (`NUVEMIXA_2FA_*`); de dashboardopslag gebruikt aparte variabelen en andere tabellen en bevat geen `DROP`/`TRUNCATE`/`DELETE`.
- Gebruik voor het dashboard een **aparte** database of project, niet de 2FA-database. Maak eerst een back-up van wat bewaard moet blijven. Aanmaken en migreren pas na afzonderlijk akkoord.
