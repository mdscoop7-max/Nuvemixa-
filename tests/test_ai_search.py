"""Centrale OpenAI-koppeling en AI-ondersteunde zoekbalken, uitsluitend met nagebootste API-antwoorden."""
import io
import json
import urllib.error

import pytest

import nv_ai_search
import nv_openai

CATS = {"gadgets": "Gadgets", "pets": "Huisdieren", "home-living": "Home & Living"}


class Reply:
    def __init__(self, content, usage=None):
        self.body = json.dumps({"choices": [{"message": {"content": json.dumps(content)}}],
                                "usage": usage or {"prompt_tokens": 300, "completion_tokens": 60}}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _limit):
        return self.body


def fake_results(term, *args, **kwargs):
    return {"term": term, "error": None, "searched": term, "category": kwargs.get("category"),
            "products": [{"title": "Portable Bluetooth Speaker 10W", "url": "https://a/1"},
                         {"title": "Travel case for speaker", "url": "https://a/2"}],
            "alternatives": [],
            "suppliers": [{"name": "Echte BV", "products": [{"title": "Speaker strap", "url": "https://a/3"}]}]}


@pytest.fixture
def api(monkeypatch):
    calls = []
    answers = []

    def urlopen(request, timeout):
        body = json.loads(request.data)
        calls.append(body)
        assert request.full_url.startswith("https://api.openai.com/v1/")
        assert request.headers["Authorization"] == "Bearer fixture-key"
        result = answers.pop(0)
        if isinstance(result, Exception):
            raise result
        return Reply(result)

    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setattr(nv_openai.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(nv_ai_search, "discover", fake_results)
    return calls, answers


def test_without_key_normal_search_runs_and_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(nv_ai_search, "discover", fake_results)
    monkeypatch.setattr(nv_openai.urllib.request, "urlopen", lambda *a, **k: pytest.fail("geen API-aanroep"))
    result = nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert result["ai"]["state"] == "off" and len(result["products"]) == 2


def test_ai_translates_dutch_term_and_only_removes_results(api):
    calls, answers = api
    answers += [{"category": "gadgets", "keywords_en": ["bluetooth speaker"], "keywords_nl": ["luidspreker"],
                 "exclude": ["case", "strap"]},
                {"reject": [1]}]
    result = nv_ai_search.ai_discover("draagbare muziekbox", categories=CATS)
    assert result["searched"] == "bluetooth speaker" and result["term"] == "draagbare muziekbox"
    assert [p["title"] for p in result["products"]] == ["Portable Bluetooth Speaker 10W"]
    assert result["suppliers"] == []  # leverancier had alleen een accessoire
    assert result["ai"]["state"] == "active" and result["ai"]["removed"] == 2
    assert len(calls) == 2 and all(c["model"] == "gpt-4o-mini" and c["max_tokens"] <= 200 for c in calls)
    assert "Verzonnen" not in json.dumps(result)


def test_ai_never_adds_items_and_invalid_answers_are_ignored(api):
    calls, answers = api
    answers += [{"category": "bestaat-niet", "keywords_en": ["<script>", "x" * 80], "exclude": []},
                {"reject": [0, 1, 2]}]  # alles weggooien is te onzeker: niets verwijderen
    result = nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert len(result["products"]) == 2 and len(result["suppliers"]) == 1
    assert result["ai"]["keywords_en"] == [] and result["ai"]["category"] == ""


def test_http_429_falls_back_and_pauses_further_calls(api):
    calls, answers = api
    answers.append(urllib.error.HTTPError("u", 429, "limit", {}, io.BytesIO(b"")))
    first = nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert first["ai"]["state"] == "fallback" and "429" in first["ai"]["message"]
    assert len(first["products"]) == 2  # normaal zoeken werkt door
    second = nv_ai_search.ai_discover("yogamat", categories=CATS)
    assert second["ai"]["state"] == "fallback" and len(calls) == 1
    assert nv_openai.status()["state"] == "fallback"


def test_timeout_and_auth_errors_have_safe_messages(api):
    calls, answers = api
    answers.append(TimeoutError())
    result = nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert "reageerde niet" in result["ai"]["message"] and "fixture-key" not in json.dumps(result)
    nv_openai.reset_for_tests()
    answers.append(urllib.error.HTTPError("u", 401, "auth", {}, io.BytesIO(b"")))
    result = nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert "OPENAI_API_KEY" in result["ai"]["message"] and "fixture-key" not in json.dumps(result)


def test_budget_and_daily_limit_block_before_any_call(api, monkeypatch):
    calls, _ = api
    monkeypatch.setenv("NUVEMIXA_AI_MONTHLY_USD", "0")
    result = nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert result["ai"]["state"] == "fallback" and "budget" in result["ai"]["message"].lower() and calls == []
    monkeypatch.setenv("NUVEMIXA_AI_MONTHLY_USD", "3")
    monkeypatch.setenv("NUVEMIXA_AI_DAILY_CALLS", "0")
    result = nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert "Daglimiet" in result["ai"]["message"] and calls == []


def test_identical_searches_use_the_cache_and_cost_is_tracked(api):
    calls, answers = api
    answers += [{"category": "", "keywords_en": [], "exclude": []}, {"reject": []}]
    nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    nv_ai_search.ai_discover("bluetooth speaker", categories=CATS)
    assert len(calls) == 2
    spent = nv_openai.usage()["month_usd"]
    assert 0 < spent < 0.01


def test_ai_off_switch(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-key")
    monkeypatch.setenv("NUVEMIXA_AI", "off")
    assert not nv_openai.configured() and nv_openai.status()["state"] == "off"


def test_key_never_reaches_templates_or_static_files():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for path in [*root.glob("static/*.js"), *root.glob("templates/*.html")]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert "api.openai.com" not in text and "OPENAI_API_KEY\")" not in text, path
        assert not __import__("re").search(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}", text), path


def test_search_meter_is_on_every_research_search_bar():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    forms = 0
    for path in root.glob("templates/*.html"):
        text = path.read_text(encoding="utf-8")
        for chunk in text.split("data-research-search")[1:]:
            forms += 1
            assert "data-search-phases" in chunk.split(">", 1)[0], path
    assert forms >= 12
    script = (root / "static/nv-search-meter.js").read_text(encoding="utf-8")
    assert "Bezig met zoeken..." in script and "pageshow" in script and "%" not in script.split("*/", 1)[1]
