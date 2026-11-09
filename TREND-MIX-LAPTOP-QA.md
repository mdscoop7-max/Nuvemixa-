# Trend Mix — checklist voor de laptopcontrole

## Klaargezet op ontwikkelbranch
Branch: `seo/trendmix-content-audit-20261026`.
Niets is naar `main` gemerged of naar productie gedeployed. De bestaande homepagehero is niet aangepast.

## Laptop: ophalen
```powershell
cd C:\Users\user\Desktop\Trendmix-test
git status
git fetch origin
git pull --ff-only origin seo/trendmix-content-audit-20261026
python -m pytest -q
python app.py
```
Let op: inspecteer eventuele lokale onopgeslagen bestanden met `git status` voordat je schakelt. Gooi niets weg.

## Functionele en visuele QA
1. Desktop (1440px), tablet (768px), mobiel (390px, 375px en 320px): productrasters, zoekbalk, filters, navigatie, productfoto's/zoom, footer, NL/EN; geen horizontale scroll.
2. Homepagehero vergelijken met vorige versie: tekst, animatie, afbeeldingen en afmetingen moeten ongewijzigd zijn.
3. `/faq`, `/contact`, `/bestellen`, `/retouren`, `/privacy`, `/cookies`, `/voorwaarden`, `/over-trendmix`: correcte teksten, links en mobiele leesbaarheid.
4. Test contactformulier zonder RESEND-config: toont duidelijk dat verzenden niet beschikbaar is; mag nooit succes veinzen.
5. Productpagina: demo-review is standaard verborgen; alleen zichtbaar met lokale `TRENDMIX_SHOW_DEMO_REVIEWS=1`, nooit op Vercel. Echte reviews nog niet actief.
6. Winkelwagen: plus/min, verwijderen, lege winkelwagen, aantallen maximaal 99 en actuele productprijzen; productsubtotaal klopt.
7. `/afrekenen`: vermeldt duidelijk testfase; verzendkosten zijn nog onbekend; gebruik fictieve klantgegevens. Geen echte betaling/order bevestigen.
8. SEO: juiste titel, meta description, canonical, JSON-LD en sitemap. Demo-producten zijn `noindex` en staan niet in sitemap.
9. `/beheer`: standaard 404; bij geldige testcredentials alleen-lezen, nooit publiek openzetten.
10. Test veiligheidsheaders, CSRF op formulieren en GitHub Actions-status.

## Voor commerciële livegang — nog niet voltooid
- EU-dropshippingleveranciers contractueel vastleggen; authentieke feed en afbeeldingsrechten, actuele prijs/voorraad/levering.
- Werkende betaalprovider, betaalbevestiging, bestelverwerking, retourafhandeling en controle op verzendkosten.
- Werkend beheerdashboard met beveiligde persistente productmutaties en auditlog.
- Echt reviewproces: alleen reviews van gekoppelde, geverifieerde aankopen publiceren; geen demodata of nepsterren.
- Contact-e-mail koppelen en testen. Wettelijke bedrijfsgegevens en toepasselijke consumenteninformatie invullen en juridisch controleren.
- Visuele laptopcontrole vóór een merge of publicatie; geen automatische publicatie.

## Designwijzigingen van 27 oktober 2026
- Lichtblauwe webshopfilters, labels, sortering en knoppen: CSS in `static/trendmix-forms-polish.css`.
- Taalopties afzonderlijk onder elkaar met vlaggen en actieve status. `static/storefront-language.js` schakelt de taal van zichtbare zoek- en filterknoppen. **Nog geen volledige Engelse vertaling van alle pagina- en productteksten**; dit moet vóór meertalige livegang worden voltooid.
- Productbeschikbaarheid, compacte categorienavigatie, categoriekaarten en lijniconen visueel vernieuwd.
- Beheerdashboard visueel vernieuwd; **uitsluitend lezen**, zonder wijzig-/bestelfuncties.
- De homepagehero blijft intact; geen merge of productiepublicatie.

## Nog te bouwen / externe blokkades
1. **Productbeheer**: database, mutaties van producten en foto's, rolgebaseerde beveiliging, uploadvalidatie, auditlog, backups en conflictbehandeling.
2. **Dropshipping**: leverancierkeuze, contract, API-inloggegevens, echte catalogus, voorraad- en prijs-sync, retour- en leverafspraken, margecontrole.
3. **Betaling en orders**: PSP-account, echte betaalbevestiging via beveiligde webhook, idempotente orderverwerking, verzending en terugbetalingen.
4. **Volledige NL/EN-vertalingen**, incl. beleidspagina's, checkout, foutmeldingen en SEO-hreflang na correcte URL-strategie.
5. **Klantenservice/compliance**: zakelijk e-mailadres, werkende aflever- en retourscenario's, actuele bedrijfsgegevens en definitieve juridische teksten.
6. **Veiligheid/QA**: volledige laptopreview op mobiel/desktop, betaalflow in testomgeving, daarna RankFix-scan (lokale adressen alleen als scanner dit veilig ondersteunt).
Een groene GitHub Actions-run vervangt geen handmatige visuele of betaal-/leveringstest.

## Extra dashboardcontrole (27 oktober)
- Nieuwe beveiligde read-only pagina `/beheer/lancering`, bereikbaar via het beheerdashboard. Toont acht afzonderlijke blokkades voor echte verkoop, bewust niet automatisch als "gereed" op basis van alleen configuratievariabelen.
- Automatische regressietest: pagina zonder credentials verborgen, met credentials afgeschermd, `noindex` en `no-store`; onbetrouwbare claims blijven uit.
- Volgende bouwfase (afhankelijk van echte aansluitingen): productdatabase en publicatievalidatie; EU leverancier-feedadapter; veilige betaalwebhook/idempotente orderverwerking; admin auditlog en backups; volledige meertaligheid. Niet activeren zonder accounts en testbewijs.

## NL/EN en klantenservice, 27 oktober
- De bestaande tweetalige informatie- en juridische teksten in `info.html` worden nu geactiveerd door `static/trendmix-bilingual-pages.js`; de contactpagina toont tweetalige ondersteunende teksten en een duidelijk bedrijfsinformatieblok.
- Er is **geen** KvK-, btw-, adres- of supportmailadres verzonnen. Deze moeten door de eigenaar worden bevestigd; e-mailverzending blijft afhankelijk van geldige Resend-configuratie.
- Nieuwe tests staan in `tests/test_bilingual_support_pages.py`.
- Nog af te maken vóór productie: alle product- en checkoutteksten, foutmeldingen en volledige header/footer consequent meertalig maken, en echte taal-URL's/hreflang voor SEO. De huidige taalkeuze is nog browsergebaseerd, niet volledig server-side.
