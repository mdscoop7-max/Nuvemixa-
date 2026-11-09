"""Supplier-to-shop price estimates; explicit inputs, Decimal arithmetic, no assumed VAT."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

def number(value, label, maximum="1000000"):
    try:
        val=Decimal(str(value).replace(",","."))
    except (TypeError,ValueError,InvalidOperation):
        raise ValueError(label+" is ongeldig")
    if not val.is_finite() or val<0 or val>Decimal(maximum):
        raise ValueError(label+" buiten toegestane grenzen")
    return val

def quote(purchase, shipping, packaging, fees_fixed, fees_percent, vat_percent, margin_percent):
    buy=number(purchase,"Inkoop")
    ship=number(shipping,"Verzending")
    pack=number(packaging,"Verpakking")
    fixed=number(fees_fixed,"Vaste kosten")
    fee=number(fees_percent,"Betaalkostenpercentage","90")
    vat=number(vat_percent,"BTW-percentage","50")
    margin=number(margin_percent,"Gewenste brutomarge","90")
    cost=buy+ship+pack+fixed
    # Margin is a share of pre-VAT selling price, after percentage-based payment costs.
    denominator=Decimal("1")-(margin/100)-(fee/100)*(Decimal("1")+vat/100)
    if denominator<=0:
        raise ValueError("Marge en kosten vormen geen haalbare prijs")
    excl=(cost/denominator).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    incl=(excl*(Decimal("1")+vat/100)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    vat_amount=incl-excl
    processing=(incl*fee/100+fixed).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
    profit=excl-buy-ship-pack-processing
    return {"purchase":buy,"shipping":ship,"packaging":pack,"fixed":fixed,
            "vat_percent":vat,"fee_percent":fee,"margin_percent":margin,
            "price_ex_vat":excl,"price_inc_vat":incl,"vat_amount":vat_amount,
            "estimated_profit":profit,"processing_cost":processing,
            "actual_margin_percent":(profit/excl*100).quantize(Decimal("0.01")) if excl else Decimal(0)}
