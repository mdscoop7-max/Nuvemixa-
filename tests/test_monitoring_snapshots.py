"""Admin monitoring can save genuine submitted metrics but cannot mutate remote services."""
import base64
from app import app
from monitor_snapshots import latest_reports

def test_verified_metric_form(monkeypatch,tmp_path):
    monkeypatch.setenv("TRENDMIX_ADMIN_USER","tester")
    monkeypatch.setenv("TRENDMIX_ADMIN_PASSWORD","admin-password-long-enough")
    monkeypatch.delenv("VERCEL_ENV",raising=False)
    monkeypatch.setenv("TRENDMIX_MONITORING_DB",str(tmp_path/"monitor.db"))
    headers={"Authorization":"Basic "+base64.b64encode(b"tester:admin-password-long-enough").decode()}
    client=app.test_client()
    response=client.get("/beheer/monitoring",headers=headers)
    assert response.status_code==200
    with client.session_transaction() as s:
        token=s["_tm_csrf"]
    valid=client.post("/beheer/monitoring",headers=headers,data={"_csrf_token":token,
        "source":"rankfix","subject":"TrendMix QA 27 oktober","metric":"seo_score","value":"87.5"})
    assert valid.status_code==303
    rows=latest_reports()
    assert rows[0]["metrics"]["seo_score"] == 87.5
    invalid=client.post("/beheer/monitoring",headers=headers,data={"_csrf_token":token,
        "source":"google_ads","subject":"TrendMix QA 27 oktober","metric":"seo_score","value":"87.5"})
    assert invalid.status_code==400
    assert len(latest_reports())==1
