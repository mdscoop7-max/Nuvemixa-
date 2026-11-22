# NUVEMIXA — eindcontrole en herstel (22-11-2026)

Live site: https://nuvemixa.alwaysdata.net/ · GitHub-branch: `ccr-3ad6edb4-zfvkje`

## 1. Belangrijkste vaststelling: live wijkt af van GitHub

- De live site gebruikt bestanden die in **geen enkele GitHub-branch** staan:
  `nv-hero-2026.css`, `nv-fix-20261120e.js`, een nieuwe Home & Living-hero (`nv-hl-new`) en een oudere `app.py`.
- De deploy-workflow `.github/workflows/deploy-nuvemixa.yml` is 2× mislukt. Oorzaak: de secret
  `NUVEMIXA_SSH_HOST` is ongeldig ("hostname contains invalid characters"). Daarnaast rolt de workflow
  een oude branch uit (`design/pixel-polish-responsive-20261027`) via een remote-check op `mdscoop7-max/Trendmix`.
- Een branch uitrollen zou daardoor live-werk overschrijven. Daarom zijn de verbeteringen gemaakt als
  **losse correctielaag** plus een **beveiligd patchscript** dat alleen exact herkende stukken aanpast.

**Gepubliceerd op 22-11-2026, 13:18 UTC.** De eigenaar voerde het pakket uit via SSH (gebruiker `nuvemixa_deploy`) en herstartte daarna de site.
- Back-ups vóór de wijziging: `~/backups/nuvemixa-pre-polish-20261122-131724.tar.gz` en `-131758.tar.gz`.
- Controle op de server: "RESULTAAT: OK".
- Live gecontroleerd: correctielaag op alle pagina's (CSS/JS 200), overal precies één H1, `offers: null` weg, hero-afmetingen gelijk aan vóór, geen horizontale overloop.
- Opmerking: het account zat aan zijn opslaglimiet. Daarom is `~/.cache` (pip-cache, 20 MB) geleegd en zijn alleen de 5 benodigde bestanden gedownload.
- Opmerking: `nuvemixa_deploy` mag `wsgi.py` niet lezen. Herstarten gaat daarom via het beheerpaneel (Web → Sites).
- Terugdraaien: `NUVEMIXA_BACKUPS=~/backups bash ~/nv-kit/deploy/alwaysdata-20261122/rollback.sh` en daarna de site herstarten.

## 2. Back-up (vóór elke wijziging)

- Volledige spiegel van de publieke live site: 265 bestanden, 30 MB (HTML, CSS, JS, afbeeldingen).
- `apply.sh` maakt op de server opnieuw een gecontroleerde tar-back-up van `app.py` en `templates/`
  vóór toepassen. Je kunt altijd terug met `rollback.sh`.

## 3. Gevonden fouten en reparaties

| # | Probleem (live) | Status | Reparatie |
|---|---|---|---|
| 1 | Blauwe header zonder afgeronde onderhoeken (het blauw komt van `border-image`, dat `border-radius` negeert) | Opgelost | Het onderste blauwe deel gebruikt nu een identieke gradient als achtergrond, met een afronding van 24 px. Werkt op alle paginatypes. |
| 2 | Oranje randlijn rond het categorieblok, die bij #1 zichtbaar werd | Opgelost | `border-color: transparent` |
| 3 | Header op mobiel te hoog | Opgelost | 140 → 132 px (en 133 → 125 px op 320 px breed) |
| 4 | Zoekbalk heeft 3 varianten (icoon, alleen "Zoeken", blauwe pil), plus verschillende placeholders | Opgelost | Overal dezelfde balk: 46/48 px, navy knop, op desktop icoon + "Zoeken", in NL en EN. Tekst 16 px, zodat iOS niet inzoomt. |
| 5 | Hero "Alle Producten" staat lager: 26 px op mobiel, 50 px op desktop | Opgelost | Padding van `legacy-main` en `.shop-page` weggehaald. Staat nu exact gelijk met de andere hero's. |
| 6 | Breedte van de desktop-hero hangt af van de vensterhoogte (`calc((100vh - 290px) * 2.2)`) | **Bewust ongewijzigd (op verzoek)** | De hero's blijven precies zoals live; gecontroleerd: 0 afwijkingen op 9 formaten. |
| 7 | Reviews tonen een afwijkend logo (tasje met "M") | Opgelost | Zelfde bestand als het headerlogo (`nuvemixa-logo-test.png`) |
| 8 | Reviews tonen "0,0 / 5" terwijl er geen reviews zijn | Opgelost | Bij 0 reviews staat er "Nog geen beoordelingen" (EN: "No ratings yet") |
| 9 | Product-/winkelwagenpagina's op desktop: "Account" afgekapt en de winkelwagenteller zweeft aan de rand van het scherm | Opgelost | Knoppen krijgen ruimte en de teller zit op de knop zelf |
| 10 | Tablet (761–1000 px): account-/winkelwagenknop over de zoekbalk, "Aanbiedingen" buiten beeld, taalkeuze buiten beeld | Opgelost | Zoekbalk begrensd, categoriebalk compacter, infobalk toont 2 punten |
| 11 | SEO: `"offers": null` op alle 100 productpagina's (stock_status = unknown) | Opgelost in code en patch | Offer met prijs/EUR/conditie. `availability` alleen als die bekend is (geen verzonnen voorraad). Geen `null`-waarden meer, afbeeldings-URL's absoluut. |
| 12 | SEO: H1 ontbreekt op Home & Living | Opgelost via patch | `<h2>` → `<h1>`. Het script controleert daarna dat er precies één H1 is en zet de wijziging anders terug. |
| 13 | SEO: winkelwagen zonder canonical | Opgelost in code | `X-Robots-Tag: noindex, follow` op winkelwagen, afrekenen en favorieten |
| 14 | SEO: `/over-nuvemixa` canonical → `/over-trendmix`, dubbele titel | **Al opgelost in GitHub `main`, niet live** | Live `app.py` is verouderd. Het patchscript meldt dit (wijzigt `app.py` niet automatisch). |
| 15 | Gebroken interne links / 404 | Geen gevonden | 121 interne URL's gaven 200. Alleen `/dashboard` geeft 302 (login). |
| 16 | Ontbrekende/dubbele paginatitels | Alleen #14 | De lege titel op /shop was witruimte; geen fout |

## 4. Bewust ongewijzigd

- **Hero's op desktop: afmetingen en weergave exact zoals live (op verzoek).**
- Logo's, blauw/oranje kleuren, hero-afbeeldingen, het witte "Menu & categorieën"-blok, de paarse AI-knop
  en de blauwe onderste navigatie zijn niet aangepast.
- **Productfoto's**: de catalogus bevat geen echte productfoto's, alleen willekeurige stock-URL's (loremflickr/unsplash
  op trefwoord). De categorie-icoon-placeholders zijn dus correct. Er is niets verzonnen of gekoppeld.
  Prijzen en productgegevens zijn niet aangepast.
- Er zijn geen testreviews op live geplaatst. Het formulier is alleen client-side getest.
- Er zijn geen bestellingen of betalingen gedaan. De checkout is getest tot vóór het verzenden.
- Mobiele hero's houden hun eigen beeldverhouding (afbeeldingen ongewijzigd).
- **Render, Neon en de 2FA-database zijn niet aangeraakt.**

## 5. Testresultaten

Getest op de echte live HTML, met de correctielaag geïnjecteerd:

- Schermformaten: 320×640, 360×740, 390×844, 430×932, 768×1024, 1024×768, 1366×768, 1920×1080 en 1920×600.
  Geen horizontale overloop.
- Functioneel geslaagd:
  - zoeken (Enter en knop)
  - 7 categorieën
  - menu
  - productpagina
  - toevoegen aan winkelwagen
  - aantal +1 (€34,95 → €69,90)
  - verwijderen
  - afrekenpagina
  - favorieten
  - taal EN
  - reviews: logo, lege toestand, formulier opent, leeg formulier geweigerd
  - AI-chatbot opent
  - 5 navigatieknoppen (allemaal HTTP 200)
  - laatste producten en footer eindigen boven de navigatiebalk
- Python-tests: 76 geslaagd, 1 overgeslagen, 1 mislukt. De mislukte test is `test_nv_storage_paths`; die faalde al vóór deze wijzigingen en staat er los van. Er zijn 3 nieuwe regressietests toegevoegd.
- Patchscript gesimuleerd op twee kopieën (de neon-reviews-branch en `main`), allebei met een droge run, uitvoering,
  render-controle en terugdraaien. Na het terugdraaien was er 0 verschil.

### Resterende aandachtspunten
1. **JS-fout op live** (bestond al, los van deze wijzigingen): `Identifier 'commerceTranslations' has already been declared`
   op product- en winkelwagenpagina's (`languages.js`).
2. `/over-trendmix` → 301 en canonical: neem de routes uit GitHub `main` over in de live `app.py`.
3. De deploy-secret `NUVEMIXA_SSH_HOST` herstellen (alleen de hostnaam, zonder `ssh://`, gebruiker of spaties).
   Pas daarnaast de workflow aan (branch en repo-naam) **voordat** je hem gebruikt.
4. Echte productfoto's toevoegen zodra die er zijn.
5. Live en GitHub weer gelijktrekken: de handmatige serverbestanden committen.

## 6. Publiceren op Alwaysdata (door iemand met SSH-toegang)

```bash
cd /home/nuvemixa && git clone --depth 1 -b ccr-3ad6edb4-zfvkje https://github.com/mdscoop7-max/Nuvemixa-.git nv-kit
bash nv-kit/deploy/alwaysdata-20261122/apply.sh            # back-up + droge run
bash nv-kit/deploy/alwaysdata-20261122/apply.sh --apply    # toepassen + controle + herstart
# terugdraaien indien nodig:
bash nv-kit/deploy/alwaysdata-20261122/rollback.sh
```
Controleer daarna de live site met Ctrl+F5 op mobiel en desktop.

## 7. Screenshots
De live-situatie na publicatie staat in `screenshots/live/`.
Zie de map `screenshots/`. Daarin staan vóór/na-vergelijkingen per formaat (`mobiel-*.jpg`, `tablet-*.jpg`, `desktop-*.jpg`),
uitsneden van de header en de reviews (`voor-*`, `na-*`) en `tablet-header-voor-na.png`.
