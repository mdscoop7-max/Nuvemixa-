# NUVEMIXA – technische voorstellen (punt 3 t/m 7)

Status: **alleen onderzoek en voorstel**. Er is niets uitgevoerd: geen migratie, geen kolommen, geen nieuwe tracking, geen Render-/Woo-wijziging, geen merge, geen deployment. Alles hieronder wacht op aparte toestemming.

Uitgangspunt: branch `dev/nuvemixa-dashboard-modern-20261117`, gecontroleerd op 17-11-2026.

---

## 3. Bezoekerslandenoverzicht

### Wat wordt nu geregistreerd (`nv_webshop_visits.py`)
Tabel `webshop_daily_visitors`: `day`, `visitor` (dagelijkse HMAC-pseudoniem van IP + browser + geheim), `first_seen`, `pageviews`, `last_path`, `last_at`.
- Geen IP-adres, geen browsertekst, geen cookie, geen land.
- Alleen met `NUVEMIXA_WEBSHOP_TRACKING=true` én het script op de webshop. Nu staat dit **niet** aan: er zijn geen echte cijfers.

**Conclusie:** de bestaande gegevens zijn *niet* genoeg voor een landenoverzicht. Het land is nergens vastgelegd en kan achteraf niet uit de pseudoniemen worden afgeleid (dat is bewust zo).

### Hoe kom je aan het land zonder IP op te slaan
| Optie | Werking | Nauwkeurigheid | Gevolg |
|---|---|---|---|
| A. Geo-header van een CDN/proxy (bv. Cloudflare `CF-IPCountry`) | Het land komt kant-en-klaar mee; er is geen IP-opzoeking in onze code | Hoog | Alleen mogelijk als de webshop achter zo'n dienst staat. Dat is nu niet zo (Alwaysdata). Vraagt DNS-wijziging |
| B. Lokale landentabel (bv. DB-IP Lite of GeoLite2) | IP wordt alleen in het geheugen opgezocht, direct weggegooid; alleen de 2-letterige landcode blijft | Hoog (land) | Extra bestand in de code, licentie/bronvermelding nodig, maandelijks bijwerken |
| C. Browsertaal/tijdzone | Geen IP nodig | Laag (taal ≠ land) | Alleen een schatting; niet aan te raden als "land" |

**Voorkeur:** B (of A als de webshop ooit achter een CDN komt).

### Benodigde databasewijziging (later, na toestemming)
Voorkeur: een **aparte aggregatietabel**, dus géén kolom bij individuele bezoekers:

```sql
CREATE TABLE webshop_daily_countries (
  day TEXT NOT NULL,            -- Nederlandse kalenderdag
  country CHAR(2) NOT NULL,     -- ISO-landcode, 'ZZ' = onbekend
  visitors INTEGER NOT NULL,
  pageviews INTEGER NOT NULL,
  PRIMARY KEY (day, country));
```
- Telt alleen per dag en land; er is geen koppeling met een persoon.
- Landen met minder dan 5 bezoekers per dag worden in het dashboard als "Overig" getoond (voorkomt herleidbaarheid).
- Dubbele telling: dezelfde regel als nu (`visitor` per dag uniek); het land wordt alleen opgehoogd bij de eerste hit van die dag.

### Privacy en AVG
- Een IP-adres is een persoonsgegeven. In optie B wordt het alleen kort in het werkgeheugen verwerkt om het land te bepalen, nooit opgeslagen of gelogd. Dat moet in de privacyverklaring staan (doel: anonieme bezoekersstatistiek, grondslag: gerechtvaardigd belang).
- Opslag is alleen landcode + aantallen: geen persoonsgegevens.
- Geen cookies, geen koppeling met bestellingen/accounts.
- Voor puur statistische meting zonder cookies is in Nederland meestal geen toestemming nodig. Dit is geen juridisch advies: laat de privacytekst en de gekozen grondslag controleren.
- Tracking blijft uit tot jij het expliciet aanzet.

### Echt of testdata
- Echte bezoeken komen alleen binnen van de toegestane webshop-oorsprong (`allowed_origins`); bots en dashboard-/admin-paden worden genegeerd.
- Voorstel: kolom/tabel krijgt geen testdata; testdata blijft in het testbestand/de tests. Het dashboard toont elk getal met de melding "echte metingen sinds <datum>".
- Het voorbeeld in `docs/voorbeeld-landenoverzicht.html` is **demonstratie**, duidelijk gemarkeerd, niet gekoppeld aan de app.

### Dashboardpagina
Onder Rapportages → Webshopbezoekers: kaart "Bezoekers per land" met horizontale balken (top 10 + Overig), periodeknoppen dag/week/maand/totaal, en een melding als landmeting nog niet is geactiveerd.

### Tests (te schrijven)
Land uit header/opzoeking, geen IP in database (bestaande test blijft), drempel "Overig", onbekend = `ZZ`, geen dubbele telling, tracking uit = niets opgeslagen, migratie herhaalbaar en zonder gegevensverlies.

---

## 4. Bezoekersstatistieken permanent bewaren

### Nu
- Zonder database-URL gebruikt de teller **SQLite op de Render-schijf**. Op Render Free is het bestandssysteem tijdelijk: bij elke herstart/slaapstand/deploy zijn die cijfers weg.
- `NUVEMIXA_DASHBOARD_DATABASE_URL` **wordt al ondersteund** (`nv_dashboard_postgres.configured()`): met die variabele schrijft de teller naar PostgreSQL, schema `nuvemixa_dashboard`, tabel `webshop_daily_visitors`.
- De 2FA-opslag is gescheiden: eigen modules (`nv_2fa_postgres*`), eigen schema/rol/sleutel. `DASHBOARD-POSTGRES.md` verbiedt dat het 2FA-schema wordt gebruikt.

### Wat moet er gebeuren (na jouw toestemming)
1. Een **aparte** PostgreSQL-database voor het dashboard (niet de 2FA-database).
2. Twee rollen: migratierol (eigenaar schema) en applicatierol (alleen SELECT/INSERT/UPDATE), zoals in `DASHBOARD-POSTGRES.md`.
3. Schema aanmaken met `nv_dashboard_postgres.sql`.
4. DSN in `NUVEMIXA_DASHBOARD_DATABASE_URL` (Render-variabele, door jou te zetten).
5. Bestaande SQLite-cijfers migreren met `migrate_dashboard_postgres.py` (eerst proefrun zonder `--apply`, daarna op de geïsoleerde database; weigert bestaande rijen, dus geen dubbele tellingen). Er zijn nu nog geen echte cijfers (tracking staat uit), dus er valt weinig te migreren.
6. Controle: telling vóór/na, dagelijkse export.

### Kosten (Render Postgres, opgezocht 17-11-2026; controleer op render.com/pricing vóór aanschaf)
- Gratis plan: bestaat, maar is niet geschikt voor blijvende opslag (Render laat gratis databases na korte tijd verlopen; de exacte termijn kon ik niet op de prijzenpagina bevestigen).
- Betaald: vanaf circa **$6 per maand** (256 MB), $19 per maand (1 GB). Extra opslag $0,30 per GB. Dit zijn nieuwe betaalde kosten, dus alleen na jouw akkoord.
- Back-ups: point-in-time herstel is volgens de prijzenpagina beschikbaar; het venster hangt af van je workspace-plan (3 of 7 dagen).

### Back-up en herstel
- Automatisch: PITR van Render (zie plan).
- Eigen extra: wekelijkse logische export (`pg_dump` van alleen schema `nuvemixa_dashboard`), bewaard buiten Render.
- Herstel: naar een **nieuwe** database herstellen, tellingen vergelijken, daarna de DSN omzetten. Een code-rollback herstelt nooit databasegegevens.
- Geen automatische terugval naar SQLite (zou stilletjes een tweede, afwijkende telling maken).

---

## 5. WooCommerce-koppeling

### Waarom "Niet gekoppeld"
Het dashboard (`nv_woo_bridge.read_configuration_present`) vereist **alle vier**: `NUVEMIXA_WOO_URL`, `NUVEMIXA_WOO_KEY`, `NUVEMIXA_WOO_SECRET`, `NUVEMIXA_WOO_HOST`. Ontbreekt er één (of staat de host niet gelijk aan de URL-host), dan is de status "Niet gekoppeld". Er is daarnaast een oudere set `WOOCOMMERCE_URL/CONSUMER_KEY/CONSUMER_SECRET` (gebruikt door de winkelkant in `app.py`). Die twee sets staan los van elkaar. Ik kan niet zien welke variabelen op Render staan en heb daar niets aan gewijzigd.

### Gewenste statussen
| Status | Voorwaarde | Kleur |
|---|---|---|
| Niet ingesteld | Geen of onvolledige variabelen | grijs |
| Geconfigureerd, niet getest | Alle vier aanwezig, nog geen geslaagde test | oranje |
| Verbonden | Laatste alleen-lezen test geslaagd (met tijdstip) | groen |
| Verbindingsfout | Test mislukt: reden zonder geheimen (sleutel geweigerd, host komt niet overeen, DNS, TLS, time-out) | rood |

Nooit "Verbonden" zonder een echte, geslaagde test.

### Veilige test (voorstel)
Knop "Test verbinding" (alleen eigenaar, POST met CSRF): één alleen-lezen `GET /wp-json/wc/v3/products?per_page=1` met bestaande bescherming (HTTPS-only, host-vergrendeling, DNS/SSRF-controle, time-out). Resultaat alleen als status + tijdstip in het geheugen. Foutmeldingen bevatten nooit URL-delen met sleutels of de sleutel zelf.

### Productpublicatie
Blijft zoals nu: alleen concept (`draft`), tweeledige goedkeuring (ondertekende goedkeuring voor exact deze productgegevens, 1 uur geldig) en `NUVEMIXA_WOO_WRITE=on` als aparte schakelaar. Er bestaat nog geen schrijfsleutelconfiguratie en geen zender; publiceren is nu onmogelijk.

### Veilige activering (stappen, voor later)
1. In WordPress (Alwaysdata): WooCommerce → Instellingen → Geavanceerd → REST API → sleutel met **alleen lezen** aanmaken (door jou). Niets delen in chat.
2. Op Render door jou: de vier `NUVEMIXA_WOO_*`-variabelen zetten.
3. Ik voeg (na akkoord) de statusknop en de vier statussen toe en test met nepdata.
4. Op de testbranch: alleen-lezen test. Pas daarna bespreken we een tweede sleutel met schrijfrechten voor concepten.
5. Publiceren blijft per product jouw expliciete goedkeuring.

---

## 6. Overlap met beveiligingshotfix PR #78

PR #78 (`hotfix/nuvemixa-2fa-omzeiling-20261117`, nog concept) is gebaseerd op `41fad63`, de huidige Live-integratiecommit. De moderniseringsbranch staat op dezelfde basis.

### Bestanden die in beide staan
`app.py`, `nv_dashboard_manager.py`, `templates/_dashboard_team.html`, `tests/test_staff_access.py`, `tests/test_supplier_workspace.py`.

### Vergelijking
| Onderdeel | PR #78 | Moderniseringsbranch |
|---|---|---|
| Medewerkers nooit eigenaar (`return False`) | ja | ja, identiek |
| `staff_login_enabled()` | alleen exact `on` | `on`, `1`, `true` of `yes`, standaard `off` |
| Aanmaken/inloggen alleen als schakelaar aan | ja | ja |
| Melding in `_dashboard_team.html` | ja | nee |
| Test `test_staff_access.py` | 153 regels | eigen versie |

**Verschil:** de hotfix is strenger (alleen `on`). De kopie op de moderniseringsbranch accepteert extra waarden. Dat is een inconsistentie die niet naast elkaar mag blijven bestaan. Daarnaast bevat de moderniseringsbranch niet-beveiligingswijzigingen in dezelfde bestanden (o.a. de concept-publicatieroutes en `staff_login_enabled=` in de template-context).

### Mergeproef (zonder iets te wijzigen: `git merge-tree`)
Conflicten in `app.py`, `nv_dashboard_manager.py` en `tests/test_staff_access.py`. Ze zijn klein en oplosbaar.

### Gecontroleerd op de moderniseringsbranch
Eigenaar met Google Authenticator blijft zoals het was (de 2FA-bestanden zijn niet aangepast). Een medewerker met rol `admin` wordt niet als eigenaar behandeld.

### Is PR #78 los uitrolbaar?
Ja, dat is technisch het veiligste: dezelfde basis als Live, klein (6 bestanden, +209/−2 regels), geen migratie. Let op één gevolg: de medewerkerslogin staat daarna standaard **uit**. Als er in productie medewerkers zijn die nu inloggen, verliezen die toegang tot `NUVEMIXA_STAFF_LOGIN=on` wordt gezet. Ik kan niet zien of die bestaan.

### Integratieplan (alles na jouw akkoord)
1. Eerst PR #78 afronden en apart uitrollen (jouw beslissing).
2. Daarna `integration` in de moderniseringsbranch samenvoegen en de conflicten oplossen door **de PR #78-versie van de beveiligingscode te houden** (strikt `on`), en de eigen kopie en testversie te laten vervallen.
3. Tests: `test_staff_access.py` van PR #78 plus de moderniseringstests; 42 Postgres-tests blijven apart gerapporteerd.
4. Pas daarna de modernisering voor te leggen.

Niets hiervan is uitgevoerd; PR #78 en #75 zijn niet aangeraakt.

---

## 7. Render-rollback en herstelplan

Bron: Render-documentatie "Rollbacks" (render.com/docs/rollbacks). Niets is uitgevoerd of herstart.

### Wat de documentatie zegt
- Rollback = een eerdere geslaagde deploy opnieuw kiezen in het dashboard (Deploys-pagina). Er start een nieuwe deploy op basis van het bewaarde build-artifact (snel, zonder opnieuw bouwen).
- **Een rollback via het dashboard zet automatische deploys uit.** Dat is hier belangrijk, omdat de integratiebranch automatisch deployt. Daarna moet je auto-deploy zelf weer aanzetten.
- Alleen deploys met een nog bewaard artifact zijn beschikbaar; het aantal hangt van het plan af.
- Terug gezet worden o.a. startcommando, health check en **omgevingsvariabelen van die deploy**. Disks en databases worden niet teruggezet. Recente wijzigingen in environment groups zitten niet in het artifact.
- Of dit voor **Render Free** geldt, staat niet op de pagina; dat kon ik niet bevestigen. Kijk in het Render-dashboard (Deploys → "Rollback") of de knop bij jouw dienst beschikbaar is.

### Gevolgen voor NUVEMIXA
- **SQLite op Render Free**: tijdelijk bestandssysteem; een rollback/herstart wist die gegevens sowieso. Een rollback is dus nooit een databaseherstel.
- **Eigenaarstoegang met 2FA**: de 2FA-gegevens staan in een eigen opslag, los van de code-rollback. Controleer wel dat de omgevingsvariabelen (o.a. geheime sleutel, 2FA-instellingen) tussen de te herstellen deploy en nu niet zijn gewijzigd, omdat een rollback variabelewaarden van de oude deploy terugzet.

### Alternatief: GitHub-revert
`git revert` van de wijzigende commit/PR op de integratiebranch en pushen. Render bouwt dan opnieuw (trager dan rollback) en auto-deploy blijft aan. Voordeel: het geschiedenisspoor is duidelijk en geen variabelen worden teruggezet.

### Praktisch herstelplan
1. **Vóór elke uitrol**: noteer de huidige werkende commit (nu `41fad63`) en de variabelen die gewijzigd worden.
2. **Bij een fout**: eerst de gezondheid controleren (`/dashboard` en eigenaarslogin met 2FA).
3. **Snelste herstel**: Render → Deploys → vorige geslaagde deploy → Rollback (indien beschikbaar). Daarna auto-deploy weer aanzetten.
4. **Als rollback ontbreekt**: GitHub → revert-PR/commit op de integratiebranch → laat auto-deploy bouwen.
5. **Controle**: inloggen als eigenaar met Google Authenticator, startpagina, Accountbeheer.
6. **Gegevens**: indien een database is gebruikt, herstellen via een database-herstel naar een nieuwe database; nooit aannemen dat de coderollback gegevens terugbrengt.
7. **Noodtoegang**: bewaar de herstelcodes van de eigenaar buiten het systeem (bestaande herstelprocedure blijft ongewijzigd).
