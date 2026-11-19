"""AI mag resultaten alleen zichtbaar uitsluiten, nooit ongemerkt verwijderen; schakelaar in Internationaal/Viral."""
import pytest
from werkzeug.datastructures import MultiDict

import nv_ai_search
import nv_market_search
import nv_openai
from test_ai_search import CATS, api  # noqa: F401  (fixture)


def argan_results(term, *args, **kwargs):
    titles = ["Argan Oil 100% Pure", "Argan Oil Refill (5 Litre)", "Argan Oil Professional Refill 5L",
              "Argan Oil Brow Gel", "Organic Argan Oil 50 ml", "Argan oil hair serum", "Moroccan Argan Oil"]
    return {"term": term, "error": None, "searched": term,
            "products": [{"title": t, "url": f"https://bron/{i}", "source": "Bron"} for i, t in enumerate(titles)],
            "alternatives": [],
            "suppliers": [{"name": "Naissance", "products": [{"title": titles[1], "url": "https://bron/1"}]},
                          {"name": "KYRO Beauty", "products": [{"title": titles[3], "url": "https://bron/3"}]}]}


def test_excluded_results_stay_visible_with_reason(api, monkeypatch):  # noqa: F811
    calls, answers = api
    monkeypatch.setattr(nv_ai_search, "discover", argan_results)
    answers += [{"category": "", "keywords_en": ["argan oil"], "exclude": ["gel"]}, {"reject": [3]}]
    result = nv_ai_search.ai_discover("arganolie", categories=CATS)
    titles = [p["title"] for p in result["products"]]
    assert "Argan Oil Brow Gel" not in titles and "Argan Oil Refill (5 Litre)" in titles
    excluded = result["ai"]["excluded"]
    assert [e["title"] for e in excluded] == ["Argan Oil Brow Gel"]
    assert excluded[0]["reason"] and excluded[0]["url"] == "https://bron/3"
    assert result["ai"]["excluded_suppliers"] == ["KYRO Beauty"]
    assert [c["name"] for c in result["suppliers"]] == ["Naissance"]


def test_refill_and_size_words_are_never_exclusion_words(api, monkeypatch):  # noqa: F811
    calls, answers = api
    monkeypatch.setattr(nv_ai_search, "discover", argan_results)
    answers += [{"category": "", "keywords_en": [], "exclude": ["refill", "litre", "bulk"]}, {"reject": []}]
    result = nv_ai_search.ai_discover("arganolie", categories=CATS)
    assert len(result["products"]) == 7 and result["ai"]["removed"] == 0


def test_too_many_rejections_keep_all_source_results(api, monkeypatch):  # noqa: F811
    calls, answers = api
    monkeypatch.setattr(nv_ai_search, "discover", argan_results)
    answers += [{"category": "", "keywords_en": [], "exclude": []}, {"reject": [0, 1, 2, 3, 4, 5]}]
    result = nv_ai_search.ai_discover("arganolie", categories=CATS)
    assert len(result["products"]) == 7 and len(result["suppliers"]) == 2
    assert "te onzeker" in result["ai"]["message"] and result["ai"]["removed"] == 0


def test_filter_prompt_keeps_refills_and_sizes():
    assert "refill" in nv_ai_search.FILTER_SYSTEM and "Always keep" in nv_ai_search.FILTER_SYSTEM


@pytest.mark.parametrize("args,expected", [
    (MultiDict([("mrun", "1"), ("mq", "x")]), True),
    (MultiDict([("mrun", "1"), ("mq", "x"), ("mai", "0"), ("mai", "1")]), True),
    (MultiDict([("mrun", "1"), ("mq", "x"), ("mai", "0")]), False),
])
def test_ai_switch_in_market_search(args, expected):
    assert nv_market_search.parse("internationaal", args, CATS)["ai"] is expected


def test_ai_off_uses_plain_search_and_never_calls_openai(monkeypatch):
    seen = {}

    def plain(term, **kwargs):
        seen["plain"] = term
        return {"error": None, "products": [], "suppliers": [], "news": [], "trends": [], "country_name": "Nederland"}

    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setattr(nv_market_search, "plain_discover", plain)
    monkeypatch.setattr(nv_market_search, "discover", lambda *a, **k: pytest.fail("AI-zoeken mag niet draaien"))
    monkeypatch.setattr(nv_openai.urllib.request, "urlopen", lambda *a, **k: pytest.fail("geen API-aanroep"))
    view = nv_market_search.search_view("internationaal", CATS,
                                        MultiDict([("mrun", "1"), ("mq", "bluetooth speaker"), ("mai", "0")]))
    assert seen["plain"] == "bluetooth speaker" and view["ai"]["state"] == "off"


def test_sources_start_while_ai_chooses_keywords_when_term_needs_no_translation(monkeypatch):
    import time
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    seen = []

    def slow_expand(term, categories):
        time.sleep(0.6)
        return {"category": "", "keywords_en": [], "keywords_nl": [], "exclude": []}

    def slow_discover(term, *args, **kwargs):
        seen.append(term)
        time.sleep(0.6)
        return {"term": term, "error": None, "products": [], "alternatives": [], "suppliers": []}

    monkeypatch.setattr(nv_ai_search, "expand", slow_expand)
    monkeypatch.setattr(nv_ai_search, "discover", slow_discover)
    started = time.monotonic()
    nv_ai_search.ai_discover("bluetooth speaker", categories=CATS, category="gadgets")
    assert time.monotonic() - started < 1.0 and seen == ["bluetooth speaker"]


def test_dutch_term_that_needs_translation_still_waits_for_ai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    seen = []
    monkeypatch.setattr(nv_ai_search, "expand", lambda term, categories: {
        "category": "", "keywords_en": ["portable speaker"], "keywords_nl": [], "exclude": []})
    monkeypatch.setattr(nv_ai_search, "reject_ids", lambda *a, **k: set())
    monkeypatch.setattr(nv_ai_search, "discover", lambda term, *a, **k: seen.append(term) or {
        "term": term, "error": None, "products": [], "alternatives": [], "suppliers": []})
    nv_ai_search.ai_discover("draagbare muziekbox", categories=CATS)
    assert seen == ["portable speaker"]
