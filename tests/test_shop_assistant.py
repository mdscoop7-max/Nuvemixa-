"""Webshop-assistent: juiste onderwerp-herkenning, begroeting, budget/cadeau en AI met kostenbewaking."""
import trendmix_assistant as ta

CATS = {"gadgets": {"name": "Gadgets"}, "lifestyle-sport": {"name": "Lifestyle & Sport"}}
CATALOG = {"gadgets": [{"name": "Noise-cancelling koptelefoon", "slug": "nc", "price": 49.95},
                       {"name": "Smartwatch", "slug": "sw", "price": 39.95},
                       {"name": "Bluetooth-tracker", "slug": "bt", "price": 14.95}],
           "lifestyle-sport": [{"name": "Fitness tracker", "slug": "ft", "price": 24.95},
                               {"name": "Yogamat", "slug": "ym", "price": 19.95, "hidden": True}]}


def ask(q):
    found = ta.matches(q, CATALOG, CATS, "/")
    return ta.general_answer(q, "nl", found, CATS, False, ta.catalog_items(CATALOG, CATS))[0]


def test_koptelefoon_is_not_a_contact_question():
    assert "contactpagina" not in ask("Welke koptelefoon raden jullie aan om te sporten?")
    assert "koptelefoon" in ask("Welke koptelefoon raden jullie aan om te sporten?").lower()


def test_tracker_is_not_order_tracking():
    answer = ask("Wat is het verschil tussen de smartwatch en de fitness tracker?")
    assert "bestelling" not in answer and "Smartwatch" in answer


def test_budget_and_gift_questions_get_products_under_the_limit():
    answer = ask("Hebben jullie cadeau-ideeën onder 30 euro?")
    assert "Fitness tracker" in answer and "Bluetooth-tracker" in answer and "Smartwatch" not in answer
    assert "Yogamat" not in answer  # verborgen (concept) producten nooit tonen


def test_greeting_gets_a_friendly_answer_without_test_wording():
    answer = ask("Hallo, wie zijn jullie?")
    assert answer.startswith("Hallo") and "test" not in answer.lower()


def test_ai_uses_guarded_post_and_full_overview(monkeypatch):
    import nv_openai
    sent = {}
    monkeypatch.setattr(nv_openai, "configured", lambda: True)
    monkeypatch.setattr(nv_openai, "post", lambda path, data, **kw: sent.update(path=path, data=data, kw=kw)
                        or {"choices": [{"message": {"content": "Probeer de Fitness tracker."}}]})
    out = ta.ai_answer("cadeau onder 30?", "nl", [], ta.catalog_items(CATALOG, CATS))
    assert out == "Probeer de Fitness tracker." and sent["path"] == "chat/completions"
    assert "Fitness tracker" in sent["data"]["messages"][0]["content"] and "Yogamat" not in sent["data"]["messages"][0]["content"]


def test_ai_unavailable_falls_back(monkeypatch):
    import nv_openai
    monkeypatch.setattr(nv_openai, "configured", lambda: True)
    def boom(*a, **k):
        raise nv_openai.AIUnavailable("limit", "limiet")
    monkeypatch.setattr(nv_openai, "post", boom)
    assert ta.ai_answer("hoi", "nl", [], []) is None


def test_ai_answer_never_shows_invented_domains_or_markdown():
    out = ta.clean_answer("1. **Oordopjes** - €24.95 [Bekijk hier](https://nuvemixa.nl/gadgets/oordopjes) of https://example.com")
    assert "nuvemixa.nl" not in out and "example.com" not in out and "**" not in out
    assert "/gadgets/oordopjes" in out
