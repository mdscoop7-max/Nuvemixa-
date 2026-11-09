"""Read-only integration overview; never invent metrics."""
import os

def status_rows():
    entries=[
        ("RankFix AI","TRENDMIX_RANKFIX_REPORT_URL","SEO, GEO en technische controles"),
        ("Google Search Console","TRENDMIX_SEARCH_CONSOLE_PROPERTY","Zoekverkeer en indexering"),
        ("Google Ads","TRENDMIX_GOOGLE_ADS_CUSTOMER_ID","Campagneprestaties en kosten"),
        ("Leveranciers","TRENDMIX_SUPPLIER_FEED_CONFIGURED","Producten en voorraad"),
        ("Klantenservice","RESEND_WEBHOOK_SECRET","E-mailvragen"),
    ]
    return [{"name":name,"purpose":purpose,"configured":bool(os.getenv(key)),
             "last_check":"Nog niet uitgevoerd","metrics":"Geen geverifieerde metingen"} for name,key,purpose in entries]
