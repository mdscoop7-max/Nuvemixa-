"""Een mislukte Syncee-taak toont één keer de fout; een mislukte extra zoekvariant houdt eerdere resultaten."""
from concurrent.futures import Future

import requests

import nv_research_sources as rs
import nv_source_guard as guard


def failed():
    future = Future()
    future.set_exception(requests.Timeout("traag"))
    return future


def test_failed_job_is_returned_once_then_retried():
    guard._jobs.clear()
    calls = []

    def submit():
        calls.append(1)
        return failed() if len(calls) == 1 else Future()

    first = guard.job("k", submit)
    assert first.exception() is not None
    assert guard.job("k", submit) is first          # de fout wordt getoond, niet 'nog bezig'
    retry = guard.job("k", submit)
    assert retry is not first and len(calls) == 2   # daarna een nieuwe poging


def test_failing_extra_variant_keeps_earlier_results(monkeypatch):
    found = ({"website": "https://syncee.com/supplier/1/a"}, {"url": "https://syncee.com/product/1/a"})

    def search(fetch, variant, *args, **kwargs):
        if variant == "eerste":
            return [found]
        raise requests.Timeout("traag")

    monkeypatch.setattr(rs, "syncee_search", search)
    attempts = []
    out = rs.syncee_products(None, "eerste", "NL", {}, {}, None, None, None, term="x", product_matches=None,
                             attempts=attempts, alternates=("tweede",))
    assert out == [found] and attempts[-1]["error"] == "Timeout"


def test_failing_first_variant_still_reports_error(monkeypatch):
    monkeypatch.setattr(rs, "syncee_search", lambda *a, **k: (_ for _ in ()).throw(requests.Timeout("x")))
    try:
        rs.syncee_products(None, "eerste", "NL", {}, {}, None, None, None, term="x", product_matches=None)
    except requests.Timeout:
        return
    raise AssertionError("fout verwacht")
