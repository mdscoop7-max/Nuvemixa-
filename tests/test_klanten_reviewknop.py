from pathlib import Path


def test_klanten_has_reviews_button():
    tpl = Path(__file__).resolve().parent.parent.joinpath("templates", "dashboard.html").read_text(encoding="utf-8")
    start = tpl.index("{% if section == 'klanten' %}")
    block = tpl[start:start + 1500]
    assert "⭐ Reviews beheren" in block
    assert "url_for('admin_reviews_beheren')" in block
    assert 'rel="noopener noreferrer"' in block
