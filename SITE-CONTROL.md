# NUVEMIXA — site control

## Deployment
- [x] Flask app runs on Render
- [x] Gunicorn is included in requirements.txt
- [x] Render URL is the canonical site: https://trendmix.onrender.com
- [ ] After each deploy, check Render logs for HTTP 500/404 errors

## Navigation & pages
- [x] Home
- [x] Five product collections
- [x] Product detail pages
- [x] Winkelwagen
- [x] Afrekenen
- [x] Over NUVEMIXA
- [x] Bestellen & levering
- [x] Privacy
- [x] Cookies & voorkeuren
- [x] FAQ
- [x] Contact

## Ecommerce consistency
- [x] Affiliate/dropshipping wording removed from the visible ecommerce footer/catalog metadata
- [x] No fake review section in the footer/homepage
- [x] Catalog statistics removed from the hero
- [x] Contact button uses the same visual treatment as the contact control
- [x] Contact message textarea uses readable dark text on a light field
- [x] Information pages have server-rendered fallback content

## Languages
- [x] Dutch
- [x] English
- [x] French
- [x] German
- [x] Italian
- [x] Spanish
- [x] FAQ and information pages use ecommerce translations
- [x] Contact labels use the selected language

## Product images
- [x] Product catalog image URLs are loaded from products.json
- [ ] Replace catalog image URLs when the final NUVEMIXA product photos are supplied/committed

## Final manual QA
1. Open the Render homepage and hard-refresh with Ctrl+F5.
2. Change language to each of the five non-Dutch languages.
3. Open FAQ and every information page in at least English and one other language.
4. Open Contact and type into the message field.
5. Submit a test contact message and confirm the success state.
6. Add a product to the cart and test quantity/remove/checkout navigation.
7. Check mobile layout at approximately 390px width.
8. Confirm Render logs contain no new 404 requests for app.js?v=... or languages.js?v=...