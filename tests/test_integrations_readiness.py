import base64
from app import app
from integration_readiness import status_rows

def test_integrations_never_claim_live_measurements(monkeypatch):
    monkeypatch.delenv("TRENDMIX_RANKFIX_REPORT_URL", raising=False)
    rows=status_rows()
    assert len(rows)==5
    assert all(row["last_check"]=="Nog niet uitgevoerd" for row in rows)
    assert all("Geen geverifieerde" in row["metrics"] for row in rows)

def test_monitoring_private_and_read_only(monkeypatch):
    monkeypatch.setenv("TRENDMIX_ADMIN_USER","tester")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD","a-strong-admin-password")
    monkeypatch.delenv("VERCEL_ENV",raising=False)
    client=app.test_client()
    assert client.get("/beheer/monitoring").status_code == 401
    headers={"Authorization":"Basic "+base64.b64encode(b"tester:a-strong-admin-password").decode()}
    response=client.get("/beheer/monitoring",headers=headers)
    assert response.status_code==200
    assert b"RankFix" in response.data
    assert response.headers["Cache-Control"]=="no-store"
    assert client.post("/beheer/monitoring",headers=headers).status_code==403
