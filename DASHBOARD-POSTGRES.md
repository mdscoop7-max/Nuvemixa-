# NUVEMIXA-dashboardopslag

Dit is de werkwijze voor een lokaal of geïsoleerd migratiedoel. De reviewbranch activeert geen productieopslag.

## Scheiding van toegang

- Gebruik een aparte migratierol als eigenaar van schema `nuvemixa_dashboard` en een aparte applicatierol voor de dashboardverbinding.
- Beperk de applicatierol tot `USAGE` op dit schema en `SELECT, INSERT, UPDATE` op de tabellen die de applicatie gebruikt. Verleen waar vereist `USAGE` op bijbehorende sequenties. Houd `CREATE`, `TRUNCATE` en toegang tot `nuvemixa_auth` buiten deze rol.
- Zet de DSN via `NUVEMIXA_DASHBOARD_DATABASE_URL`. Het dashboard valideert het TLS-certificaat en de hostname. Het bestaande 2FA-schema, de rol en de sleutel blijven afzonderlijk.
- De bezoekersteller en productdossiers ondersteunen deze PostgreSQL-verbinding. De overige bestaande routes lezen en schrijven nog via SQLite. Een geslaagde import is daarom alleen een migratieproef. Voor een omschakeling moeten ook die routes aantoonbaar dezelfde gegevens lezen en schrijven.

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
