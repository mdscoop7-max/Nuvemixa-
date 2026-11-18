"""Volledige workflow: zoeken -> beoordelen -> kandidaat/concept -> selecteren -> publicatievoorbereiding.
Alle leveranciersantwoorden zijn nagebootste TESTDATA; WooCommerce wordt alleen met mocks aangeroepen. Niets wordt gepubliceerd."""
import re

import pytest
import requests
from test_system_check import administrator, CSRF_TOKEN  # noqa: F401
from test_nv_product_discovery import Response, SYNCEE_PRODUCT, syncee_card, syncee_details
from zoek_fixture import maak_fetch

import app as dashboard
import nv_concepts as nc
import nv_publicatie as pub
import nv_woo_writer as writer

POST = lambda c, url, **d: c.post(url, data={"_csrf_token": CSRF_TOKEN, **d})
FORM = {"titel": "Decathlon Yogamat 8 mm antislip", "categorie": "lifestyle-sport", "leverancier": "Manduka",
        "bron_url": "https://example.invalid/yogamat", "inkoop": "9,50", "verzend": "2,95", "verkoop": "29,95",
        "beschrijving": "Antislip yogamat van 8 mm voor thuis en in de studio. Eigen tekst van de eigenaar.",
        "afbeeldingen": "https://images.example.invalid/yogamat-1.jpg"}


@pytest.fixture
def storage_tmp(tmp_path, monkeypatch):
    import nuvemixa_admin_store as store
    monkeypatch.setattr(store, "ADMIN_DB", tmp_path / "admin.sqlite3")
    monkeypatch.setattr(store, "database_path", lambda: tmp_path / "admin.sqlite3")
    return tmp_path


def maak_concept(client, **extra):
    r = POST(client, "/dashboard/concepten/nieuw", **{**FORM, **extra})
    assert r.status_code == 303
    return nc.list_concepts()[0]


def test_onderzoeksresultaat_naar_concept_neemt_alleen_bekende_gegevens_over(administrator, storage_tmp, monkeypatch):
    monkeypatch.setattr(requests, "get", maak_fetch())
    pagina = administrator.get("/dashboard?section=onderzoek&research_run=1&research_term=Decathlon+yogamat+8+mm"
                               "&research_category=lifestyle-sport&research_mode=product&research_country=NL"
                               "&research_platform=Productcatalogi").get_data(as_text=True)
    assert "Bewaar als conceptproduct" in pagina
    velden = dict(re.findall(r'<input type="hidden" name="(titel|bron_url|categorie|leverancier)" value="([^"]*)"', pagina))
    assert velden["titel"] and velden["categorie"] == "lifestyle-sport"
    r = POST(administrator, "/dashboard/concepten/nieuw", **velden)
    assert r.status_code == 303
    c = nc.list_concepts()[0]
    assert c["inkoop"] is None and c["verkoop"] is None and c["beschrijving"] == "" and c["afbeeldingen"] == []
    assert c["status"] == "nieuw" and c["sku"].startswith("NV-")


def test_leveranciersresultaat_wordt_ongepubliceerd_huisdierenconcept(administrator, storage_tmp, monkeypatch):
    title = "Automatic Cat Feeder"

    def fetch(url, **kwargs):
        if url == SYNCEE_PRODUCT:
            return Response(syncee_details(["NL"], title))
        assert url.startswith("https://syncee.com/collections/")
        return Response(syncee_card(title))

    monkeypatch.setattr(requests, "get", fetch)
    response = administrator.get("/dashboard", query_string={
        "section": "onderzoek", "research_run": 1, "research_term": "Automatische kattenvoerbak",
        "research_mode": "dropship", "research_platform": "Productcatalogi", "research_supplier_filter": "all",
    })
    assert response.status_code == 200
    html = response.get_data(as_text=True).split('id="nv-research-suppliers"', 1)[1]
    form = re.search(r'<form [^>]*class="nv-concept-save">(.*?)</form>', html, re.S)[1]
    fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form))
    saved = administrator.post("/dashboard/concepten/nieuw", data=fields)
    assert saved.status_code == 303
    concept, = nc.list_concepts()
    assert concept["status"] == "nieuw"
    assert (concept["titel"], concept["categorie"], concept["bron_url"]) == (title, "Huisdieren", SYNCEE_PRODUCT)
    assert concept["inkoop"] is None and concept["verkoop"] is None
    assert title in administrator.get("/dashboard?section=concepten&concept_q=kattenvoerbak").get_data(as_text=True)
    assert title not in administrator.get("/dashboard?section=concepten&concept_q=yogamat").get_data(as_text=True)


def test_concept_zonder_prijzen_blokkeert_publicatievoorbereiding(administrator, storage_tmp):
    POST(administrator, "/dashboard/concepten/nieuw", titel="Alleen een titel", categorie="gadgets")
    c = nc.list_concepts()[0]
    stappen = {r["stap"]: r["status"] for r in pub.check(nc.to_candidate(c), [])}
    assert stappen["Inkoopprijs"] == "fout" and stappen["Verkoopprijs"] == "fout" and stappen["Afbeeldingen"] == "fout"


def test_volledige_workflow_tot_en_met_geweigerde_verzending(administrator, storage_tmp, monkeypatch):
    c = maak_concept(administrator)
    assert "Opslag: tijdelijk" in administrator.get("/dashboard?section=concepten").get_data(as_text=True)
    # nog niet geselecteerd: niet beschikbaar in publicatie
    assert administrator.get(f"/dashboard?section=publicatie&kandidaat={c['sku']}").get_data(as_text=True).count(c["sku"]) == 0
    assert POST(administrator, "/admin/nv/publicatie/goedkeuren", sku=c["sku"]).status_code == 404
    # beoordelen en selecteren
    checks = {f"check_{k}": "1" for k in nc.CHECKS}
    POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="opslaan", **{**FORM, **checks})
    POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="selecteren", **FORM)
    c = nc.get_concept(c["id"])
    assert c["status"] == "geselecteerd" and len(c["checks"]) == len(nc.CHECKS)
    page = administrator.get(f"/dashboard?section=publicatie&kandidaat={c['sku']}").get_data(as_text=True)
    assert "JOUW CONCEPT" in page and FORM["titel"] in page and "TESTDATA</span> Het product" not in page
    # goedkeuren, dan verzenden: geweigerd want geen schrijfkoppeling
    assert POST(administrator, "/admin/nv/publicatie/goedkeuren", sku=c["sku"]).status_code == 303
    assert "Goedgekeurd door jou" in administrator.get(f"/dashboard?section=publicatie&kandidaat={c['sku']}").get_data(as_text=True)
    POST(administrator, "/admin/nv/publicatie/publiceren", sku=c["sku"], bevestig="1")
    assert "niet verzonden" in administrator.get(f"/dashboard?section=publicatie&kandidaat={c['sku']}").get_data(as_text=True).lower()


def test_verzenden_vereist_alle_controles_en_bevestiging(administrator, storage_tmp, monkeypatch):
    c = maak_concept(administrator)
    POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="selecteren", **FORM)
    POST(administrator, "/admin/nv/publicatie/goedkeuren", sku=c["sku"])
    verzonden = []
    monkeypatch.setattr(writer, "build_sender", lambda: (lambda payload: verzonden.append(payload) or {"id": 1}))
    monkeypatch.setenv(pub.WRITE_SWITCH, "on")
    POST(administrator, "/admin/nv/publicatie/publiceren", sku=c["sku"], bevestig="1")  # controles niet afgevinkt
    assert verzonden == []
    checks = {f"check_{k}": "1" for k in nc.CHECKS}
    POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="opslaan", **{**FORM, **checks})
    POST(administrator, "/admin/nv/publicatie/goedkeuren", sku=c["sku"])
    POST(administrator, "/admin/nv/publicatie/publiceren", sku=c["sku"])  # zonder bevestiging
    assert verzonden == []
    POST(administrator, "/admin/nv/publicatie/publiceren", sku=c["sku"], bevestig="1")
    assert len(verzonden) == 1 and verzonden[0]["status"] == "draft" and verzonden[0]["sku"] == c["sku"]


def test_testproducten_worden_nooit_verzonden(administrator, monkeypatch):
    verzonden = []
    monkeypatch.setattr(writer, "build_sender", lambda: (lambda payload: verzonden.append(payload)))
    monkeypatch.setenv(pub.WRITE_SWITCH, "on")
    POST(administrator, "/admin/nv/publicatie/goedkeuren", sku="TEST-P1")
    POST(administrator, "/admin/nv/publicatie/publiceren", sku="TEST-P1", bevestig="1")
    assert verzonden == []


def test_bewerken_zet_geselecteerd_concept_niet_terug_en_afwijzen_bewaart(administrator, storage_tmp):
    c = maak_concept(administrator)
    POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="selecteren", **FORM)
    POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="opslaan", **{**FORM, "notities": "x"})
    assert nc.get_concept(c["id"])["status"] == "geselecteerd"
    POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="afwijzen", **FORM)
    assert nc.get_concept(c["id"])["status"] == "afgewezen" and nc.get_concept(c["id"])["titel"] == FORM["titel"]


@pytest.mark.parametrize("veld,waarde", [("inkoop", "abc"), ("verkoop", "-5"), ("titel", "ab"), ("bron_url", "javascript:alert(1)"),
                                          ("afbeeldingen", "http://x.invalid/a.jpg"), ("afbeeldingen", "https://x.invalid/a.exe"),
                                          ("beschrijving", "x" * 501)])
def test_ongeldige_invoer_wordt_geweigerd_en_niet_opgeslagen(administrator, storage_tmp, veld, waarde):
    r = POST(administrator, "/dashboard/concepten/nieuw", **{**FORM, veld: waarde})
    assert r.status_code == 303 and nc.list_concepts() == []


def test_concepten_zijn_alleen_voor_de_eigenaar(administrator, storage_tmp, monkeypatch):
    c = maak_concept(administrator)
    anoniem = dashboard.app.test_client()
    for url in ("/dashboard?section=concepten",):
        assert anoniem.get(url).status_code in (302, 303, 403)
    assert anoniem.post("/dashboard/concepten/nieuw", data=FORM).status_code in (302, 303, 400, 403)
    monkeypatch.setattr(nc, "admin", lambda: False)
    assert POST(administrator, "/dashboard/concepten/nieuw", **FORM).status_code == 403
    assert POST(administrator, "/dashboard/concepten/bijwerken", concept_id=c["id"], actie="selecteren", **FORM).status_code == 403
    assert POST(administrator, "/dashboard/concepten/bijwerken", actie="selecteren").status_code == 403


def test_geen_verwijderfunctie_en_bestaande_notities_blijven_ongemoeid(administrator, storage_tmp):
    import inspect
    assert "DELETE" not in inspect.getsource(nc).upper().replace("# GEEN", "")
    import nuvemixa_admin_store as store
    store.add_research("Gadgets", "Gewone notitie", "bron", "geen concept")
    maak_concept(administrator)
    assert len(nc.list_concepts()) == 1 and len(store.list_research()) == 2


# --- WooCommerce-schrijfkoppeling: alleen mocks ---------------------------------------------------------------

class FakeHttp:
    def __init__(self, bestaand=None, status=201, body=None):
        self.calls, self.bestaand, self.status, self.body = [], bestaand or [], status, body

    def _resp(self, code, data):
        class R:
            status_code = code
            def json(self_inner): return data
        return R()

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw)); return self._resp(200, self.bestaand)

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self._resp(self.status, self.body if self.body is not None else {**kw["json"], "id": 77})


@pytest.fixture
def woo_env(monkeypatch):
    for k, v in {"NUVEMIXA_WOO_URL": "https://shop.example.invalid", "NUVEMIXA_WOO_HOST": "shop.example.invalid",
                 "NUVEMIXA_WOO_WRITE_KEY": "ck_fixture", "NUVEMIXA_WOO_WRITE_SECRET": "cs_fixture"}.items():
        monkeypatch.setenv(k, v)


PAYLOAD = {"name": "Product", "type": "simple", "status": "draft", "sku": "NV-00001", "regular_price": "29.95"}


def test_schrijfkoppeling_staat_standaard_uit(monkeypatch):
    for k in writer.WRITE_VARIABLES:
        monkeypatch.delenv(k, raising=False)
    assert writer.build_sender() is None and not writer.configured()
    assert set(writer.missing_configuration()) == set(writer.WRITE_VARIABLES)


def test_schrijfkoppeling_maakt_alleen_een_concept_aan(woo_env):
    http = FakeHttp()
    result = writer.build_sender(http)(PAYLOAD)
    assert result["id"] == 77 and result["status"] == "draft"
    assert [c[0] for c in http.calls] == ["GET", "POST"]
    assert all(c[2]["allow_redirects"] is False and c[2]["timeout"] for c in http.calls)
    assert http.calls[1][1] == "https://shop.example.invalid/wp-json/wc/v3/products"


@pytest.mark.parametrize("status", ["publish", "pending", "private", ""])
def test_schrijfkoppeling_weigert_alles_behalve_draft(woo_env, status):
    http = FakeHttp()
    with pytest.raises(writer.WriteError):
        writer.build_sender(http)({**PAYLOAD, "status": status})
    assert http.calls == []


def test_schrijfkoppeling_maakt_geen_dubbele_sku_aan(woo_env):
    http = FakeHttp(bestaand=[{"id": 5}])
    with pytest.raises(writer.WriteError, match="bestaat al"):
        writer.build_sender(http)(PAYLOAD)
    assert [c[0] for c in http.calls] == ["GET"]


def test_schrijfkoppeling_meldt_fouten_zonder_geheimen(woo_env):
    for http in (FakeHttp(status=500, body={"message": "ck_fixture lekt"}), FakeHttp(body={"status": "publish"})):
        with pytest.raises(writer.WriteError) as fout:
            writer.build_sender(http)(PAYLOAD)
        assert "ck_fixture" not in str(fout.value) and "cs_fixture" not in str(fout.value)

    class Kapot(FakeHttp):
        def get(self, *a, **k): raise requests.ConnectionError("ck_fixture")
    with pytest.raises(writer.WriteError) as fout:
        writer.build_sender(Kapot())(PAYLOAD)
    assert "ck_fixture" not in str(fout.value)


@pytest.mark.parametrize("url,host", [("http://shop.example.invalid", "shop.example.invalid"),
                                       ("https://shop.example.invalid", "andere.example.invalid"),
                                       ("https://user:pw@shop.example.invalid", "shop.example.invalid"),
                                       ("https://shop.example.invalid:8443", "shop.example.invalid"),
                                       ("https://shop.example.invalid/../x", "shop.example.invalid")])
def test_schrijfkoppeling_weigert_onveilige_adressen(woo_env, monkeypatch, url, host):
    monkeypatch.setenv("NUVEMIXA_WOO_URL", url)
    monkeypatch.setenv("NUVEMIXA_WOO_HOST", host)
    with pytest.raises(writer.WriteError):
        writer.build_sender(FakeHttp())


def test_geen_sleutels_in_de_code():
    import inspect
    for module in (writer, nc):
        bron = inspect.getsource(module)
        assert not re.search(r"\b(ck|cs)_[0-9a-f]{20,}", bron) and "sk-" not in bron
