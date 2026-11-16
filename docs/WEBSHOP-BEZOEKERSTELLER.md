# Webshopbezoekers (cookievrij)

De teller telt alleen echte paginaweergaven van de publieke webshop, nooit het dashboard.

## Activeren (handmatig, eenmalig)
1. **Permanente opslag**: zet `NUVEMIXA_DASHBOARD_BACKEND=postgres` en `NUVEMIXA_DASHBOARD_DATABASE_URL` op Render en voer de SQL uit `nv_dashboard_postgres.sql` uit (tabel `nuvemixa_dashboard.webshop_daily_visitors`; geef de app-rol INSERT/UPDATE/SELECT). Zonder PostgreSQL gebruikt de app SQLite en gaat de telling bij een Render-herstart verloren; het dashboard waarschuwt hiervoor.
2. Zet `NUVEMIXA_WEBSHOP_TRACKING=true` op Render. Andere domeinen dan `https://nuvemixa.alwaysdata.net`: `NUVEMIXA_WEBSHOP_ORIGINS=https://domein1,https://domein2`.
3. Plaats in de webshop (onder eigen beheer): `<script src="https://trendmix.onrender.com/static/nv-webshop-visit.js" defer></script>`
4. Werk de privacyverklaring bij (zie hieronder) voordat je activeert.

## Telregels
- Bezoeker = dagelijkse pseudoniem (HMAC van IP + browser, zout wisselt per Nederlandse dag). Geen cookie, geen IP-opslag.
- Week (maandag start), maand en totaal tellen bezoekersdagen. Tijdzone Europe/Amsterdam.
- Herladen van dezelfde pagina binnen 30 minuten telt niet als nieuwe paginaweergave.
- Bots, healthchecks, prefetch, Do Not Track en Global Privacy Control worden niet geteld.

## Privacy
Zonder cookies of apparaatopslag en zonder bewaard IP-adres is er geen cookietoestemming nodig voor deze teller; vermeld de anonieme meting wel in de privacyverklaring. Dit is geen juridisch advies.
