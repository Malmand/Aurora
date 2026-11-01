import pytest

from aurora.data import paths
from aurora.data.site import check, load_site, value


def test_every_value_sourced_or_flagged():
    site = load_site()
    assert check(site, paths.SOURCES_MD.read_text(encoding="utf-8")) == []


def test_missing_values_are_refused():
    site = load_site()
    missing = [k for k, e in site["values"].items() if e["status"] == "missing"]
    assert missing, "expected some missing values while documents are unread"
    with pytest.raises(KeyError):
        value(site, missing[0])


def test_inl_current_state_is_used():
    site = load_site()
    assert value(site, "diesel_available_kw") == value(site, "diesel_combined_kw_inl") - value(
        site, "diesel_out_of_service_kw_inl")
    assert value(site, "diesel_price_php_per_l") == 113
