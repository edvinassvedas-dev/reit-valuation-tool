# pip install pytest
# run: pytest tests/

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import fields
from schema import Inputs, DEFAULTS, gui_key


def _base_payload(**overrides):
    payload = dict(DEFAULTS)
    placeholders = {
        "-SHARES-": "100", "-DPS-": "2",
        "-AFFO-": "150", "-AFFO_DEBT-": "200", "-AFFO_CASH-": "50",
        "-GAV-": "5000", "-NAV_DEBT-": "2000",
    }
    for k, v in placeholders.items():
        if payload.get(k, "") == "":
            payload[k] = v
    payload.update(overrides)
    return payload



def test_from_window_all_defaults_with_minimal_required():
    inp = Inputs.from_window(_base_payload())
    assert inp.shares == 100.0
    assert inp.dps == 2.0
    assert inp.ddm_stage1_years == 5
    assert inp.affo_years == 10
    assert inp.w_ddm == 33.0


def test_from_window_optional_absent_returns_none():
    inp = Inputs.from_window(_base_payload())
    assert inp.market_price is None
    assert inp.noi is None


def test_from_window_optional_present_parses():
    inp = Inputs.from_window(_base_payload(**{"-MARKET_PRICE-": "55", "-NOI-": "250"}))
    assert inp.market_price == 55.0
    assert inp.noi == 250.0


def test_from_window_int_field_returns_int_not_float():
    inp = Inputs.from_window(_base_payload(**{"-DDM_STAGE1_YEARS-": "7"}))
    assert inp.ddm_stage1_years == 7
    assert isinstance(inp.ddm_stage1_years, int)


def test_from_window_int_field_accepts_float_string():
    inp = Inputs.from_window(_base_payload(**{"-DDM_STAGE1_YEARS-": "5.0"}))
    assert inp.ddm_stage1_years == 5
    assert isinstance(inp.ddm_stage1_years, int)



def test_from_window_missing_required_field_names_it():
    payload = _base_payload(**{"-SHARES-": ""})
    with pytest.raises(ValueError, match="shares is required"):
        Inputs.from_window(payload)


def test_from_window_garbage_input_names_field_and_value():
    payload = _base_payload(**{"-DPS-": "abc"})
    with pytest.raises(ValueError, match="dps.*abc"):
        Inputs.from_window(payload)


def test_from_window_whitespace_only_treated_as_empty():
    payload = _base_payload(**{"-SHARES-": "   "})
    with pytest.raises(ValueError, match="shares is required"):
        Inputs.from_window(payload)


def test_from_window_optional_whitespace_only_returns_none():
    payload = _base_payload(**{"-NOI-": "   "})
    inp = Inputs.from_window(payload)
    assert inp.noi is None



def test_ddm_scenario_returns_decimals_for_base():
    inp = Inputs.from_window(_base_payload())
    g1, g2, r = inp.ddm_scenario("base")
    assert (g1, g2, r) == (0.04, 0.02, 0.08)


def test_affo_scenario_returns_decimals_for_worst():
    inp = Inputs.from_window(_base_payload())
    g, w, t = inp.affo_scenario("worst")
    assert (g, w, t) == (0.01, 0.09, 0.015)



def test_defaults_cover_every_inputs_field():
    expected = {gui_key(f.name) for f in fields(Inputs)} | {"-ANALYSIS_NAME-", "-NOTES-"}
    assert set(DEFAULTS) == expected
