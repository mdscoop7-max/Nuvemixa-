import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

import app as dashboard
import nv_webshop_visits as visits
from test_system_check import administrator  # noqa: F401  (fixture)

SHOP = "https://nuvemixa.alwaysdata.net"
BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


@pytest.fixture
def counter(monkeypatch, tmp_path):
    monkeypatch.setattr(visits, "DB", tmp_path / "visits.sqlite3")
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_DATABASE_URL", raising=False)
    monkeypatch.delenv("NUVEMIXA_DASHBOARD_BACKEND", raising=False)
    monkeypatch.setenv("NUVEMIXA_WEBSHOP_TRACKING", "true")
    return dashboard.app.test_client()


def hit(client, path="/", origin=SHOP, agent=BROWSER, ip="203.0.113.7", **headers):
    base = {"Origin": origin, "User-Agent": agent, "X-Forwarded-For": ip, "Content-Type": "text/plain", **headers}
    return client.post("/api/webshop-visit", data='{"p": "%s"}' % path, headers=base)


def rows(tmp):
    with closing(sqlite3.connect(tmp)) as db:
        return db.execute("SELECT * FROM webshop_daily_visitors").fetchall()


def test_valid_visit_is_counted_once_per_visitor(counter):
    assert hit(counter, "/").status_code == 204
    data = rows(visits.DB)
    assert len(data) == 1 and data[0][3] == 1


def test_reload_is_not_counted_but_other_page_is(counter):
    hit(counter, "/product/a")
    hit(counter, "/product/a")
    hit(counter, "/product/b")
    (row,) = rows(visits.DB)
    assert row[3] == 2


def test_two_real_visitors_are_counted_separately(counter):
    hit(counter, "/", ip="203.0.113.7")
    hit(counter, "/", ip="203.0.113.8")
    assert len(rows(visits.DB)) == 2


def test_unknown_or_missing_origin_is_refused_and_nothing_stored(counter):
    assert hit(counter, origin="https://evil.example").status_code == 403
    assert counter.post("/api/webshop-visit", data="{}").status_code == 403
    assert not visits.DB.exists()


def test_nothing_stored_when_tracking_is_not_activated(counter, monkeypatch):
    monkeypatch.delenv("NUVEMIXA_WEBSHOP_TRACKING")
    assert hit(counter).status_code == 204
    assert not visits.DB.exists()


@pytest.mark.parametrize("agent", ["", "Googlebot/2.1", "curl/8.0", "Render/1.0", "UptimeRobot/2.0", "HeadlessChrome/120"])
def test_bots_and_monitoring_are_ignored(counter, agent):
    hit(counter, agent=agent)
    assert not visits.DB.exists()


@pytest.mark.parametrize("path", ["/dashboard", "/dashboard?section=onderzoek", "/wp-admin/x", "/api/x", "//evil.example", "nope"])
def test_dashboard_admin_and_invalid_paths_are_ignored(counter, path):
    hit(counter, path)
    assert not visits.DB.exists()


@pytest.mark.parametrize("header", [{"DNT": "1"}, {"Sec-GPC": "1"}, {"Sec-Purpose": "prefetch"}])
def test_privacy_signals_and_prefetch_are_respected(counter, header):
    hit(counter, **header)
    assert not visits.DB.exists()


def test_preflight_is_answered_without_counting(counter):
    response = counter.options("/api/webshop-visit", headers={"Origin": SHOP})
    assert response.status_code == 204 and response.headers["Access-Control-Allow-Origin"] == SHOP
    assert not visits.DB.exists()


def test_no_ip_or_browser_is_stored(counter):
    hit(counter, ip="203.0.113.77")
    with closing(sqlite3.connect(visits.DB)) as db:
        dump = " ".join(str(v) for row in db.execute("SELECT * FROM webshop_daily_visitors") for v in row)
    assert "203.0.113.77" not in dump and "Mozilla" not in dump


def test_visitor_hash_changes_every_day_and_needs_the_secret():
    a = visits.visitor_hash("2026-11-16", "1.2.3.4", BROWSER, "secret")
    assert a == visits.visitor_hash("2026-11-16", "1.2.3.4", BROWSER, "secret")
    assert a != visits.visitor_hash("2026-11-17", "1.2.3.4", BROWSER, "secret")
    assert a != visits.visitor_hash("2026-11-16", "1.2.3.4", BROWSER, "other")


def test_day_week_month_total_use_dutch_calendar_days(counter):
    nl = ZoneInfo("Europe/Amsterdam")
    # 2026-11-15 is a Sunday; 23:30 UTC on Saturday is already Sunday 00:30 in the Netherlands.
    sunday_night = datetime(2026, 11, 14, 23, 30, tzinfo=timezone.utc).astimezone(nl)
    monday = datetime(2026, 11, 16, 9, 0, tzinfo=nl)
    earlier_month = datetime(2026, 10, 30, 12, 0, tzinfo=nl)
    for moment, ip in ((sunday_night, "10.0.0.1"), (monday, "10.0.0.2"), (monday, "10.0.0.3"), (earlier_month, "10.0.0.4")):
        visits.register_hit("/", ip, BROWSER, "secret", now=moment)
    with dashboard.app.test_request_context("/"):
        result = visits.summary(today=date(2026, 11, 16))
    periods = {label: (visitors, views) for label, visitors, views in result["periods"]}
    assert periods["Vandaag"] == (2, 2)
    assert periods["Deze week"] == (2, 2)      # week starts Monday 16 Nov; Sunday 15 Nov is previous week
    assert periods["Deze maand"] == (3, 3)     # includes Sunday 15 Nov, excludes 30 Oct
    assert periods["Totaal"] == (4, 4)
    assert result["has_data"] and len(result["chart"]) == 30
    assert dict((d, v) for d, v, _ in result["chart"])["15-11"] == 1


def test_data_survives_a_restart(counter):
    hit(counter, "/")
    with dashboard.app.test_request_context("/"):
        before = visits.summary()["periods"]
    # A new process opens the same database file and sees the same measurements.
    with closing(sqlite3.connect(visits.DB)) as db:
        assert db.execute("SELECT count(*) FROM webshop_daily_visitors").fetchone()[0] == 1
    with dashboard.app.test_request_context("/"):
        assert visits.summary()["periods"] == before


def test_dashboard_says_clearly_when_tracking_is_not_activated(administrator, monkeypatch, tmp_path):
    monkeypatch.setattr(visits, "DB", tmp_path / "empty.sqlite3")
    monkeypatch.delenv("NUVEMIXA_WEBSHOP_TRACKING", raising=False)
    page = administrator.get("/dashboard?section=statistieken").get_data(as_text=True)
    assert "Tracking nog niet geactiveerd" in page and "nv-webshop-visit.js" in page


def test_dashboard_shows_real_numbers_without_invented_data(administrator, monkeypatch, tmp_path):
    monkeypatch.setattr(visits, "DB", tmp_path / "real.sqlite3")
    monkeypatch.setenv("NUVEMIXA_WEBSHOP_TRACKING", "true")
    page = administrator.get("/dashboard?section=statistieken").get_data(as_text=True)
    assert "nog geen bezoek van de webshop ontvangen" in page
    hit(dashboard.app.test_client(), "/")
    page = administrator.get("/dashboard?section=statistieken").get_data(as_text=True)
    assert "Deze maand" in page and "nog geen bezoek van de webshop ontvangen" not in page
    assert "SQLite op de dashboardhost" in page  # honest warning that this storage is not permanent


def test_summary_counts_all_visitors_per_period_and_series(counter):
    """Bezoekers uit elk land (andere IP-adressen) tellen mee; week-, maand- en totaalreeks kloppen."""
    zone = ZoneInfo("Europe/Amsterdam")
    now = datetime.now(zone)
    for ip in ("203.0.113.7", "198.51.100.9", "192.0.2.44"):  # drie verschillende bezoekers vandaag
        visits.register_hit("/", ip, BROWSER, "geheim", now=now)
    earlier = now.replace(day=1) - __import__("datetime").timedelta(days=3)  # vorige maand
    visits.register_hit("/", "203.0.113.7", BROWSER, "geheim", now=earlier)
    data = visits.summary(today=now.date())
    labels = {label: visitors for label, visitors, views in data["periods"]}
    assert labels["Vandaag"] == 3 and labels["Totaal"] == 4
    assert labels["Deze maand"] == 3
    assert len(data["weeks"]) == 12 and len(data["months"]) == 12
    assert data["months"][-1][1] == 3 and data["months"][-2][1] == 1
    assert sum(number for _, number in data["weeks"]) >= 3


def test_dashboard_home_shows_visitor_card_without_invented_numbers(counter, administrator):
    page = administrator.get("/dashboard?section=dashboard")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert "Webshopbezoekers" in body
