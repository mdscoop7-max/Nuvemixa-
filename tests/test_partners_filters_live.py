import nv_partners as p


def n(**a):
    return len(p.search(a))


def test_soort_filters_partition_without_inventing():
    assert n(soort="affiliate") == 4 and all(r["models"] == ("C",) for r in p.search({"soort": "affiliate"}))
    assert all("C" not in r["models"] for r in p.search({"soort": "dropshipping"}))
    assert n(soort="hybride") == 0  # geen verzonnen hybride partners


def test_affiliate_is_not_dropshipping():
    assert not any(r["status"] == "aantoonbaar" for r in p.search({"soort": "affiliate"}))


def test_woo_confirmed_subset_of_hint():
    assert 0 < n(woo="bevestigd") <= n(woo="aanwijzing") < n()
    assert all(r["woo"] == "bevestigd" for r in p.search({"woo": "bevestigd"}))


def test_scope_and_eu():
    assert all(r["country"] in p.EU for r in p.search({"eu": "1"}))
    assert 0 < n(bereik="nl") < n(bereik="europa") < n()


def test_english_synonym_matches_dutch():
    assert n(q="perfume") == n(q="parfum") >= 1


def test_rows_carry_compare_fields():
    r = p.search({})[0]
    assert {"woo", "affiliate_text", "dropship_status", "scope_labels"} <= set(r)
