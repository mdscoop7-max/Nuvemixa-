# NUVEMIXA-dashboardopslag

Dit is de werkwijze voor een lokaal of geïsoleerd migratiedoel. De reviewbranch activeert geen productieopslag.

## Scheiding van toegang

- Gebruik een aparte migratierol als eigenaar van schema `nuvemixa_dashboard` en een aparte applicatierol voor de dashboardverbinding.
- Beperk de applicatierol tot `USAGE` op dit schema en `SELECT, INSERT, UPDATE` op de tabellen die de applicatie gebruikt. Verleen waar vereist `USAGE` op bijbehorende sequenties. Houd `CREATE`, `TRUNCATE` en toegang tot `nuvemixa_auth` buiten deze rol.
- Zet de DSN via `NUVEMIXA_DASHBOARD_DATABASE_URL`. Het dashboard valideert het TLS-certificaat en de hostname. Het bestaande 2FA-schema, de rol en de sleutel blijven afzonderlijk.
- De bezoekersteller, productdossiers en leveranciersvergelijking gebruiken deze PostgreSQL-verbinding zodra de DSN aanwezig is. Met `NUVEMIXA_DASHBOARD_BACKEND=postgres` gebruiken ook teamaccounts, klanten, kortingsacties, catalogus, leveranciers, onderzoek en SEO die opslag. Verifieer vooraf op een geïsoleerd doel dat alle routes aangemelde gegevens lezen en schrijven. De vaste hoofdbeheerder en bestaande 2FA gebruiken hun afzonderlijke configuratie en opslag.
- Bewaar toegang tot de vorige opslag en de geverifieerde snapshots. Bij ontbrekende of onbereikbare PostgreSQL-opslag geeft de applicatie in PostgreSQL-modus een fout. Een automatische terugval zou twee versies van dezelfde gegevens kunnen creëren.

## Back-up en proefimport

1. Verkrijg drie consistente SQLite-snapshots via de Backup API, inclusief de actuele WAL-inhoud. Gebruik productiebestanden alleen na gecontroleerde export uit de bron of uit een aantoonbare productieback-up. Beveilig de kopieën en de onafhankelijk vastgelegde SHA-256-checksums buiten Git.
2. Maak op het geïsoleerde, lege doel de tabellen met `nv_dashboard_postgres.sql`. Pas dit bestand niet toe op `nuvemixa_auth`.
3. Bereid een JSON-bestand voor met de drie bestandsnamen zoals in `migrate_dashboard_postgres.py`, en hun onafhankelijk vastgelegde SHA-256-hashes. Controleer eerst zonder `--apply`:

   ```text
   python -B migrate_dashboard_postgres.py --bundle <snapshotmap> --checksums <checksums.json>
   ```

4. Voer dezelfde opdracht met `--apply` uit op het expliciet gekozen geïsoleerde doel. De import weigert bestaande doelrijen en onbekende brontabellen of kolommen. Vergelijk de aantallen en voer een dump/herstelproef en applicatietest uit.
5. Een mislukte import wordt teruggedraaid. Bewaar het bronbestand en de gevalideerde kopie. Als een latere omschakeling al nieuwe schrijfacties heeft aangenomen, is eerst een export en reconciliatie nodig voordat het oude systeem weer schrijvend kan worden gebruikt.

Historische metingen blijven als afzonderlijke sessiedagen bewaard. Voor de nieuwe meting telt een teruggekeerde meetcookie eenmaal per Nederlandse kalenderdag. Alleen sessies waarvan minimaal één volgende geschikte aanvraag aankomt komen in de telling.


## Leverancierszoeker

De bestaande onderzoeksassistent en handmatige bronnen werken onafhankelijk van de optionele webzoekfunctie. Geef `NUVEMIXA_SUPPLIER_SEARCH_MODEL` alleen een model met Responses API-webzoekondersteuning en houd de OpenAI-sleutel in de omgeving. De zoekopdracht stuurt titel, openbaar productkenmerk en bestemmingsland naar de provider. Het dashboard toont uitsluitend geciteerde links uit bekende B2B-domeinen. De magazijnlocatie, prijs, voorraad, veiligheid en dropshippingstatus worden per SKU en land handmatig onderbouwd.


## Verbindingspool (optioneel, standaard UIT)

- Schakelaar: `NUVEMIXA_DASHBOARD_POOL=1`. Werkt alleen mét `NUVEMIXA_DASHBOARD_BACKEND=postgres` en `NUVEMIXA_DASHBOARD_DATABASE_URL`. Zonder schakelaar is het gedrag ongewijzigd (een nieuwe verbinding per aanroep).
- Eén pool per proces: minimaal 1 en maximaal 3 verbindingen, 4 s wachttijd op een verbinding, verbindingen leven maximaal 5 minuten en worden na 60 s inactiviteit gesloten. Elke aanroep van `application_db()` blijft een eigen transactie met dezelfde time-outs (`statement_timeout` 5 s, `lock_timeout` 3 s). Alleen een dode verbinding (bijvoorbeeld na een slaapstand van Neon of een herstart) wordt vervangen, en alleen vóórdat er iets is gelezen of geschreven.
- **Geen terugval naar SQLite.** Is PostgreSQL niet bereikbaar, dan geeft de opslag de fout "PostgreSQL-dashboardopslag is niet beschikbaar". Verbindingsgegevens (host, gebruiker, wachtwoord) komen niet in logs; alleen de klassenaam van de fout.
- Na de eerste PostgreSQL-schrijfactie is terugschakelen naar SQLite **geen** eenvoudig herstel: de nieuwe gegevens staan dan alleen in PostgreSQL. Eerst bevriezen, exporteren en samen beslissen.
- Houd de uptime-controle uit: een voortdurend wakker gehouden service houdt ook de Neon-compute wakker en verbruikt de gratis rekenuren.

### Regio en snelheid (beide regio's werken met dezelfde code)
De regio zit alleen in de DSN. Plan om later vanuit Render te vergelijken (alleen fictieve testdatabases):
1. Maak twee Neon-testprojecten (Frankfurt `aws-eu-central-1` en Oregon `aws-us-west-2`) met het schema uit `nv_dashboard_postgres.sql`.
2. Zet in Render de diagnosevariabelen van PR #73 (`NUVEMIXA_DB_DIAGNOSTIC=1` en `NUVEMIXA_DB_DIAGNOSTIC_URL`) en lees als beheerder `/admin/nv/db-diagnose` (alleen getallen: nieuwe verbinding, query, p95).
3. Herhaal na wisseling van de URL naar de andere regio, ieder minstens 3 keer op verschillende momenten (ook na een koude start van Neon).
4. Vergelijk daarna een dashboardpagina met pool uit en aan. Zet de diagnose weer uit.
