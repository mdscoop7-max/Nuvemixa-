# Trend Mix — Projectagenda

**Project:** Eigen Trend Mix dropshippingwebshop  
**Datum planning:** 26 oktober 2026  
**Werkbranch:** `seo/trendmix-content-audit-20261026`  
**Status:** voorbereid; taken niet automatisch als afgerond beschouwen. Geen merge/deploy voordat QA is geslaagd.  
**Belangrijk:** bestaande hero niet veranderen.

## Werkvolgorde — nu uitvoeren

### 1. Eerst: mobiele webshop, productpagina's en filters
- [ ] Mobiel menu en categorieën nalopen op veelgebruikte schermbreedtes.
- [ ] Productkaarten verbeteren: duidelijke foto's, prijs, winkelwagenknop en focus.
- [ ] Fotovergroting toetsenbord- en mobielvriendelijk testen.
- [ ] Productfilters voor categorie, prijs en eventueel merk toevoegen of controleren; bij ontbrekende gegevens geen nepfilters tonen.
- [ ] Desktopweergave en toegankelijkheid controleren.
- **Klaar wanneer:** navigatie, filters en winkelwagen in de browser werken op desktop en mobiel; geen overlap of afgesneden knoppen.

### 2. Daarna: SEO/GEO, klantenservice en footer
- [ ] SEO-titels, descriptions, canonicals, sitemap en interne links testen.
- [ ] Product JSON-LD en breadcrumb-gegevens op betrouwbaarheid controleren; geen onbevestigde voorraad of ratings.
- [ ] Klantenservice, levering, retouren, privacy, contact en footer op consistentie controleren.
- [ ] Betaallogo's als testvoorbeelden tonen totdat betaalmethoden echt actief zijn.
- [ ] Demo-reviews duidelijk als TEST / DEMO markeren, nooit als klantreview publiceren.
- [ ] RankFix op een geschikte QA-omgeving gebruiken zodra dat technisch mogelijk is.
- **Klaar wanneer:** betrouwbare inhoud, correcte metadata en geen misleidende claims; RankFix-resultaten kritisch op bewijs beoordelen.

### 3. Vervolgens: beheerdashboard en automatische tests
- [ ] Beheerdashboard of read-only productcontrole voorbereiden met ontbrekende productgegevens.
- [ ] Productgereedheid controleren: leverancier, rechten op afbeeldingen, voorraad, prijs en levertijd.
- [ ] Flask-regressietests en relevante frontendchecks uitvoeren.
- [ ] Fouten repareren zonder werkende functies of de hero onnodig aan te passen.
- **Klaar wanneer:** alle relevante controles slagen en open blokkades gedocumenteerd zijn.

## Later — uitsluitend wanneer voorwaarden zijn vervuld

### Google Shopping-advertenties
**Niet eerder dan:** echte producten én een volledig werkende en geteste checkout.
- [ ] Betrouwbare leveranciersproducten, actuele prijzen, voorraad en echte foto's.
- [ ] Betalingen veilig verwerken en orderstatus bevestigen.
- [ ] Verzend-, retour- en bedrijfsgegevens publiceren.
- [ ] Merchant Center-feed en conversiemeting activeren; advertentiebudget bepalen.
- [ ] Pas dan gecontroleerd campagnes starten.
**Blokkade:** geen betaalde Google Shopping-advertenties met demoproducten of testcheckout.

### Echte klantreviews
**Niet eerder dan:** er zijn daadwerkelijke klantbestellingen.
- [ ] Reviews verzamelen volgens een controleerbaar en privacybewust proces.
- [ ] Echte klantbeoordelingen modereren op authenticiteit, niet op sentiment.
- [ ] Pas na verificatie echte sterren en beoordelingsmarkup gebruiken.
**Blokkade:** demo-reviews tellen nooit mee in een beoordeling en mogen niet als echt worden gepresenteerd.

## Afgesproken grenzen
- Hero volledig onaangeroerd houden.
- Werken op `seo/trendmix-content-audit-20261026`.
- Geen merge naar `main` en geen livepublicatie zonder test en akkoord.
- Betalingen en leverancierskoppelingen later; nu geen productclaims verzinnen.
- Trend Mix blijft eigen webshop voor inkomsten; RankFix later inzetten voor kwaliteitscontrole.

**Planning zonder vaste data:** er zijn nog geen deadlines of gereserveerde agenda-uren afgesproken; de volgorde is leidend.
