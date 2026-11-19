import pytest

import nv_source_guard


@pytest.fixture(autouse=True)
def fresh_source_guard():
    nv_source_guard.reset()
    yield
    nv_source_guard.reset()


@pytest.fixture(autouse=True)
def fresh_openai_guard(monkeypatch, tmp_path):
    """Geen echte OpenAI-aanroepen of gedeelde tellers tussen tests; teller in een eigen SQLite-bestand."""
    import contextlib
    import sqlite3
    import nv_openai
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    @contextlib.contextmanager
    def store():
        db = sqlite3.connect(tmp_path / "ai_usage.sqlite3")
        try:
            yield db
            db.commit()
        finally:
            db.close()
    monkeypatch.setattr(nv_openai, "store_connect", store)
    nv_openai.reset_for_tests()
    yield
    nv_openai.reset_for_tests()


@pytest.fixture(autouse=True)
def fresh_stats_cache():
    import nv_stats_cache
    nv_stats_cache.clear()
    yield
    nv_stats_cache.clear()
