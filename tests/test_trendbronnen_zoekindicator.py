import re
from pathlib import Path

import nv_trendbronnen as t
from test_system_check import administrator  # noqa: F401


def test_no_social_source_claims_live():
    for s in t.sources():
        if s["key"] in {"google-trends", "tiktok", "instagram", "youtube", "reddit", "google-shopping", "pinterest"}:
            assert s["status"] not in ("live", "cache")


def test_manual_links_only_and_valid_period():
    links = t.manual_links("smart plug", "DE", "30")
    assert links[0]["url"].startswith("https://trends.google.com/") and "geo=DE" in links[0]["url"] and "today+1-m" in links[0]["url"]
    assert all(l["url"].startswith("https://") for l in links)
    assert t.manual_links("", "NL", "30") == []


def test_view_has_no_invented_numbers():
    v = t.view({"a": "gadgets", "b": "home-living", "land": "FR", "periode": "7"})
    assert v["live_count"] == 1 and v["missing_count"] >= 6
    assert v["form"]["land"] == "FR" and "section=partners" in v["niches"][0]["next"]["partners"]


def test_trends_page_renders(administrator):
    html = administrator.get("/dashboard?section=trends&a=smart-home&b=shop").get_data(as_text=True)
    assert "geen live trendfeed" in html and "Niet berekend" in html and "Dierenproducten" in html
    assert "nv-zoekindicator.js" in html


def test_indicator_script_guards():
    js = Path("static/nv-zoekindicator.js").read_text()
    assert "aria-live" in js and "busy" in js and "pageshow" in js and "TIMEOUT_MS" in js
    assert not re.search(r"\d+\s*%", js)  # geen verzonnen percentage
    css = Path("static/nuvemixa-dashboard-eindcorrectie.css").read_text()
    assert "prefers-reduced-motion" in css
