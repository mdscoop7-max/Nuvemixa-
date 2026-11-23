# Mobiel staand en liggend — aanvullende lokale controle

De eerdere correctie dekte slechts een deel van de telefoonweergave. Veel bestaande mobiele stijlen stopten bij 760 px, terwijl een telefoon horizontaal breder is. Daardoor kon een mix van mobiele en desktopstijlen verschijnen.

`static/nv-phone-layout.js` herkent nu een telefoon via schermformaat en aanraakmogelijkheden. Bij draaien worden de bestaande mobiele stijlen hergebruikt in plaats van een tweede mobiel ontwerp te maken. Dit werkt onafhankelijk van browser-/standalone-modus. Het menu wordt niet meer alleen wegens het passeren van een desktopbreedte gesloten. De mobiele hero-afbeeldingen zijn behouden; echte desktop houdt zijn 400 px hero.

Controles:

- Zeven geautomatiseerde logische apparaatgevallen geslaagd, inclusief telefoon beide richtingen, terugdraaien, tablet en desktop/touchlaptop.
- 50 lokale browsercontroles met gesimuleerde scherm-/touchwaarden: schermprofielen 390×844 en 430×932, staand en liggend, plus 1024×430 als brede telefoontest. Home, vijf categorieën, shop, aanbiedingen, account en winkelwagen gecontroleerd. Mobiele dock zichtbaar, mobiele hero zichtbaar, desktopcopy verborgen en geen horizontale overloop.
- Menu openen → draaien → open gebleven; Escape sluit het menu.
- Gevulde winkelwagen en checkout bij 844×390: mobiele navigatie aanwezig, checkout in één kolom, adresformulier aanwezig en geen horizontale overloop. Uitsluitend fictieve lokale gegevens; geen bestelling voorbereid of betaald in deze controle.
- Gewone desktop 1366×900: geen telefoonclassificatie, dock verborgen, hero 400 px.

De manifestinstellingen blijven `display: standalone` en `orientation: any`. De normale browser mag zijn eigen browserbalk tonen; een geïnstalleerde PWA gebruikt standalone voor zover het platform dat ondersteunt.

**Beperking:** een afzonderlijke headless Chromium-aanraaktest kon door de lokale uitvoerbeperking niet starten (`spawn EPERM`). De browsercontrole hierboven gebruikt daarom uitsluitend de geïsoleerde launcherdiagnose `?local_phone=390x844`, die scherm-/touch-APIwaarden simuleert. Deze diagnose zit niet in productie-requesthandling. Er is geen fysieke iPhone/Safari-, Android- of geïnstalleerde-PWA-acceptatie uitgevoerd. De fysieke eindcontrole blijft nodig. Niets is live gepubliceerd.
