import pytest

import nv_source_guard


@pytest.fixture(autouse=True)
def fresh_source_guard():
    nv_source_guard.reset()
    yield
    nv_source_guard.reset()


@pytest.fixture(autouse=True)
def fresh_openai_guard(monkeypatch):
    """Geen echte OpenAI-aanroepen of gedeelde tellers tussen tests."""
    import nv_openai
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    nv_openai.reset_for_tests()
    yield
    nv_openai.reset_for_tests()
