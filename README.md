# REIT Valuation Tool
![App Interface](images/screenshot.png)

A Python desktop app for multi-model REIT valuation, combining three methodologies simultaneously with scenario analysis, sensitivity tables, and a local file-based database.

---

## Overview

The tool was built to support structured investment analysis of Real Estate Investment Trusts. Runs three independent valuation models side by side — DDM, AFFO DCF, and NAV — and produces a weighted cross-model summary that can be adjusted based on the REIT type. All analyses are saved as individual JSON files in a local `reit_db/` directory.

---

## Models

### 1. Two-Stage Dividend Discount Model (DDM)
- Stage 1: user-defined high-growth period (default 5 years)
- Stage 2: perpetual terminal growth rate
- Three scenarios: Worst / Base / Best
- Displays dividend coverage ratio (AFFO per share / DPS)

### 2. AFFO-Based DCF
- Discounted cash flow using Adjusted Funds from Operations
- Discounts the AFFO equity flow at cost of equity (sourced from DDM rate); no net-debt bridge
- 10-year projection horizon (configurable)
- Three scenarios with independent growth and terminal assumptions

### 3. Net Asset Value (NAV)
- NAV per share from Gross Asset Value, debt, and other liabilities
- Implied cap rate display (requires NOI input)
- **GAV sensitivity table**: NAV at ±10%, ±20% GAV
- **Cap rate sensitivity table**: NAV at cap rates from 3.5% to 6.5%
- Premium / discount to market price

---
## Project

```
reit_valuation_app.py    # Entry point — GUI, layout, event loop
schema.py                # Input field definitions and validation
models.py                # Pure math (DDM, AFFO DCF, NAV)
db.py                    # JSON persistence
tests/                   # pytest tests. Run with: pytest tests/
reit_db/                 # Saved analyses (created on first run)
```

---

## Requirements
```
Python 3.9+
FreeSimpleGUI
pytest (for tests)
```
---


## Database

**Local JSON database** — each analysis is saved as an individual `.json` file in `reit_db/`. From the GUI you can save, load, delete, open the JSON file, or open the database folder.

**Database fields:**
| Field | Description |
|---|---|
| `analysis_name` | User-defined label |
| `shares` | Shares / units outstanding (millions) |
| `market_price` | Current market price |
| `dps` | Annual dividend per share |
| `ddm_stage1_years` | DDM Stage 1 projection years |
| `ddm_[worst/base/best]_growth` | Stage 1 growth rate per scenario |
| `ddm_[worst/base/best]_terminal` | Stage 2 terminal growth rate per scenario |
| `ddm_[worst/base/best]_rate` | Discount rate per scenario |
| `affo` | AFFO (millions, TTM) |
| `affo_debt` | Total debt (millions) — vestigial, retained for back-compat |
| `affo_cash` | Cash & equivalents (millions) — vestigial, retained for back-compat |
| `affo_years` | DCF projection years |
| `affo_[worst/base/best]_growth` | AFFO growth rate per scenario |
| `affo_[worst/base/best]_wacc` | WACC per scenario — vestigial; AFFO-DCF discount rate comes from `ddm_*_rate` |
| `affo_[worst/base/best]_terminal` | Terminal growth rate per scenario |
| `gav` | Gross Asset Value (millions) |
| `nav_debt` | Total debt for NAV (millions) |
| `nav_other` | Other liabilities (millions) |
| `noi` | Net Operating Income (millions) |
| `w_ddm` / `w_affo` / `w_nav` | Model weights (%) |
| `notes` | Free-text notes |
| `analysis_date` | Auto-recorded date of save (YYYY-MM-DD) |

---


## Notes

- Required fields (shares, DPS, AFFO, GAV, projection years) must be positive — the app validates on Calculate and reports the offending field.
- Cap rate sensitivity requires the NOI field to be populated.
- Weights do not need to sum to 100 — the weighted average normalises automatically and a status-bar notice appears if any model returned no result.
- In DDM, to run a single-stage model set Stage 1 Growth = Stage 2 Terminal Growth for whichever scenario you want to treat as single-stage. (You can mix: e.g., use two-stage for best case and single-stage logic for worst case within the same calculation.)
---

## Weighting Guide

| REIT Type | Recommended Weighting |
|---|---|
| Property-heavy (core, net lease) | NAV 50–60%, AFFO DCF 30%, DDM 10–20% |
| Dividend-focused (mREITs, high-yield) | DDM 40–50%, AFFO DCF 30%, NAV 20–30% |
| Balanced (residential, diversified) | Equal weights (33/34/33) |

NAV should carry more weight when the portfolio consists of readily appraised assets (apartments, industrial, retail) and when the REIT is in an operational transition where current cash flows understate intrinsic value. DDM deserves more weight when dividend sustainability and growth are the primary investment thesis.

---

## License

MIT - do whatever you like.
