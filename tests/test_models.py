# pip install pytest
# run: pytest tests/

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import (
    ddm_two_stage, affo_dcf_calculate, affo_dcf_equity, nav_calculate, nav_from_cap_rate,
    nav_sensitivity, mos, upside_pct, weighted_avg,
)


# =DDM

def test_ddm_two_stage_known_value():
    # Hand-computed: stage-1 PVs (~9.20) + discounted TV (~32.37) ≈ 41.57.
    price = ddm_two_stage(2.0, 0.05, 5, 0.025, 0.08)
    assert price == pytest.approx(41.57, abs=0.01)


def test_ddm_rate_must_exceed_terminal():
    with pytest.raises(ValueError, match="Discount rate"):
        ddm_two_stage(2.0, 0.05, 5, 0.09, 0.08)


def test_ddm_rejects_zero_stage1_years():
    with pytest.raises(ValueError, match="Stage 1 years"):
        ddm_two_stage(2.0, 0.05, 0, 0.025, 0.08)


def test_ddm_rejects_nonpositive_dps():
    with pytest.raises(ValueError, match="Dividend"):
        ddm_two_stage(0, 0.05, 5, 0.025, 0.08)


def test_ddm_single_stage_when_g1_equals_g2():
    # setting Stage-1 growth equal to terminal should approximate a Gordon model: P ≈ D1 / (r - g)  where D1 = dps * (1 + g)
    g, r, dps = 0.03, 0.08, 2.0
    gordon = dps * (1 + g) / (r - g)
    two_stage = ddm_two_stage(dps, g, 5, g, r)
    assert two_stage == pytest.approx(gordon, abs=0.01)


# =AFFO DCF

def test_affo_dcf_known_value():
    price = affo_dcf_calculate(100, 0, 0, 100, 10, 0.03, 0.08, 0.02)
    assert price == pytest.approx(18.36, abs=0.01)


def test_affo_dcf_wacc_must_exceed_terminal():
    with pytest.raises(ValueError, match="WACC"):
        affo_dcf_calculate(100, 0, 0, 100, 10, 0.03, 0.02, 0.05)


def test_affo_dcf_zero_shares_raises():
    with pytest.raises(ValueError, match="Shares"):
        affo_dcf_calculate(100, 0, 0, 0, 10, 0.03, 0.08, 0.02)


def test_affo_dcf_debt_reduces_equity():
    no_debt = affo_dcf_calculate(100, 0,   0, 100, 10, 0.03, 0.08, 0.02)
    debt    = affo_dcf_calculate(100, 500, 0, 100, 10, 0.03, 0.08, 0.02)
    assert debt == pytest.approx(no_debt - 5.0, abs=0.001)


# =AFFO DCF equity (corrected)

def test_affo_dcf_equity_coe_must_exceed_terminal():
    with pytest.raises(ValueError, match="Cost of equity"):
        affo_dcf_equity(100, 100, 10, 0.03, 0.02, 0.05)


def test_affo_dcf_equity_zero_shares_raises():
    with pytest.raises(ValueError, match="Shares"):
        affo_dcf_equity(100, 0, 10, 0.03, 0.08, 0.02)


def test_affo_dcf_equity_zero_leverage_equivalence():
    # With debt=0, cash=0, and WACC == CoE, both methods must agree exactly.
    # Reference values from VNA base case (handoff §5.1).
    result = affo_dcf_equity(1541, 848, 5, 0.035, 0.09, 0.0175)
    legacy = affo_dcf_calculate(1541, 0, 0, 848, 5, 0.035, 0.09, 0.0175)
    assert result == pytest.approx(legacy)
    assert result == pytest.approx(27.486, abs=0.001)


# =NAV=

def test_nav_basic():
    assert nav_calculate(1000, 400, 50, 100) == pytest.approx(5.50)


def test_nav_zero_shares_raises():
    with pytest.raises(ValueError):
        nav_calculate(1000, 400, 50, 0)


def test_nav_from_cap_rate_equivalence():
    direct  = nav_calculate(1000, 400, 50, 100)
    derived = nav_from_cap_rate(50, 0.05, 400, 50, 100)
    assert derived == pytest.approx(direct)


def test_nav_sensitivity_shape_and_anchor():
    labels, navs = nav_sensitivity(1000, 400, 50, 100)
    assert len(labels) == 5 and len(navs) == 5
    assert navs[2] == pytest.approx(5.50)        #
    assert navs[0] <  navs[2] < navs[4]          #


# =MoS/upside

def test_mos_positive_when_intrinsic_above_market():
    assert mos(100, 80) == pytest.approx(20.0)


def test_mos_negative_when_intrinsic_below_market():
    assert mos(100, 120) == pytest.approx(-20.0)


def test_mos_returns_none_for_nonpositive_intrinsic():
    assert mos(0, 50) is None
    assert mos(-5, 50) is None


def test_upside_pct_basic():
    assert upside_pct(120, 100) == pytest.approx(20.0)
    assert upside_pct(80, 100) == pytest.approx(-20.0)


# =Weighted avgs=

def test_weighted_avg_all_three():
    avg, renorm = weighted_avg(50, 60, 70, 33, 34, 33)
    expected = (50*33 + 60*34 + 70*33) / 100
    assert avg == pytest.approx(expected)
    assert renorm is False


def test_weighted_avg_renormalizes_when_one_missing():
    avg, renorm = weighted_avg(None, 50, 60, 30, 30, 40)
    # 50*(30/70) + 60*(40/70)
    expected = (50*30 + 60*40) / 70
    assert avg == pytest.approx(expected)
    assert renorm is True


def test_weighted_avg_returns_none_when_all_missing():
    avg, renorm = weighted_avg(None, None, None, 33, 34, 33)
    assert avg is None
    assert renorm is True


def test_weighted_avg_handles_zero_weights():
    avg, renorm = weighted_avg(50, 60, 70, 0, 0, 0)
    assert avg is None
