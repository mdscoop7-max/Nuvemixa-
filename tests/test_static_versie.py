"""Statische bestanden krijgen een inhoudsversie, zodat gewijzigde scripts niet uit een 7-daagse browsercache komen."""
import re

from test_system_check import administrator  # noqa: F401

import app as dashboard


def test_dashboard_assets_carry_content_version(administrator):
    html = administrator.get("/dashboard?section=onderzoek").get_data(as_text=True)
    for name in ("nv-margin-live.js", "nv-search-history.js", "nv-research-rows.js", "nv-search-meter.js",
                 "nv-dashboard-navigation.js", "nv-dashboard-compact-20261118.css"):
        found = re.search(re.escape(name) + r"\?v=([0-9a-f]{10})\"", html)
        assert found, name
        assert found.group(1) == dashboard.nv_static_version(name)
    assert "?v=1\"" not in html and "nv_static_version" not in html


def test_version_changes_with_content(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard.app, "static_folder", str(tmp_path))
    dashboard._NV_STATIC_VERSIONS.clear()
    (tmp_path / "x.js").write_text("a")
    first = dashboard.nv_static_version("x.js")
    dashboard._NV_STATIC_VERSIONS.clear()
    (tmp_path / "x.js").write_text("b")
    assert dashboard.nv_static_version("x.js") != first
    dashboard._NV_STATIC_VERSIONS.clear()
