"""The numbers on the deck must follow from the committed results."""
import json

import pytest

from aurora.experiments import headline as H


@pytest.fixture(scope="module")
def nums():
    return json.loads(json.dumps(H.all_numbers(), default=float))


def test_committed_json_is_current(nums):
    assert json.loads(H.OUT_JSON.read_text(encoding="utf-8")) == nums


def test_deck_headlines(nums):
    ny, st = nums["normal_year"], nums["storms_14d"]
    assert round(ny["diesel_saved_pct"]) == 37
    assert round(ny["diesel_saved_l"], -3) == 126_000
    assert ny["co2_saved_t"] == 338
    assert st["clinic_dark_h"]["C"] == 0
    assert round(st["homes_hours_cut_vs_operator_pct"]) == -43
    assert nums["sizing"]["chosen"] == {"pv_kwp": 300, "bat_kwh": 1500, "clock_h": 27.6, "capex_mphp": 176.1}


def test_chosen_size_follows_the_rule(nums):
    s = nums["sizing"]
    assert s["clinic_dark_any_size_h"] == 0 and s["chosen"]["clock_h"] >= 24
