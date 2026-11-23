# NUVEMIXA — lokaal gebruik en afzonderlijke acceptatie

Deze ronde publiceert niets. De lokale voorbeeldwebshop staat los van Alwaysdata,
Render, Neon, Vercel en een extern dashboard. `nv_store.py` met de geconfigureerde
private SQLite-database is de leidende lokale bron voor productoverrides,
publicatie, prijzen/aanbiedingen, coupons, orders, favorieten en testcommunicatie.
De bestaande JSON-catalogus blijft de bron van 100 herkenbare voorbeeldartikelen
en hun blijvende URL’s. Klantcredentials blijven in de bestaande klantdatabase;
nieuwe aanvullende accountstatus wordt aan de numerieke klant-ID gekoppeld.
Een later extern dashboard moet deze services gebruiken, geen tweede losse
voorraad-/couponadministratie aanmaken.

## Lokaal starten

Voer in `NUVEMIXA-LOKALE-TEST` uit: `python -B tools/run_local.py --demo-admin`.
De preview gebruikt `http://127.0.0.1:5001`. De tijdelijke beheerlogin staat alleen
in `.repair-state/local-admin.txt`. Dit bestand is testdata, wordt niet gekopieerd
naar de werkmap en mag nooit worden gepubliceerd. De launcher blokkeert uitgaande
netwerk-/mailaanroepen en wist geërfde providercredentials uit zijn eigen proces.
De privésessie gebruikt een eigen cookienaam. Het gewone werkproject krijgt geen
demo-adminwachtwoord of echte klantdata uit deze omgeving.

Werkmap: herstelpunt onder `herstelpunten/voor-afwerking-20261123-165244`.
Code/assets zijn bewaard, klantdatabases en secrets zijn bewust niet gekopieerd.
Gebruik het manifest om specifieke bronbestanden gecontroleerd terug te zetten;
overschrijf nooit klantdata met testdata. Geen automatische rollback uitvoeren.

## Beheer

`/admin/commerce` is het lokale hoofdbeheer; bestaande dashboard/control-URL’s
blijven beveiligde ingangen. Daar kunnen leveranciers, productconcepten,
handmatige verificatie, publicatie, voorraad/prijzen, gedateerde aanbiedingen,
gecurateerde productrelaties, welkomst-/reviewcampagnes en testorders worden
beheerd. De gewone formulieren vereisen geen JSON/programmeerwerk.

Een productwijziging maakt het product opnieuw concept. Alleen echte, volledig
gecontroleerde gegevens kunnen worden gepubliceerd. Varianten zijn als concept
te documenteren; verkoop van varianten vereist nog een afzonderlijk geaccepteerde
variantkeuze-/voorraadketen en is daarom geblokkeerd. Voorbeeldproducten geven
nooit echte orders. Actieprijzen vragen expliciet gecontroleerde referentieprijs-
informatie; dit bewijst niet automatisch juridische juistheid van de aangeleverde
gegevens. Campagnes worden niet tijdens deze ronde geactiveerd.

Bijpassende producten komen alleen uit de bestaande catalogus, via beschreven
redactionele relaties. Compatibiliteit mag alleen met bewijs worden geclaimd.
Ontbreekt een goede relatie, dan worden geen willekeurige producten getoond.

## Configuratie en privéopslag

Gebruik afzonderlijke, persistente private paden voor `NUVEMIXA_STORE_DB`,
`NUVEMIXA_CUSTOMER_DB`, `NUVEMIXA_REVIEWS_DB`, `NUVEMIXA_SSO_USED_DB` en
`NUVEMIXA_ADMIN_DB`. Productie-commerceopslag moet buiten de checkout staan.
`NUVEMIXA_ENV=production` vereist een beheerde vaste `SECRET_KEY`; lokaal wordt
een eigen sleutel exclusief aangemaakt. `NUVEMIXA_COOKIE_SECURE` blijft standaard
true; alleen de geïsoleerde HTTP-launcher zet dit false. `SITE_URL` moet later de
echte HTTPS-origin zijn. Geen credentials in Git, logs of dit document opnemen.

Sessies, tokens en private pagina’s zijn niet publiek cachebaar. Review-SSO zet
alleen de reviewrol. Proxyheaders worden niet rechtstreeks als klant-IP vertrouwd;
configureer een eventuele vertrouwde proxylaag pas voor de echte hostingketen.

Back-up/herstel: `python tools/manage_storage.py backup BRON NIEUW_PRIVEBESTAND`.
Dezelfde controle met `restore` maakt een nieuwe gecontroleerde database, zonder
een bestaande te overschrijven. Het omschakelen van productieconfiguratie blijft
een aparte operatorhandeling. Herstel is met fictieve data getest; een echte
bedrijfsbrede recoveryprocedure, encryptie/toegangsrechten en retentie moeten nog
operationeel worden vastgesteld. Het onbekende binaire bestand staat met dezelfde
hash in `instance/quarantine`, niet meer in de publieke staticmap. Het is niet
ontsleuteld, uitgevoerd of verwijderd.

## Geld, orders, coupons en e-mail

Alle financiële berekeningen gebruiken centen/Decimal. Kortingen en gedeeltelijke
refunds worden met grootste-restenverdeling over regels verdeeld; refunds kunnen
het betaalde bedrag niet overschrijden. Btw wordt op de toegewezen bedragen
berekend. Simulatieprijzen/btw zijn geen geverifieerde verkoop-/factuurgegevens.
Voorbeeldverzending wordt uitdrukkelijk fictief als nul getoond. Voor echte
productrecords moeten verzendkosten eerst worden bevestigd.

Orders beginnen met `SIM-`. Dubbele klikken gebruiken een idempotentiesleutel.
Couponreservering gebeurt onder een SQLite-schrijftransactie; annulering,
mislukking en timeout geven de reservering vrij. Een betaalde code wordt niet
automatisch heruitgegeven na een refund. Dit beleid moet in de campagnevoorwaarden
staan. Betalingen, fulfilment en refunds in deze omgeving zijn uitsluitend
simulaties. Er is geen operationele betaalprovideradapter of productiewebhook;
`/payments/webhook` weigert verwerking. Een live-vlag of aanwezige Woo-credentials
kan de blokkade niet opheffen. Provider-sandbox en productieacceptatie zijn apart
vereist.

Welkomstcodes vereisen een geverifieerd e-mailadres en een actieve campagne.
Codes worden onvoorspelbaar gegenereerd, alleen gehasht voor validatie bewaard,
persoonlijk en eenmalig ingewisseld. De volledige code staat alleen in het
bedoelde private mailbericht. Datums zijn UTC, eindtijd exclusief. De banner is
bij een uitgeschakelde/verlopen campagne afwezig. De reviewbeloning is gelijk bij
1 en 5 sterren. Simulatiereviews worden nooit als echte geverifieerde aankopen
gepubliceerd. Voor een echte reviewuitnodiging zijn nog een echte aankoopbron en
beoordeling van de communicatiegrondslag vereist.

De testpostbus verstuurt niets extern. `nv_mail.py` is een voorbereide adapter,
zonder automatische dispatcher. Alleen NIEUWE berichten kunnen na afzonderlijke
mailacceptatie `pending` worden; bestaande `test`-berichten worden nooit alsnog
verzonden. Vereist zijn productieomgeving, expliciete enable-vlag,
geverifieerd afzenderdomein, HTTPS-SITE_URL en SMTP-configuratie. Deze vlaggen zijn
niet aangezet. SPF/DKIM/DMARC, providercontracten en afleverbaarheid zijn niet op
een echte ontvanger getest. SMTP geeft geen exactly-once-garantie: na een onzekere
afleverstatus wordt niet blind opnieuw verstuurd; handmatige reconciliatie nodig.

## PWA, talen en visuele acceptatie

De iconen komen uit het door de eigenaar bevestigde headerbestand
`static/nuvemixa-logo-test.png`. De oorspronkelijke logo-/herobestanden zijn
behouden. De serviceworker gebruikt uitsluitend het netwerk en bewaart geen
pagina’s, prijzen, account of mandje offline. HTTPS is nodig buiten localhost.
Android-installatie en iOS “Zet op beginscherm” werken verschillend. Er is geen
fysieke iPhone/Android- of geïnstalleerde-PWAacceptatie uitgevoerd.

NL/EN worden op de server gerenderd; bestaande sleutels/URL-aliassen blijven
compatibel. Taalwisseling herlaadt de pagina met de gekozen taal. Telefoon-
landscape gebruikt een combinatie van coarse pointer, hover, hoogte en breedte.
Aanvullend houdt `nv-phone-layout.js` de bestaande mobiele CSS actief bij draaien:
telefoons worden herkend aan aanraakmogelijkheden en een korte schermzijde tot
600 CSS-pixels, onafhankelijk van de actuele vensterbreedte. Een tablet/laptop
met een groter fysiek CSS-scherm wordt daardoor niet als telefoon behandeld.
De oorspronkelijke mobiele regels worden voor brede telefoonvensters hergebruikt;
de originele CSS- en afbeeldingsbestanden van de hero zijn behouden.
Een desktopvenster met dezelfde afmetingen is geen bewijs van een echt
touchapparaat. Controleer fysieke telefoons, tekst-/browserzoom en toetsenbord-
hulpmiddelen vóór productieacceptatie. Geen volledige WCAG-conformiteitsclaim.

## Nog door de eigenaar/acceptant aan te leveren

- Definitieve verkoper, KvK-/btw-/contactgegevens en retouradres.
- Juridisch beoordeelde voorwaarden, privacy/retentie/marketing- en reviewgrondslagen.
- Werkelijke leveranciers, productspecificaties, foto-/merkrechten en veiligheidseisen.
- Definitieve prijzen, belasting-/bezorglanden, verzendkosten en retourprocessen.
- Productiehosting-/opslag-/back-upbeleid, domein en secrets.
- Provider-sandboxconfiguratie en afzonderlijke toestemming voor operationele koppelingen.
- Maildomein, SMTP-configuratie en aparte aflever-/DNS-acceptatie.
- Fysieke apparaten, toegankelijkheidsbeoordeling en productieperformancemeting.

De toepasselijke verplichtingen verschillen per verkoper/productrol en land.
Juridische controle vereist. Deze lokale technische ronde verleent geen
commerciële of juridische vrijgave.
