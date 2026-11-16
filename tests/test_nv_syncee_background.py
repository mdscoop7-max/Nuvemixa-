"""Syncee als gedeelde achtergrondtaak, magazijninformatie en aanvullende weergave."""
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import jinja2
import pytest

import nv_market_search as market
import nv_product_discovery as npd
from test_nv_product_discovery import CATEGORIES, SYNCEE_PRODUCT, Response, syncee_card, syncee_details

TERM = "Magnetic Power Bank 10000mAh"


def slow_fetch(delay, warehouse="Australia"):
    calls = []

    def fetch(url, **options):
        if "syncee.com" in url:
            calls.append(url)
            time.sleep(delay)
            if url == SYNCEE_PRODUCT:
                return Response(syncee_details(["NL"]).replace(b"Australia", warehouse.encode()))
            return Response(syncee_card())
        return Response(b"")
    return fetch, calls


def run(fetch):
    return npd.discover(TERM, categories=CATEGORIES, mode="dropship", category="gadgets", country="NL",
                        platforms=["Productcatalogi"], fetch=fetch)


def test_slow_syncee_does_not_block_page_and_completes_in_background(monkeypatch):
    monkeypatch.setattr(npd, "SOURCE_WINDOW", 0.4)
    fetch, calls = slow_fetch(0.5)
    started = time.monotonic()
    first = run(fetch)
    assert time.monotonic() - started < 1.5
    assert first["pending_sources"] == ["Syncee"]
    assert "NNE Living" not in [c["name"] for c in first["suppliers"]]
    assert "Syncee" not in first["unavailable_sources"]
    for _ in range(40):  # de achtergrondtaak rondt af
        second = run(fetch)
        if not second["pending_sources"]:
            break
        time.sleep(0.2)
    assert second["pending_sources"] == []
    assert "NNE Living" in [c["name"] for c in second["suppliers"]]
    assert len([c for c in calls if c == SYNCEE_PRODUCT]) == 1  # één gedeelde taak, geen dubbele verzoeken


def test_all_modules_share_one_syncee_job():
    fetch, calls = slow_fetch(0.2)
    results = []
    args = {"mq": TERM, "mcat": "gadgets", "mrun": "1"}
    threads = [threading.Thread(target=lambda k=k: results.append(market.search_view(k, CATEGORIES, args, fetch=fetch)))
               for k in ("viral", "internationaal")]
    threads.append(threading.Thread(target=lambda: results.append(run(fetch))))
    [t.start() for t in threads]; [t.join() for t in threads]
    assert len([c for c in calls if "/collections/" in c]) == 1
    assert len([c for c in calls if c == SYNCEE_PRODUCT]) == 1
    assert len(results) == 3


def test_syncee_failure_is_reported_not_pending():
    def fetch(url, **options):
        raise OSError("offline")
    result = run(fetch)
    assert result["pending_sources"] == [] and "Syncee" in result["unavailable_sources"]


def test_warehouse_outside_eu_is_shown_with_attention_points():
    fetch, _ = slow_fetch(0, "United Kingdom")
    result = run(fetch)
    company = next(c for c in result["suppliers"] if c["name"] == "NNE Living")
    assert company["warehouse_label"] == "United Kingdom" and company["warehouse_region"] == "international"
    assert "buiten de EU" in company["logistics_notes"][0] and "niet bevestigd" in company["logistics_notes"][0]
    assert company["lead_time_note"] and "werkdagen" in company["lead_time_note"]


def test_warehouse_inside_eu_and_unknown():
    company = {"products": {"a": {"warehouse": "Hungary"}}}
    assert npd.logistics(company)["warehouse_region"] == "eu"
    unknown = npd.logistics({"products": {"a": {"warehouse": npd.UNKNOWN}}})
    assert unknown["warehouse_label"] is None and unknown["warehouse_region"] == "unknown"
    assert "onbekend" in unknown["logistics_notes"][0] and unknown["lead_time_note"] is None
    mixed = npd.logistics({"products": {"a": {"warehouse": "Hungary"}, "b": {"warehouse": "China"}}})
    assert mixed["warehouse_region"] == "international" and len(mixed["logistics_notes"]) == 2


def environment():
    return jinja2.Environment(loader=jinja2.FileSystemLoader(str(Path(__file__).parent.parent / "templates")))


def test_macros_render_confirmed_and_unknown_fields():
    template = environment().from_string(
        "{% from '_supplier_logistics.html' import logistics, pending_notice %}"
        "{{ logistics(a) }}|{{ logistics(b) }}|{{ pending_notice(p) }}|{{ pending_notice([]) }}")
    html = template.render(
        a={"origin": "HU", "origin_name": "Hongarije", "warehouse_label": "Hungary", "lead_time_note": "4–7 werkdagen (geschat door aanbieder)", "logistics_notes": ["x"]},
        b={"origin": None, "origin_name": "Niet bevestigd", "warehouse_label": None, "logistics_notes": ["onbekend"]},
        p=["Syncee"])
    assert "Hongarije (bevestigd)" in html and "Hungary (volgens productvermelding)" in html
    assert "Vestigingsland</strong> Niet bevestigd" in html and "Magazijn / verzendland</strong> Niet bevestigd" in html
    assert "Syncee haalt nog aanvullende resultaten op" in html and html.count("location.reload") == 1
