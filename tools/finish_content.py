"""Content/data preparation. Does not activate campaigns or write customer data."""
import json,re
from pathlib import Path
R=Path(__file__).resolve().parent.parent
def read(path):return path.read_text(encoding='utf-8')
def write(path,value):path.write_text(value,encoding='utf-8')
relations={
 '/lifestyle-sport/yogamat':[
 ('/lifestyle-sport/weerstandsbandenset','Een apart trainingsaccessoire voor een gevarieerde sportroutine; productspecificaties nog te controleren.','A separate training accessory for a varied exercise routine; product specifications still need checking.'),
 ('/lifestyle-sport/foamroller','Een aanvullend sportaccessoire; geen medische of compatibiliteitsclaim.','A complementary exercise accessory; no medical or compatibility claim.'),
 ('/lifestyle-sport/geisoleerde-sportdrinkfles','Een drinkfles voor onderweg naar je training; definitieve eigenschappen nog onbevestigd.','A bottle for travelling to your workout; final properties remain unconfirmed.'),
 ('/lifestyle-sport/sporttas','Een tas voor sportbenodigdheden. Of je mat erin past is niet bevestigd.','A bag for exercise essentials. Fit for your mat is not confirmed.')],
 '/home-living/opvouwbare-laptoptafel':[
 ('/home-living/bureau-organizer','Voor het apart ordenen van kleine werkbenodigdheden. Afmetingen zijn nog onbevestigd.','For separately organising small work items. Dimensions remain unconfirmed.'),
 ('/home-living/kabelorganizer','Voor het ordenen van kabels naast je werkplek; geen bevestigde pasvorm.','For organising cables alongside your workspace; fit is not confirmed.')],
 '/lifestyle-sport/reisorganizerset':[
 ('/lifestyle-sport/digitale-bagageweegschaal','Om bagage afzonderlijk te wegen vóór vertrek; geen bevestigde meetnauwkeurigheid.','For separately weighing luggage before travel; measurement accuracy is not confirmed.'),
 ('/lifestyle-sport/opvouwbare-waterfles','Een los reisaccessoire; eigenschappen nog te controleren.','A separate travel accessory; properties still need checking.')]
}
write(R/'content/product-relations.json',json.dumps({key:[{'product_url':url,'reason_nl':nl,'reason_en':en,'compatible':False} for url,nl,en in rows] for key,rows in relations.items()},ensure_ascii=False,indent=2))
for name in ['_storefront_card.html','_product_card.html']:
 p=R/'templates'/name;s=read(p);s=s.replace('<strong>{{ format_eur(product.price) }}</strong>','{% if product.demo %}<span class="nv-demo-label">{{ nv_tr("Voorbeeldproduct","Demonstration product") }}</span>{% endif %}<strong>{{ format_eur(product.price) }}</strong>');write(p,s)
p=R/'templates/product.html';s=read(p);s=s.replace('<div class="detail-actions">','{% if product.demo %}<p class="nv-demo-label">{{ nv_tr("Voorbeeldproduct — geen bevestigd verkoopartikel","Demonstration product — not a verified sale item") }}</p>{% endif %}<div class="detail-actions">');write(p,s)
p=R/'app.py';s=read(p).replace('source = info_doc["nl"] if info_doc else page','source = info_doc[getattr(__import__("flask").g, "nv_language", "nl")] if info_doc else page');write(p,s)
# Declare current local processing accurately, alongside the existing consumer-law explanations.
append={
 'privacy':('Lokale account- en testverwerking',['De lokale testomgeving verwerkt accountnaam, e-mailadres, wachtwoordhash, verificatie- en hersteltokens (gehasht), persoonlijke favorieten en simulatieorders. E-mailberichten staan uitsluitend in een afgeschermde lokale testpostbus. Er worden geen echte betalingen, externe e-mails of betaalde AI-aanroepen uitgevoerd. Gebruik uitsluitend fictieve testgegevens.','VERPLICHT NOG IN TE VULLEN: verantwoordelijke onderneming, privacycontact, definitieve bewaartermijnen, verwerkers en eventuele doorgiften. Deze informatie en de verwijder-/inzageprocedure moeten juridisch worden gecontroleerd vóór commerciële vrijgave.'], 'Local account and test processing',['The local test environment processes account name, email, password hash, hashed verification and reset tokens, personal favourites and simulated orders. Emails remain in a protected local test mailbox. No real payments, external emails or paid AI calls are made. Use fictitious test information only.','REQUIRED BEFORE RELEASE: controller identity, privacy contact, final retention periods, processors and any international transfers. This information and the access/deletion procedure need legal review before commercial release.']),
 'cookies':('Huidige functionele opslag',['De website gebruikt een ondertekende HttpOnly-sessie voor winkelwagen, authenticatie en beveiliging. Een taalvoorkeur wordt in een first-partycookie bewaard; de historische lokale taalkey blijft voor compatibiliteit bestaan. De PWA-serviceworker bewaart geen pagina’s, persoonsgegevens of prijzen in een offlinecache.','Tracking en marketing zijn niet geactiveerd. Bij toekomstige niet-noodzakelijke tracking moet vooraf worden vastgesteld welke toestemming nodig is en hoe die even eenvoudig kan worden ingetrokken.'], 'Current functional storage',['The website uses a signed HttpOnly session for cart, authentication and security. A first-party cookie stores language preference; the historical local language key remains for compatibility. The PWA service worker does not store pages, personal information or prices in an offline cache.','Tracking and marketing have not been activated. Before adding non-essential tracking, determine the required consent and an equally easy withdrawal method.']),
 'retouren':('Lokale herroepingsfunctie en ontbrekende gegevens',['Via de blijvende link “Overeenkomst herroepen” in de footer kun je de lokale simulatieovereenkomst ondubbelzinnig herroepen. Een account is niet verplicht. Het systeem registreert datum en tijd en zet een ontvangstbevestiging in de lokale testpostbus.','NOG AAN TE VULLEN: definitieve verkoper, retouradres, praktische retourinstructies en definitieve contactgegevens. Er worden in deze omgeving geen echte aankopen verwerkt. Juridische controle vereist vóór commerciële vrijgave.'], 'Local withdrawal function and missing details',['The permanent “Withdraw from a contract” footer link allows an unequivocal withdrawal from the local simulated contract. An account is not required. The system records the date and time and queues an acknowledgement in the local test mailbox.','STILL REQUIRED: final seller, returns address, practical returns instructions and final contact information. This environment does not process real purchases. Legal review is required before commercial release.']),
 'voorwaarden':('Commerciële vrijgave geblokkeerd',['Alle voorbeeldproducten en orders zijn demonstraties. Een lokale simulatiebetaling is geen koop, afschrijving of bewijs van een werkende productiebetaling. Verplichte bedrijfs-, verzend- en retourgegevens zijn nog niet definitief.','Toekomstige persoonlijke kortingscodes gelden alleen volgens de actievoorwaarden en actieve periode. Een beloning voor een eerlijke aankoopreview is onafhankelijk van het aantal sterren of de keuze tot publicatie. Campagnes staan standaard uit.'], 'Commercial release blocked',['All demonstration products and orders are examples. A local simulated payment is not a purchase, charge or proof of a functioning production payment. Required business, shipping and returns information is not final.','Future personal coupons apply only under campaign terms and the active period. A reward for an honest purchase review is independent of the rating or publication decision. Campaigns are disabled by default.'])}
for slug,(title,nl,etitle,en) in append.items():
 p=R/'content/information'/(slug+'.json');d=json.loads(read(p))
 if not any(section[0]==title for section in d['nl']['sections']):d['nl']['sections'].append([title,nl]);d['en']['sections'].append([etitle,en])
 write(p,json.dumps(d,ensure_ascii=False,indent=2))
# Modern explicit CI: no empty unittest pattern, no network during tests, patched framework.
workflow='''name: NUVEMIXA local acceptance
on: [push, pull_request, workflow_dispatch]
permissions:
  contents: read
jobs:
  acceptance:
    runs-on: ubuntu-latest
    env:
      SECRET_KEY: ci-test-key-not-for-production
      NUVEMIXA_COOKIE_SECURE: "false"
      NUVEMIXA_ENV: local
      NUVEMIXA_STORE_DB: /tmp/nuvemixa-ci/store.sqlite3
      NUVEMIXA_CUSTOMER_DB: /tmp/nuvemixa-ci/customers.sqlite3
      NUVEMIXA_REVIEWS_DB: /tmp/nuvemixa-ci/reviews.sqlite3
      NUVEMIXA_SSO_USED_DB: /tmp/nuvemixa-ci/sso.sqlite3
      NUVEMIXA_ADMIN_DB: /tmp/nuvemixa-ci/store.sqlite3
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install -r requirements.txt pytest
      - run: mkdir -p /tmp/nuvemixa-ci
      - run: python -m pytest tests -q -p no:cacheprovider
'''
write(R/'.github/workflows/nuvemixa-integration.yml',workflow)
write(R/'.github/workflows/trendmix-tests.yml','''# Compatibility filename retained; the complete suite is defined in nuvemixa-integration.yml.
name: NUVEMIXA source syntax
on: [push, pull_request]
permissions:
  contents: read
jobs:
  syntax:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: python -m compileall -q app.py nv_store.py nv_platform.py nv_presentation.py
''')
print('Prepared source content, labelled demos, editorial relationships and CI.')
