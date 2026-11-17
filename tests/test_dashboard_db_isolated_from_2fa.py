"""Een toekomstige permanente dashboarddatabase mag de 2FA-opslag nooit raken of beïnvloeden."""
import re
from pathlib import Path

import pytest

import nv_2fa_postgres

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_MODULES = ["nv_dashboard_postgres.py", "migrate_dashboard_postgres.py", "nv_product_dossier.py",
                     "nv_visits.py", "nv_webshop_visits.py"]


@pytest.mark.parametrize("name", DASHBOARD_MODULES)
def test_dashboardopslag_verwijst_niet_naar_2fa(name):
    tekst = (ROOT / name).read_text(encoding="utf-8")
    assert "nuvemixa_auth" not in tekst and "NUVEMIXA_2FA" not in tekst


@pytest.mark.parametrize("name", ["nv_dashboard_postgres.py", "migrate_dashboard_postgres.py"])
def test_dashboardopslag_bevat_geen_vernietigende_sql(name):
    tekst = (ROOT / name).read_text(encoding="utf-8")
    assert not re.search(r"drop\s+(table|schema|database)|truncate|delete\s+from", tekst, re.I)


def test_dashboardvariabelen_zetten_2fa_niet_aan_of_uit(monkeypatch):
    for k in ("NUVEMIXA_2FA_BACKEND", "NUVEMIXA_2FA_DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    assert nv_2fa_postgres.enabled() is False
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_DATABASE_URL", "postgresql://u:p@dashboard.invalid/db")
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND", "postgres")
    assert nv_2fa_postgres.enabled() is False
    monkeypatch.setenv("NUVEMIXA_2FA_BACKEND", "postgres")
    assert nv_2fa_postgres.enabled() is True
