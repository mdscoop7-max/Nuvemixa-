from pathlib import Path


def test_klanten_has_reviews_button_to_alwaysdata():
    tpl = Path(__file__).resolve().parent.parent.joinpath("templates", "dashboard.html").read_text(encoding="utf-8")
    start = tpl.index("{% if section == 'klanten' %}")
    block = tpl[start:start + 1500]
    assert "⭐ Reviews beheren" in block
    assert 'href="https://nuvemixa.alwaysdata.net/admin/reviews"' in block
    assert 'rel="noopener noreferrer"' in block
