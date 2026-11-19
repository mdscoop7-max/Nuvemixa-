"""Snelheid hoofdscherm: statistieken max. 60 s gecachet, alleen op het hoofdscherm, privé en zonder foutcache."""
from test_system_check import administrator  # noqa: F401

import app as dashboard
import nv_stats_cache


def counters(monkeypatch, customers=(3, [], None), visits=None):
    calls = {"customers": 0, "visits": 0}

    def read_customers(_path):
        calls["customers"] += 1
        return customers

    def read_visits():
        calls["visits"] += 1
        return visits or {"error": False, "has_data": False}

    monkeypatch.setattr(dashboard, "read_customer_activity", read_customers)
    monkeypatch.setattr(dashboard, "webshop_visit_summary", read_visits)
    return calls


def test_home_statistics_are_read_once_per_minute(administrator, monkeypatch):
    calls = counters(monkeypatch)
    for _ in range(3):
        assert administrator.get("/dashboard?section=dashboard").status_code == 200
    assert calls == {"customers": 1, "visits": 1}


def test_cache_expires_after_ttl(administrator, monkeypatch):
    calls = counters(monkeypatch)
    administrator.get("/dashboard?section=dashboard")
    for key in list(nv_stats_cache._entries):
        when, value = nv_stats_cache._entries[key]
        nv_stats_cache._entries[key] = (when - 61, value)
    administrator.get("/dashboard?section=dashboard")
    assert calls == {"customers": 2, "visits": 2}


def test_customers_statistics_and_monitoring_always_read_live(administrator, monkeypatch):
    calls = counters(monkeypatch)
    administrator.get("/dashboard?section=dashboard")
    for section in ("klanten", "klanten", "statistieken", "monitoring"):
        assert administrator.get(f"/dashboard?section={section}").status_code == 200
    assert calls["customers"] == 3 and calls["visits"] == 3


def test_failed_reads_are_never_cached(administrator, monkeypatch):
    calls = counters(monkeypatch, customers=(None, [], "niet beschikbaar"), visits={"error": True})
    administrator.get("/dashboard?section=dashboard")
    administrator.get("/dashboard?section=dashboard")
    assert calls == {"customers": 2, "visits": 2}


def test_cache_is_not_reachable_without_owner_login(monkeypatch):
    calls = counters(monkeypatch)
    client = dashboard.app.test_client()
    assert client.get("/dashboard?section=dashboard").status_code in (302, 303, 403)
    assert calls == {"customers": 0, "visits": 0} and nv_stats_cache._entries == {}


def test_margin_advice_in_browser_matches_server():
    """Automatisch verkoopadvies bij alleen een inkoopprijs: browser rekent exact als de server."""
    import json
    import pathlib
    import shutil
    import subprocess
    import pytest
    from nv_product_margin import automatic_margin
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js niet beschikbaar")
    script = pathlib.Path(__file__).resolve().parents[1] / "static/nv-margin-core.js"
    code = ("global.window={};global.document={querySelectorAll:()=>[]};require(%r);const f=window.NVMarginAdvice;"
            "const o={};for(const p of ['10','12.5','0.99','39.95']){for(const v of [21,9]){const n=f(Math.round(Number(p)*100),v);"
            "o[p+'|'+v]=[n.selling,n.revenue,n.vat,n.fee,n.total,n.profit]}}console.log(JSON.stringify(o))") % str(script)
    result = json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)
    for key, values in result.items():
        price, vat = key.split("|")
        server = automatic_margin(price, vat)
        assert values == [round(float(server[k]) * 100) for k in
                          ("selling", "revenue_ex_vat", "vat", "platform", "total_cost", "profit")], key


def test_margin_bar_percentages_give_the_chosen_margin():
    import json
    import pathlib
    import shutil
    import subprocess
    import pytest
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js niet beschikbaar")
    script = pathlib.Path(__file__).resolve().parents[1] / "static/nv-margin-core.js"
    code = ("global.window={};global.document={querySelectorAll:()=>[]};require(%r);const f=window.NVMarginAdvice;"
            "const o={};for(const t of [15,20,25,30,35,40]){o[t]=f(1250,21,t).margin}console.log(JSON.stringify(o))") % str(script)
    margins = json.loads(subprocess.run([node, "-e", code], capture_output=True, text=True, check=True).stdout)
    for pct, margin in margins.items():
        assert abs(margin - int(pct)) < 0.2, (pct, margin)
    page = (pathlib.Path(__file__).resolve().parents[1] / "templates/_margin_calculator.html").read_text(encoding="utf-8")
    form = page.split("macro margin_form", 1)[1].split("</form>", 1)[0]
    assert form.index('name="margin_product"') < form.index('name="purchase_cost"') < form.index('name="target_margin"')
    assert form.index('name="target_margin"') < form.index("selling_price")
