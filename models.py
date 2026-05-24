def ddm_two_stage(dps, growth1, years1, growth2, discount_rate):
    """Two-stage DDM. Stage 1: growth1 for years1. Stage 2: growth2 perpetual."""
    if discount_rate <= growth2:
        raise ValueError("Discount rate must be greater than Stage 2 growth rate.")
    if years1 < 1:
        raise ValueError("Stage 1 years must be at least 1.")
    if dps <= 0:
        raise ValueError("Dividend per share must be greater than zero.")
    pv, d = 0.0, dps
    for t in range(1, int(years1) + 1):
        d *= (1 + growth1)
        pv += d / (1 + discount_rate) ** t
    tv = d * (1 + growth2) / (discount_rate - growth2)
    pv += tv / (1 + discount_rate) ** int(years1)
    return pv


def affo_dcf_calculate(affo, debt, cash, shares, years, growth_rate, wacc, terminal_growth):
    """AFFO-based DCF, returning equity value per share"""
    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth rate.")
    if shares <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")
    projected = [affo * (1 + growth_rate) ** i for i in range(1, years + 1)]
    discounted = [v / (1 + wacc) ** i for i, v in enumerate(projected, 1)]
    tv = projected[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    dtv = tv / (1 + wacc) ** years
    ev = sum(discounted) + dtv
    return (ev - debt + cash) / shares


def nav_calculate(gross_asset_value, total_debt, other_liabilities, shares):
    """NAV per share"""
    if shares <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")
    return (gross_asset_value - total_debt - other_liabilities) / shares


def nav_from_cap_rate(noi, cap_rate, total_debt, other_liabilities, shares):
    """NAV per share derived from NOI / cap_rate as GAV"""
    if cap_rate <= 0:
        raise ValueError("Cap rate must be greater than zero.")
    gav = noi / cap_rate
    return nav_calculate(gav, total_debt, other_liabilities, shares)


def nav_sensitivity(gross_asset_value, total_debt, other_liabilities, shares):
    """Return ([labels], [navs]) for GAV shifted by -20%, -10%, 0, +10%, +20%."""
    steps = [-0.20, -0.10, 0.0, 0.10, 0.20]
    rows, labels = [], []
    for s in steps:
        adj_gav = gross_asset_value * (1 + s)
        rows.append(nav_calculate(adj_gav, total_debt, other_liabilities, shares))
        labels.append(f"GAV {s*100:+.0f}%")
    return labels, rows


def mos(intrinsic, market):
    """Margin of safety as a percentage, or None if intrinsic <= 0"""
    if intrinsic <= 0:
        return None
    return (intrinsic - market) / intrinsic * 100


def upside_pct(intrinsic, market):
    """Upside relative to market price, as a percentage."""
    return (intrinsic - market) / market * 100


def weighted_avg(ddm_p, affo_p, nav_p, w_ddm, w_affo, w_nav):
    pairs = [(p, w) for p, w in [(ddm_p, w_ddm), (affo_p, w_affo), (nav_p, w_nav)]
             if p is not None]
    total_w = sum(w for _, w in pairs)
    renormalized = len(pairs) < 3
    if total_w == 0:
        return None, False
    return sum(p * w for p, w in pairs) / total_w, renormalized
