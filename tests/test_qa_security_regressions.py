"""Security regressions from Trend Mix QA round one."""
import pytest
from customer_accounts import authenticate
from monitor_snapshots import save_report

def test_unknown_customer_does_not_crash(monkeypatch, tmp_path):
    monkeypatch.setenv("TRENDMIX_ACCOUNTS_DB", str(tmp_path / "accounts.sqlite3"))
    account, limited = authenticate("unknown@example.test", "not-the-password", "127.0.0.1")
    assert account is None
    assert limited is False

@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_metrics_cannot_store_nonfinite_values(monkeypatch, tmp_path, value):
    monkeypatch.setenv("TRENDMIX_MONITORING_DB", str(tmp_path / "monitor.sqlite3"))
    with pytest.raises(ValueError):
        save_report("rankfix", "TrendMix QA", {"seo_score": value})
