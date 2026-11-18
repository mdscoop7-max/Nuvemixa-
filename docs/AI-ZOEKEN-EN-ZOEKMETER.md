# AI-zoekondersteuning en zoekmeter (NUVEMIXA-dashboard)

## Configuratie (Render → Environment)
| Variabele | Verplicht | Standaard | Betekenis |
|---|---|---|---|
| `OPENAI_API_KEY` | ja | – | Al ingesteld. Alleen backend; komt nooit in HTML/JS. |
| `NUVEMIXA_AI_MODEL` | nee | `gpt-4o-mini` | Model voor zoekwoorden en filteren (korte JSON-verzoeken). |
| `NUVEMIXA_SUPPLIER_SEARCH_MODEL` | nee | `gpt-4.1-mini` | Model voor AI-leverancierszoeken met web_search (alleen gecontroleerde domeinen). |
| `NUVEMIXA_AI_MONTHLY_USD` | nee | `3.00` | Eigen maandlimiet (geschatte kosten). OpenAI-projectbudget US$ 5 blijft de achtervang. |
| `NUVEMIXA_AI_DAILY_CALLS` | nee | `80` | Maximaal aantal AI-aanroepen per dag. |
| `NUVEMIXA_AI` | nee | aan | `off` schakelt alle AI uit; normaal zoeken blijft werken. |

`NUVEMIXA_RESEARCH_AI` is niet meer nodig.

## Wat AI doet
Centrale service `nv_openai.py`; zoeklogica `nv_ai_search.py` (gebruikt door Productonderzoek, niches,
trends, Leveranciers/dropshipping, Internationaal marktonderzoek en Viral Product Finder).
1. Zoekterm → NL/EN-zoekwoorden, categorie en uit te sluiten accessoirewoorden.
2. Opgehaalde resultaten → alleen markeren/verwijderen wat duidelijk een ander product of accessoire is.
AI voegt nooit producten, leveranciers, prijzen, verkoopcijfers of trendcijfers toe.

## Kostenbewaking
Caching (6 uur) per identieke vraag, max. 160–200 uitvoertokens, temperatuur 0, pauze na HTTP 429/5xx/time-out,
pauze van 15 minuten na een geweigerde sleutel. Tellers staan in het servergeheugen en beginnen na een herstart
opnieuw; het OpenAI-projectbudget blijft daarom de harde grens.

## Zoekmeter
`static/nv-search-meter.js` + `.css` op elk formulier met `data-research-search` (fasen via `data-search-phases`).
Geen percentage: een bewegende balk, echte verstreken tijd, melding na 15 s, stopknop na 45 s, herstel bij terugnavigeren.
