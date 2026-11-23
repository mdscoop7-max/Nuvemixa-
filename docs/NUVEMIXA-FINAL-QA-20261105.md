# NUVEMIXA — eindcontrole ontwikkelbranch (5 november 2026)

## Scope en bescherming

Repository: `mdscoop7-max/Trendmix`; branch: `design/pixel-polish-responsive-20261027`.
De bestaande NUVEMIXA-template, kleurenschema, categorie-hero's, alle vijf categorieën, Nederlandse en Engelse taalkeuze, en de Luvyza-omgeving zijn niet bewust gewijzigd door de administratieve updates. Geen push of herstart op Alwaysdata uitgevoerd.

## Bevestigd via GitHub-broncodecontrole

De volgende **20 statische codecontroles** zijn uitgevoerd op de huidige branch en leverden geen ontbrekende verwijzingen op:

1. Alle 19 geselecteerde bron- en testbestanden bestaan.
2. Vijf categorie-ID's aanwezig.
3. Vier bestaande afbeeldinghero-paden behouden.
4. Home & Living houdt oorspronkelijke producthero.
5. Alle acht gecontroleerde storefront- en admintemplates gebruiken de NUVEMIXA-PNG-verwijzing.
6. Mobiel uitschuifmenu heeft Home & Living.
7. Eenvoudige footer heeft hoofdlinks en geen niet-werkend nieuwsbriefinschrijfformulier.
8. Winkelwagen heeft CSRF-formulieren.
9. Winkelwagen heeft nieuwe styling voor desktop en mobiel.
10. Admincontrole schermt dashboard en adminroutes af.
11. Adminroutes krijgen `Cache-Control: no-store` en `X-Robots-Tag`.
12. Productgereedheidscheck voor Merchant Center is aanwezig.
13. WooCommerce-orders worden alleen opgehaald met GET in het nieuwe admindashboard.
14. SQLite-leverancierstabel is aanwezig.
15. SQLite-onderzoekstabel is aanwezig.
16. Admin-schrijfacties zijn POST-routes met authenticatie; globale CSRF-check blijft actief.
17. Dashboard heeft mobiele mediaregels.
18. Mobiele taalkeuze EN/NL bestaat nog.
19. Beide nieuwe Python-regressietestmodules bestaan.
20. De nieuwe GitHub Actions-workflow heeft publieke en beveiligde route-smoketests.

**Dit zijn statische checks, geen uitgevoerde end-to-end-tests.**

## Nieuwe werkende softwareonderdelen in de branch

- Dashboardlogin en uitloggen met hash-gebaseerd wachtwoord (mits `SECRET_KEY` en `NUVEMIXA_ADMIN_PASSWORD_HASH` correct ingesteld).
- Dashboardlogo + compactere afbeeldingen in de header en footer.
- Leveranciersregister: handmatig leverancierscontacten opslaan in een privé SQLite-database.
- Productonderzoek: eigen onderzoeksnotities opslaan; geen gefingeerde vraagcijfers.
- Bestellingen: alleen-lezen weergave van recente WooCommerce-orders indien een echte bestaande WooCommerce-API werkt.
- Merchant Center: per product overzicht van ontbrekende informatie, zonder publicatie.
- De compacte footer en moderne winkelwagenweergave met bestaande formulieracties.
- Nieuwe tests plus GitHub Actions-workflow voor tests bij branchwijzigingen.

## Niet bevestigd of geblokkeerd

**P0 — niet live zetten zonder verificatie:**

1. `static/nuvemixa-logo.png` ontbreekt momenteel in de GitHub-branch; de afbeeldingsverwijzing gebruikt fallback `logo.svg`. Upload het exacte aangeleverde PNG-bestand naar de server of voeg het als binaire GitHub-asset toe.
2. De GitHub Actions-testworkflow is aangemaakt, maar een **groene run is niet bevestigd** via de beschikbare GitHub-checks.
3. De huidige GitHub-commitstatus bevat meerdere mislukte/geblokkeerde Vercel-deploymentchecks. Vercel is niet de Alwaysdata-productieserver; hun status bewijst geen Alwaysdata-fout, maar is ook geen groen CI-bewijs.
4. Er is nog geen testresultaat van `python -m unittest ...` en `from wsgi import application` op de NUVEMIXA Alwaysdata-server.
5. Dashboardgeheimen `SECRET_KEY` en `NUVEMIXA_ADMIN_PASSWORD_HASH` moeten veilig in de NUVEMIXA-serveromgeving zijn ingesteld. Anders blijft het nieuwe dashboard bewust gesloten.
6. `NUVEMIXA_ADMIN_DB` moet naar een schrijfbare privélocatie buiten de public webroot wijzen, met passende bestandsrechten en back-upbeleid.
7. Mobiele en desktopbrowsercontroles op 320, 375, 390, 430, 768, 1024, 1440 en 1920 CSS-pixels zijn nog niet met screenshots uitgevoerd.

**P1 — externe integratie:**

- Echte leverancier/productfeeds met gecontroleerde voorraad, prijzen, afbeeldingen en btw.
- Merchant Center-account en Google Ads-koppeling; de productgegevens voldoen nog niet aantoonbaar aan Google Merchant-regels.
- Betaalprovider, veilige webhooks, orderstatusverificatie, terugbetalingen en fulfilment.
- RankFix AI API met gevalideerd bewijs en geen automatische mutaties zonder controles.
- Bronnen voor daadwerkelijk productvraag-/concurrentieonderzoek.
- Verkoop- en privacyinformatie, geregistreerde ondernemingsgegevens en betaal/lever/retourvoorwaarden vóór commerciële lancering.

## Go/no-go

**NO-GO voor echte betalingen, Google-advertenties en commerciële livegang.**

Code is naar de **GitHub-ontwikkelbranch** gepusht. De bestaande Alwaysdata-site is in deze ronde **niet bijgewerkt**. Na bevestigde back-up, correcte secret-configuratie, aanwezigheid logo en database, geslaagde WSGI-/unittests en mobiele browserchecks kan een afzonderlijke, gecontroleerde Alwaysdata-deployment volgen.

Zie ook `docs/NUVEMIXA-INTEGRATION-DEPLOY.md`.
