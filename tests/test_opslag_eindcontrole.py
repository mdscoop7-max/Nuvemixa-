"""Eindcontrole opslag: concepten, kandidaten, beoordelingen en statussen blijven bewaard.

SQLite-tests lopen altijd; de PostgreSQL-test draait alleen met een eigen wegwerpdatabase
(NUVEMIXA_TEST_PG_URL, zonder TLS) en raakt nooit Neon of het 2FA-schema.
"""
import contextlib
import os
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest

from test_system_check import administrator  # noqa: F401
import nv_concepts as nc
import nuvemixa_admin_store as store

ROOT = Path(__file__).resolve().parent.parent
FORM = {"titel": "Opslagproef speaker", "categorie": "gadgets", "inkoop": "12,50", "verzend": "3,00",
        "verkoop": "39,95", "leverancier": "Proef BV", "bron_url": "https://example.com/p"}


@pytest.fixture
def sqlite_file(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ADMIN_DB", tmp_path / "admin.sqlite3")
    monkeypatch.setattr(store, "database_path", lambda: tmp_path / "admin.sqlite3")
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_BACKEND", raising=False)
    return tmp_path / "admin.sqlite3"


def test_gegevens_blijven_na_nieuwe_verbinding_en_status_blijft(sqlite_file):
    cid = nc.create(nc.read_form(FORM))
    nc.set_status(cid, "geselecteerd")
    store.add_supplier("Kandidaat Proef", "", "https://example.com", "[Kandidaat · model B]")
    # "herstart": alles opnieuw openen, niets uit geheugen
    gevonden = nc.get_concept(cid)
    assert gevonden["status"] == "geselecteerd" and gevonden["inkoop"] == 1250
    with store.connect() as db:
        assert db.execute("SELECT status FROM suppliers WHERE name=?", ("Kandidaat Proef",)).fetchone()[0] == "onderzoek"


def test_ui_meldt_tijdelijke_opslag_zonder_postgres(administrator, sqlite_file):
    pagina = administrator.get("/dashboard?section=concepten").get_data(as_text=True)
    assert "Opslag: tijdelijk" in pagina and "Opslag: permanent" not in pagina


def test_ui_meldt_permanente_opslag_met_postgres(administrator, sqlite_file, monkeypatch):
    monkeypatch.setenv("NUVEMIXA_DASHBOARD_BACKEND", "postgres")
    monkeypatch.setattr(nc, "list_concepts", lambda: [])
    import nv_publicatie
    monkeypatch.setattr(nv_publicatie, "existing_products", lambda: ([], "test", None))
    assert nc.view()["permanent"] is True


PG = os.environ.get("NUVEMIXA_TEST_PG_URL", "").strip()


@pytest.mark.skipif(not PG, reason="NUVEMIXA_TEST_PG_URL (eigen wegwerp-PostgreSQL) niet gezet")
def test_postgres_bewaart_concept_status_en_kandidaat_over_aparte_processen():
    script = textwrap.dedent("""
        import contextlib, os, sys, psycopg
        import nv_dashboard_postgres as p
        @contextlib.contextmanager
        def plain():
            with psycopg.connect(os.environ["NUVEMIXA_DASHBOARD_DATABASE_URL"], prepare_threshold=None) as db:
                yield db
        p.connect = plain
        import nv_concepts as c, nuvemixa_admin_store as s
        if sys.argv[1] == "schrijf":
            cid = c.create(c.read_form({"titel": "PG proef speaker " + sys.argv[2], "categorie": "gadgets", "inkoop": "10", "verkoop": "30"}))
            c.set_status(cid, "geselecteerd")
            s.add_supplier("PG proef kandidaat " + sys.argv[2], "", "https://example.com", "[Kandidaat]")
        else:
            rows = [x for x in c.list_concepts() if x["titel"] == "PG proef speaker " + sys.argv[2]]
            assert rows and rows[0]["status"] == "geselecteerd", rows
            with s.connect() as db:
                assert db.execute("SELECT 1 FROM suppliers WHERE name=?", ("PG proef kandidaat " + sys.argv[2],)).fetchone()
    """)
    env = {**os.environ, "NUVEMIXA_DASHBOARD_BACKEND": "postgres", "NUVEMIXA_DASHBOARD_DATABASE_URL": PG, "PYTHONPATH": str(ROOT)}
    run = uuid.uuid4().hex[:8]
    for fase in ("schrijf", "lees"):
        r = subprocess.run([sys.executable, "-c", script, fase, run], env=env, capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 0, r.stderr[-800:]
