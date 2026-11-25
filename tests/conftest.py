import pytest
import nv_public_products


@pytest.fixture(autouse=True)
def isolate_public_feed(monkeypatch):
    """Catalogue tests must not make live Render calls or depend on production data."""
    monkeypatch.setattr(nv_public_products, 'fetch_extra_products', lambda: [])
