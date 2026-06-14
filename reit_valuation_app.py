import os
import subprocess
import sys
from datetime import datetime

import FreeSimpleGUI as sg

from models import (
    ddm_two_stage, affo_dcf_calculate, nav_calculate, nav_from_cap_rate,
    nav_sensitivity, mos, upside_pct, weighted_avg,
)
from db import (
    DB_DIR,
    analysis_path, load_database, save_analysis, delete_analysis,
)
from schema import Inputs, DEFAULTS, PERSISTED_FIELDS, gui_key


# =helpers

def _set_dash(window, *keys):
    for k in keys:
        window[k].update("—")


def render_scenario(window, prefix, intrinsic, market_price):
    pk, mk, uk = f"-{prefix}_PRICE-", f"-{prefix}_MOS-", f"-{prefix}_UPSIDE-"
    if intrinsic is None:
        _set_dash(window, pk, mk, uk)
        return
    if intrinsic <= 0:
        window[pk].update(f"${intrinsic:.2f}", text_color="red")
        _set_dash(window, mk, uk)
        return
    window[pk].update(f"${intrinsic:.2f}", text_color=sg.theme_text_color())
    if market_price:
        m = mos(intrinsic, market_price)
        u = upside_pct(intrinsic, market_price)
        color = "green" if u > 0 else "red"
        window[mk].update(f"{m:+.1f}%" if m is not None else "—", text_color=color)
        window[uk].update(f"{u:+.1f}%", text_color=color)
    else:
        _set_dash(window, mk, uk)


def render_sum_cell(window, pk, uk, price, market_price):
    if price is None:
        _set_dash(window, pk, uk)
        return
    if price <= 0:
        window[pk].update(f"${price:.2f}", text_color="red")
        window[uk].update("—")
        return
    window[pk].update(f"${price:.2f}", text_color=sg.theme_text_color())
    if market_price:
        u = upside_pct(price, market_price)
        window[uk].update(f"{u:+.1f}%", text_color="green" if u > 0 else "red")
    else:
        window[uk].update("—")


# =Status field=

_STATUS_COLORS = {
    "info":    "#666666",
    "success": "#27AE60",
    "warn":    "#D68910",
    "error":   "#C0392B",
}


def set_status(window, msg, level="info"):
    color = _STATUS_COLORS.get(level, _STATUS_COLORS["info"])
    ts = datetime.now().strftime("%H:%M")
    window["-STATUS-"].update(f"[{ts}]  {msg}", text_color=color)


# =DB table=

_TABLE_HEADINGS = ["Analysis Name", "Date"]
_SEARCH_PLACEHOLDER = "Search..."


def _build_sorted_rows(database, sort_state, search=""):
    col, direction = sort_state["col"], sort_state["dir"]
    raw = search.strip()
    term = "" if raw == _SEARCH_PLACEHOLDER else raw.lower()
    pairs = [(r, [r.get("analysis_name", ""), r.get("analysis_date", "")])
             for r in database
             if not term or term in r.get("analysis_name", "").lower()]
    non_empty = [p for p in pairs if p[1][col]]
    empty = [p for p in pairs if not p[1][col]]
    # Date col (1) sorts directly; name col (0) is case-insensitive.
    non_empty.sort(key=lambda p: p[1][col] if col == 1 else p[1][col].lower(),
                   reverse=(direction == "desc"))
    pairs = non_empty + empty
    return [p[0] for p in pairs], [p[1] for p in pairs]


def _update_sort_indicators(window, sort_state):
    arrow = " ▼" if sort_state["dir"] == "desc" else " ▲"
    try:
        tree = window["-ANALYSIS_TABLE-"].Widget
        for i, base in enumerate(_TABLE_HEADINGS):
            text = (base + arrow) if i == sort_state["col"] else base
            tree.heading(f"#{i+1}", text=text)
    except Exception:
        pass


# =Result keys

RESULT_KEYS = [
    "-DDM_WORST_PRICE-", "-DDM_WORST_MOS-", "-DDM_WORST_UPSIDE-",
    "-DDM_BASE_PRICE-",  "-DDM_BASE_MOS-",  "-DDM_BASE_UPSIDE-",
    "-DDM_BEST_PRICE-",  "-DDM_BEST_MOS-",  "-DDM_BEST_UPSIDE-",
    "-DDM_COV-",
    "-AFFO_WORST_PRICE-", "-AFFO_WORST_MOS-", "-AFFO_WORST_UPSIDE-",
    "-AFFO_BASE_PRICE-",  "-AFFO_BASE_MOS-",  "-AFFO_BASE_UPSIDE-",
    "-AFFO_BEST_PRICE-",  "-AFFO_BEST_MOS-",  "-AFFO_BEST_UPSIDE-",
    "-NAV_PRICE-", "-NAV_PREMIUM-", "-NAV_CAP_RATE-",
    "-NAV_S1-", "-NAV_S1U-", "-NAV_S2-", "-NAV_S2U-",
    "-NAV_S3-", "-NAV_S3U-", "-NAV_S4-", "-NAV_S4U-",
    "-NAV_S5-", "-NAV_S5U-",
    "-CAP_S1-", "-CAP_S1U-", "-CAP_S2-", "-CAP_S2U-",
    "-CAP_S3-", "-CAP_S3U-", "-CAP_S4-", "-CAP_S4U-",
    "-CAP_S5-", "-CAP_S5U-", "-CAP_S6-", "-CAP_S6U-",
    "-CAP_S7-", "-CAP_S7U-",
    "-SUM_WORST_DDM-",  "-SUM_WORST_AFFO-",  "-SUM_WORST_NAV-",  "-SUM_WORST_WAVG-",
    "-SUM_BASE_DDM-",   "-SUM_BASE_AFFO-",   "-SUM_BASE_NAV-",   "-SUM_BASE_WAVG-",
    "-SUM_BEST_DDM-",   "-SUM_BEST_AFFO-",   "-SUM_BEST_NAV-",   "-SUM_BEST_WAVG-",
    "-SUM_WORST_DDM_U-","-SUM_WORST_AFFO_U-","-SUM_WORST_NAV_U-","-SUM_WORST_WAVG_U-",
    "-SUM_BASE_DDM_U-", "-SUM_BASE_AFFO_U-", "-SUM_BASE_NAV_U-", "-SUM_BASE_WAVG_U-",
    "-SUM_BEST_DDM_U-", "-SUM_BEST_AFFO_U-", "-SUM_BEST_NAV_U-", "-SUM_BEST_WAVG_U-",
]

CAP_RATE_STEPS = [0.035, 0.04, 0.045, 0.05, 0.055, 0.06, 0.065]
CAP_SENS_KEYS = [
    ("-CAP_S1-", "-CAP_S1U-"), ("-CAP_S2-", "-CAP_S2U-"),
    ("-CAP_S3-", "-CAP_S3U-"), ("-CAP_S4-", "-CAP_S4U-"),
    ("-CAP_S5-", "-CAP_S5U-"), ("-CAP_S6-", "-CAP_S6U-"),
    ("-CAP_S7-", "-CAP_S7U-"),
]
NAV_SENS_KEYS = [
    ("-NAV_S1-", "-NAV_S1U-"), ("-NAV_S2-", "-NAV_S2U-"), ("-NAV_S3-", "-NAV_S3U-"),
    ("-NAV_S4-", "-NAV_S4U-"), ("-NAV_S5-", "-NAV_S5U-"),
]


# ==GUI=

try:
    sg.theme("Reddit")
except Exception:
    sg.theme("Default1")

LBL = 22
INP = 10
INPpct = 5
RES = 10


def result_row(label, res_key, mos_key, upside_key):
    return [
        sg.Text(label, size=(10, 1)),
        sg.Text("—", key=res_key,    size=(RES, 1)),
        sg.Text("—", key=mos_key,    size=(8, 1)),
        sg.Text("—", key=upside_key, size=(8, 1)),
    ]


def col_header():
    return [
        sg.Text("",       size=(10, 1)),
        sg.Text("Price",  size=(RES, 1), font=("Helvetica", 9, "bold")),
        sg.Text("MoS",    size=(8,  1),  font=("Helvetica", 9, "bold")),
        sg.Text("Upside", size=(8,  1),  font=("Helvetica", 9, "bold")),
    ]


# =Shared top row=
shared_top = [
    [sg.Text("REIT Valuation", font=("Helvetica", 16, "bold"), text_color="#0079d3")],
    [sg.Text("Analysis Name:", size=(14, 1)),
     sg.InputText(key="-ANALYSIS_NAME-", size=(45, 1)),
     sg.VerticalSeparator(),
     sg.Text(" Shares Outstanding (M):", size=(20, 1)),
     sg.InputText("", key="-SHARES-", size=(INP, 1)),
     sg.Text("  Market Price:", size=(12, 1)),
     sg.InputText("", key="-MARKET_PRICE-", size=(INP, 1)),
     sg.VerticalSeparator(),
     sg.Text("", key="-STATUS-", size=(50, 1), font=("Helvetica", 9))],
]

# =Notes=
notes_col = [
    [sg.Text("Notes", font=("Helvetica", 11, "bold"))],
    [sg.Multiline(key="-NOTES-", size=(40, 18))],
]

# =DDM=
ddm_col = [
    [sg.Text("1 — Dividend Discount Model (DDM)", font=("Helvetica", 11, "bold"))],
    [sg.Text("Annual Dividend / Share:",  size=(LBL, 1)), sg.InputText("", key="-DPS-", size=(INP, 1))],
    [sg.Text("Stage 1 Years:",            size=(LBL, 1)), sg.InputText("5", key="-DDM_STAGE1_YEARS-", size=(INP, 1))],
    [sg.Text("", size=(LBL, 1)),
     sg.Text("Worst", size=(INPpct, 1), font=("Helvetica", 10, "bold"), text_color="#C0392B"),
     sg.Text("Base",  size=(INPpct, 1), font=("Helvetica", 10, "bold"), text_color="#7F8C8D"),
     sg.Text("Best",  size=(INPpct, 1), font=("Helvetica", 10, "bold"), text_color="#27AE60")],
    [sg.Text("Stage 1 Growth (%):",       size=(LBL, 1)),
     sg.InputText("2", key="-DDM_WORST_GROWTH-",    size=(INPpct, 1)),
     sg.InputText("4", key="-DDM_BASE_GROWTH-",     size=(INPpct, 1)),
     sg.InputText("6", key="-DDM_BEST_GROWTH-",     size=(INPpct, 1))],
    [sg.Text("Stage 2 Terminal Gr. (%):", size=(LBL, 1)),
     sg.InputText("1.5", key="-DDM_WORST_TERMINAL-", size=(INPpct, 1)),
     sg.InputText("2",   key="-DDM_BASE_TERMINAL-",  size=(INPpct, 1)),
     sg.InputText("2.5", key="-DDM_BEST_TERMINAL-",  size=(INPpct, 1))],
    [sg.Text("Discount Rate (%):",        size=(LBL, 1)),
     sg.InputText("9", key="-DDM_WORST_RATE-",      size=(INPpct, 1)),
     sg.InputText("8", key="-DDM_BASE_RATE-",       size=(INPpct, 1)),
     sg.InputText("7", key="-DDM_BEST_RATE-",       size=(INPpct, 1))],
    [sg.HorizontalSeparator()],
    col_header(),
    result_row("Worst:", "-DDM_WORST_PRICE-", "-DDM_WORST_MOS-", "-DDM_WORST_UPSIDE-"),
    result_row("Base:",  "-DDM_BASE_PRICE-",  "-DDM_BASE_MOS-",  "-DDM_BASE_UPSIDE-"),
    result_row("Best:",  "-DDM_BEST_PRICE-",  "-DDM_BEST_MOS-",  "-DDM_BEST_UPSIDE-"),
    [sg.HorizontalSeparator()],
    [sg.Text("Div. Coverage (AFFO/DPS):", size=(26, 1)),
     sg.Text("—", key="-DDM_COV-", size=(8, 1))],
    [sg.Text("Two-stage DDM: Stage 1 high growth, Stage 2 perpetual terminal growth",
             font=("Helvetica", 8), text_color="#888888")],
]

# =AFFO=
affo_col = [
    [sg.Text("2 — AFFO-Based DCF", font=("Helvetica", 11, "bold"))],
    [sg.Text("AFFO (millions):",       size=(LBL, 1)), sg.InputText("", key="-AFFO-",       size=(INP, 1))],
    [sg.Text("Total Debt (millions):", size=(LBL, 1)), sg.InputText("", key="-AFFO_DEBT-",  size=(INP, 1))],
    [sg.Text("Cash (millions):",       size=(LBL, 1)), sg.InputText("", key="-AFFO_CASH-",  size=(INP, 1))],
    [sg.Text("Years to Project:",      size=(LBL, 1)), sg.InputText("10", key="-AFFO_YEARS-", size=(INP, 1))],
    [sg.Text("", size=(LBL, 1)),
     sg.Text("Worst", size=(INPpct, 1), font=("Helvetica", 10, "bold"), text_color="#C0392B"),
     sg.Text("Base",  size=(INPpct, 1), font=("Helvetica", 10, "bold"), text_color="#7F8C8D"),
     sg.Text("Best",  size=(INPpct, 1), font=("Helvetica", 10, "bold"), text_color="#27AE60")],
    [sg.Text("AFFO Growth Rate (%):",  size=(LBL, 1)),
     sg.InputText("1",   key="-AFFO_WORST_GROWTH-",   size=(INPpct, 1)),
     sg.InputText("3",   key="-AFFO_BASE_GROWTH-",    size=(INPpct, 1)),
     sg.InputText("5",   key="-AFFO_BEST_GROWTH-",    size=(INPpct, 1))],
    [sg.Text("WACC (%):",              size=(LBL, 1)),
     sg.InputText("9",   key="-AFFO_WORST_WACC-",     size=(INPpct, 1)),
     sg.InputText("8",   key="-AFFO_BASE_WACC-",      size=(INPpct, 1)),
     sg.InputText("7",   key="-AFFO_BEST_WACC-",      size=(INPpct, 1))],
    [sg.Text("Terminal Growth (%):",   size=(LBL, 1)),
     sg.InputText("1.5", key="-AFFO_WORST_TERMINAL-", size=(INPpct, 1)),
     sg.InputText("2",   key="-AFFO_BASE_TERMINAL-",  size=(INPpct, 1)),
     sg.InputText("2.5", key="-AFFO_BEST_TERMINAL-",  size=(INPpct, 1))],
    [sg.HorizontalSeparator()],
    col_header(),
    result_row("Worst:", "-AFFO_WORST_PRICE-", "-AFFO_WORST_MOS-", "-AFFO_WORST_UPSIDE-"),
    result_row("Base:",  "-AFFO_BASE_PRICE-",  "-AFFO_BASE_MOS-",  "-AFFO_BASE_UPSIDE-"),
    result_row("Best:",  "-AFFO_BEST_PRICE-",  "-AFFO_BEST_MOS-",  "-AFFO_BEST_UPSIDE-"),
]

# =NAV=
_nav_left = [
    [sg.Text("Inputs", font=("Helvetica", 9, "bold"))],
    [sg.Text("Gross Asset Value (M):", size=(20, 1)), sg.InputText("", key="-GAV-",       size=(INP, 1))],
    [sg.Text("Total Debt (M):",        size=(20, 1)), sg.InputText("", key="-NAV_DEBT-",  size=(INP, 1))],
    [sg.Text("Other Liabilities (M):", size=(20, 1)), sg.InputText("0", key="-NAV_OTHER-", size=(INP, 1))],
    [sg.Text("NOI (M):",               size=(20, 1)), sg.InputText("", key="-NOI-",       size=(INP, 1))],
    [sg.HorizontalSeparator()],
    [sg.Text("NAV / Share:",      size=(16, 1)), sg.Text("—", key="-NAV_PRICE-",    size=(10, 1))],
    [sg.Text("Prem / Disc:",      size=(16, 1)), sg.Text("—", key="-NAV_PREMIUM-",  size=(10, 1))],
    [sg.Text("Implied Cap Rate:", size=(16, 1)), sg.Text("—", key="-NAV_CAP_RATE-", size=(10, 1))],
    [sg.HorizontalSeparator()],
    [sg.Text("GAV Sensitivity", font=("Helvetica", 10, "bold"))],
    [sg.Text("GAV ±%",    size=(10, 1), font=("Helvetica", 9, "bold")),
     sg.Text("NAV/Share", size=(10, 1), font=("Helvetica", 9, "bold")),
     sg.Text("vs Market", size=(10, 1), font=("Helvetica", 9, "bold"))],
    [sg.Text("GAV -20%", size=(10,1)), sg.Text("—", key="-NAV_S1-", size=(10,1)), sg.Text("—", key="-NAV_S1U-", size=(10,1))],
    [sg.Text("GAV -10%", size=(10,1)), sg.Text("—", key="-NAV_S2-", size=(10,1)), sg.Text("—", key="-NAV_S2U-", size=(10,1))],
    [sg.Text("GAV  0%",  size=(10,1)), sg.Text("—", key="-NAV_S3-", size=(10,1)), sg.Text("—", key="-NAV_S3U-", size=(10,1))],
    [sg.Text("GAV +10%", size=(10,1)), sg.Text("—", key="-NAV_S4-", size=(10,1)), sg.Text("—", key="-NAV_S4U-", size=(10,1))],
    [sg.Text("GAV +20%", size=(10,1)), sg.Text("—", key="-NAV_S5-", size=(10,1)), sg.Text("—", key="-NAV_S5U-", size=(10,1))],
]

_nav_right = [
    [sg.Text("Cap Rate Sensitivity", font=("Helvetica", 10, "bold"))],
    [sg.Text("Cap Rate",  size=(10, 1), font=("Helvetica", 9, "bold")),
     sg.Text("NAV/Share", size=(10, 1), font=("Helvetica", 9, "bold")),
     sg.Text("vs Market", size=(10, 1), font=("Helvetica", 9, "bold"))],
    [sg.Text("3.5%", size=(10,1)), sg.Text("—", key="-CAP_S1-", size=(10,1)), sg.Text("—", key="-CAP_S1U-", size=(10,1))],
    [sg.Text("4.0%", size=(10,1)), sg.Text("—", key="-CAP_S2-", size=(10,1)), sg.Text("—", key="-CAP_S2U-", size=(10,1))],
    [sg.Text("4.5%", size=(10,1)), sg.Text("—", key="-CAP_S3-", size=(10,1)), sg.Text("—", key="-CAP_S3U-", size=(10,1))],
    [sg.Text("5.0%", size=(10,1)), sg.Text("—", key="-CAP_S4-", size=(10,1)), sg.Text("—", key="-CAP_S4U-", size=(10,1))],
    [sg.Text("5.5%", size=(10,1)), sg.Text("—", key="-CAP_S5-", size=(10,1)), sg.Text("—", key="-CAP_S5U-", size=(10,1))],
    [sg.Text("6.0%", size=(10,1)), sg.Text("—", key="-CAP_S6-", size=(10,1)), sg.Text("—", key="-CAP_S6U-", size=(10,1))],
    [sg.Text("6.5%", size=(10,1)), sg.Text("—", key="-CAP_S7-", size=(10,1)), sg.Text("—", key="-CAP_S7U-", size=(10,1))],
    [sg.Text("Requires NOI input", font=("Helvetica", 8), text_color="#888888")],
]

nav_col = [
    [sg.Text("3 — Net Asset Value (NAV)", font=("Helvetica", 11, "bold"))],
    [
        sg.Column(_nav_left,  vertical_alignment="top"),
        sg.VerticalSeparator(),
        sg.Column(_nav_right, vertical_alignment="top", pad=((10, 0), 0)),
    ],
]

# =Summary
_SW = 12
_ML = 10


def sc_header_row():
    return [
        sg.Text("",      size=(_ML, 1)),
        sg.Text("Worst", size=(_SW, 1), font=("Helvetica", 9, "bold"), text_color="#C0392B"),
        sg.Text("Base",  size=(_SW, 1), font=("Helvetica", 9, "bold"), text_color="#7F8C8D"),
        sg.Text("Best",  size=(_SW, 1), font=("Helvetica", 9, "bold"), text_color="#27AE60"),
    ]


def model_price_row(label, kw, kb, kbest):
    return [
        sg.Text(label, size=(_ML, 1), font=("Helvetica", 9, "bold")),
        sg.Text("—", key=kw,    size=(_SW, 1)),
        sg.Text("—", key=kb,    size=(_SW, 1)),
        sg.Text("—", key=kbest, size=(_SW, 1)),
    ]


def model_upside_row(kw, kb, kbest):
    return [
        sg.Text("upside:", size=(_ML, 1), font=("Helvetica", 8), text_color="#888888"),
        sg.Text("—", key=kw,    size=(_SW, 1)),
        sg.Text("—", key=kb,    size=(_SW, 1)),
        sg.Text("—", key=kbest, size=(_SW, 1)),
    ]


summary_row_layout = [
    [sg.Text("Summary", font=("Helvetica", 11, "bold"))],
    [sg.Text("Weights (%):", size=(_ML, 1), font=("Helvetica", 9, "bold")),
     sg.Text("DDM",  size=(6, 1), font=("Helvetica", 8)),
     sg.InputText("33", key="-W_DDM-",  size=(5, 1)),
     sg.Text("AFFO", size=(6, 1), font=("Helvetica", 8)),
     sg.InputText("34", key="-W_AFFO-", size=(5, 1)),
     sg.Text("NAV",  size=(5, 1), font=("Helvetica", 8)),
     sg.InputText("33", key="-W_NAV-",  size=(5, 1))],
    sc_header_row(),
    model_price_row("DDM:",      "-SUM_WORST_DDM-",  "-SUM_BASE_DDM-",  "-SUM_BEST_DDM-"),
    model_upside_row("-SUM_WORST_DDM_U-",  "-SUM_BASE_DDM_U-",  "-SUM_BEST_DDM_U-"),
    model_price_row("AFFO DCF:", "-SUM_WORST_AFFO-", "-SUM_BASE_AFFO-", "-SUM_BEST_AFFO-"),
    model_upside_row("-SUM_WORST_AFFO_U-", "-SUM_BASE_AFFO_U-", "-SUM_BEST_AFFO_U-"),
    model_price_row("NAV:",      "-SUM_WORST_NAV-",  "-SUM_BASE_NAV-",  "-SUM_BEST_NAV-"),
    model_upside_row("-SUM_WORST_NAV_U-",  "-SUM_BASE_NAV_U-",  "-SUM_BEST_NAV_U-"),
    [sg.HorizontalSeparator()],
    model_price_row("Wtd Avg:",  "-SUM_WORST_WAVG-", "-SUM_BASE_WAVG-", "-SUM_BEST_WAVG-"),
    model_upside_row("-SUM_WORST_WAVG_U-", "-SUM_BASE_WAVG_U-", "-SUM_BEST_WAVG_U-"),
]

# =Actions
action_col = [
    [sg.Text("Run", font=("Helvetica", 11, "bold"))],
    [sg.Button("Calculate", button_color=("white", "#27AE60"))],
    [sg.Button("Save")],
    [sg.Button("Reset",      button_color=("white", "#999999"))],
]

# =Saved Analyses=
saved_col = [
    [sg.Text("Saved Analyses", font=("Helvetica", 11, "bold"))],
    [sg.Input("Search...", key="-SEARCH-", enable_events=True, expand_x=True, text_color="grey")],
    [sg.Table(
        values=[],
        headings=_TABLE_HEADINGS,
        key="-ANALYSIS_TABLE-",
        auto_size_columns=False,
        col_widths=[30, 14],
        justification="left",
        num_rows=12,
        enable_events=True,
        enable_click_events=True,
        expand_x=True,
    )],
    [
        sg.Button("Load Selected",   disabled=True, key="-LOAD_SELECTED-"),
        sg.Button("Delete Selected", button_color=("white", "#C0392B"),
                  disabled=True, key="-DELETE_SELECTED-"),
        sg.Button("Reload DB"),
    ],
    [
        sg.Button("Open File", disabled=True, key="-OPEN_FILE-"),
        sg.Button("Open Folder", key="-OPEN_DIR-"),
    ],
]

layout = [
    [sg.Column(shared_top, vertical_alignment="top")],
    [sg.HorizontalSeparator()],
    [
        sg.Column(ddm_col,  vertical_alignment="top"),
        sg.VerticalSeparator(),
        sg.Column(affo_col, vertical_alignment="top", pad=((12, 12), 0)),
        sg.VerticalSeparator(),
        sg.Column(nav_col,  vertical_alignment="top", pad=((12, 0), 0)),
    ],
    [sg.HorizontalSeparator()],
    [
        sg.Column(summary_row_layout, vertical_alignment="top"),
        sg.VerticalSeparator(),
        sg.Column(notes_col,          vertical_alignment="top", pad=((12, 12), 0)),
        sg.VerticalSeparator(),
        sg.Column(action_col,         vertical_alignment="top", pad=((12, 12), 0)),
        sg.VerticalSeparator(),
        sg.Column(saved_col,          vertical_alignment="top", pad=((12, 0), 0)),
    ],
]

window = sg.Window("REIT Valuation", layout, size=(1300, 805), resizable=True, finalize=True)

def _search_focus_in(event):
    if window["-SEARCH-"].get() == _SEARCH_PLACEHOLDER:
        window["-SEARCH-"].update("", text_color=sg.theme_text_color())

def _search_focus_out(event):
    if window["-SEARCH-"].get() == "":
        window["-SEARCH-"].update(_SEARCH_PLACEHOLDER, text_color="grey")

window["-SEARCH-"].Widget.bind("<FocusIn>", _search_focus_in)
window["-SEARCH-"].Widget.bind("<FocusOut>", _search_focus_out)


# event loop=

def refresh_saved_list():
    """Reload DB, rebuild sorted table rows, sync button-enabled state.
    Returns (records, displayed_records) where displayed_records is the
    sort-aligned record list for index-based lookups from the table."""
    records, _, skipped = load_database()
    if skipped:
        sg.popup_error(
            "The following files could not be loaded and were skipped:\n\n"
            + "\n".join(f"  • {f}" for f in skipped),
            title="Database Load Warning",
        )
    displayed, rows = _build_sorted_rows(records, sort_state, window["-SEARCH-"].get())
    window["-ANALYSIS_TABLE-"].update(values=rows)
    _update_sort_indicators(window, sort_state)
    has_items = bool(displayed)
    window["-LOAD_SELECTED-"].update(disabled=not has_items)
    window["-DELETE_SELECTED-"].update(disabled=not has_items)
    window["-OPEN_FILE-"].update(disabled=not has_items)
    return records, displayed


sort_state = {"col": 1, "dir": "desc"}
loaded_database, displayed_records = refresh_saved_list()


def open_path(path):
    """Open a file or directory in the OS default app."""
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# =Event loop=

while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED:
        break

    if isinstance(event, tuple) and len(event) == 3 \
            and event[0] == "-ANALYSIS_TABLE-" and event[1] == "+CLICKED+":
        row, col = event[2] if isinstance(event[2], tuple) else (None, None)
        if row == -1 and isinstance(col, int) and 0 <= col < len(_TABLE_HEADINGS):
            if col == sort_state["col"]:
                sort_state["dir"] = "asc" if sort_state["dir"] == "desc" else "desc"
            else:
                sort_state["col"] = col
                sort_state["dir"] = "desc" if col == 1 else "asc"
            displayed_records, rows = _build_sorted_rows(loaded_database, sort_state, values.get("-SEARCH-", ""))
            window["-ANALYSIS_TABLE-"].update(values=rows)
            _update_sort_indicators(window, sort_state)
        continue

    # =Search filter=
    if event == "-SEARCH-":
        displayed_records, rows = _build_sorted_rows(loaded_database, sort_state, values["-SEARCH-"])
        window["-ANALYSIS_TABLE-"].update(values=rows)
        has_items = bool(displayed_records)
        window["-LOAD_SELECTED-"].update(disabled=not has_items)
        window["-DELETE_SELECTED-"].update(disabled=not has_items)
        window["-OPEN_FILE-"].update(disabled=not has_items)

    # =Reset
    if event == "Reset":
        for key, val in DEFAULTS.items():
            window[key].update(val)
        for key in RESULT_KEYS:
            window[key].update("—")
            try:
                window[key].update(text_color=sg.theme_text_color())
            except Exception:
                pass

    # =Calculate=
    elif event == "Calculate":
        try:
            inp = Inputs.from_window(values)
        except ValueError as e:
            sg.popup_error(f"Input error: {e}")
            continue

        try:
            # DDM
            ddm_prices = {}
            for sc in ("worst", "base", "best"):
                g1, g2, r = inp.ddm_scenario(sc)
                price = ddm_two_stage(inp.dps, g1, inp.ddm_stage1_years, g2, r)
                ddm_prices[sc] = price
                render_scenario(window, f"DDM_{sc.upper()}", price, inp.market_price)

            # Dividend coverage
            affo_ps = inp.affo / inp.shares
            cov = affo_ps / inp.dps
            window["-DDM_COV-"].update(
                f"{cov:.2f}x", text_color="green" if cov >= 1.0 else "red")

            # AFFO DCF
            affo_prices = {}
            for sc in ("worst", "base", "best"):
                g, w, t = inp.affo_scenario(sc)
                price = affo_dcf_calculate(
                    inp.affo, inp.affo_debt, inp.affo_cash, inp.shares,
                    inp.affo_years, g, w, t)
                affo_prices[sc] = price
                render_scenario(window, f"AFFO_{sc.upper()}", price, inp.market_price)

            # NAV:
            nav_price = nav_calculate(inp.gav, inp.nav_debt, inp.nav_other, inp.shares)
            window["-NAV_PRICE-"].update(f"${nav_price:.2f}")

            # Cap rate sensitivity --if NOI provided
            if inp.noi is not None:
                cap_rate = inp.noi / inp.gav * 100
                window["-NAV_CAP_RATE-"].update(f"{cap_rate:.2f}%")
                for cr, (nk, uk) in zip(CAP_RATE_STEPS, CAP_SENS_KEYS):
                    nav_cr = nav_from_cap_rate(
                        inp.noi, cr, inp.nav_debt, inp.nav_other, inp.shares)
                    window[nk].update(f"${nav_cr:.2f}")
                    if inp.market_price:
                        u = upside_pct(nav_cr, inp.market_price)
                        window[uk].update(f"{u:+.1f}%",
                                          text_color="green" if u > 0 else "red")
                    else:
                        window[uk].update("—", text_color=sg.theme_text_color())
            else:
                window["-NAV_CAP_RATE-"].update("—")
                for _, (nk, uk) in zip(CAP_RATE_STEPS, CAP_SENS_KEYS):
                    window[nk].update("—")
                    window[uk].update("—", text_color=sg.theme_text_color())

            # NAV vs market
            _, navs = nav_sensitivity(inp.gav, inp.nav_debt, inp.nav_other, inp.shares)
            if inp.market_price:
                premium = (inp.market_price - nav_price) / nav_price * 100
                window["-NAV_PREMIUM-"].update(
                    f"{premium:+.1f}%", text_color="red" if premium > 0 else "green")
                for (nk, uk), nav_val in zip(NAV_SENS_KEYS, navs):
                    u = upside_pct(nav_val, inp.market_price)
                    window[nk].update(f"${nav_val:.2f}")
                    window[uk].update(f"{u:+.1f}%",
                                      text_color="green" if u > 0 else "red")
            else:
                window["-NAV_PREMIUM-"].update("—", text_color=sg.theme_text_color())
                for (nk, uk), nav_val in zip(NAV_SENS_KEYS, navs):
                    window[nk].update(f"${nav_val:.2f}")
                    window[uk].update("—", text_color=sg.theme_text_color())

            # Summary + wght avg
            renorm_warned = False
            for sc in ("worst", "base", "best"):
                lbl = sc.upper()
                ddm_p, affo_p = ddm_prices[sc], affo_prices[sc]
                wavg, renormalized = weighted_avg(
                    ddm_p, affo_p, nav_price, inp.w_ddm, inp.w_affo, inp.w_nav)
                if renormalized and not renorm_warned:
                    set_status(window,
                        "Weighted avg renormalized — one or more models returned no result",
                        "warn")
                    renorm_warned = True
                render_sum_cell(window, f"-SUM_{lbl}_DDM-",  f"-SUM_{lbl}_DDM_U-",
                                ddm_p, inp.market_price)
                render_sum_cell(window, f"-SUM_{lbl}_AFFO-", f"-SUM_{lbl}_AFFO_U-",
                                affo_p, inp.market_price)
                render_sum_cell(window, f"-SUM_{lbl}_NAV-",  f"-SUM_{lbl}_NAV_U-",
                                nav_price, inp.market_price)
                render_sum_cell(window, f"-SUM_{lbl}_WAVG-", f"-SUM_{lbl}_WAVG_U-",
                                wavg, inp.market_price)

        except ValueError as e:
            sg.popup_error(f"Input error: {e}")

    # =Save
    elif event == "Save":
        name = values["-ANALYSIS_NAME-"].strip()
        if not name:
            set_status(window, "Please enter an analysis name", "warn")
        else:
            target_name = name
            if os.path.exists(analysis_path(name)):
                new_name = sg.popup_get_text(
                    f"'{name}' already exists. Enter a new name:", title="Rename")
                if not new_name or new_name == name:
                    target_name = None
                else:
                    target_name = new_name
                    window["-ANALYSIS_NAME-"].update(new_name)
            if target_name:
                record = {k: (values.get(f"-{k.upper()}-", "") or "")
                          for k in PERSISTED_FIELDS}
                record["notes"] = record["notes"].strip()
                try:
                    save_analysis(target_name, record)
                    set_status(window, f"Saved '{target_name}'", "success")
                    loaded_database, displayed_records = refresh_saved_list()
                except Exception as e:
                    sg.popup_error(f"Error saving analysis: {e}")

    # =Reload
    elif event == "Reload DB":
        loaded_database, displayed_records = refresh_saved_list()
        set_status(window, f"Reloaded ({len(displayed_records)} analyses)", "info")

    # =Table row selection=
    elif event == "-ANALYSIS_TABLE-":
        selected = bool(values.get("-ANALYSIS_TABLE-"))
        window["-LOAD_SELECTED-"].update(disabled=not selected)
        window["-DELETE_SELECTED-"].update(disabled=not selected)
        window["-OPEN_FILE-"].update(disabled=not selected)

    # =Load selected=
    elif event == "-LOAD_SELECTED-":
        sel = values.get("-ANALYSIS_TABLE-", [])
        if sel and 0 <= sel[0] < len(displayed_records):
            a = displayed_records[sel[0]]
            window["-ANALYSIS_NAME-"].update(a.get("analysis_name", ""))
            for k in PERSISTED_FIELDS:
                window[f"-{k.upper()}-"].update(a.get(k, ""))
            set_status(window, f"Loaded '{a.get('analysis_name', '')}'", "success")

    # =Delete selected=
    elif event == "-DELETE_SELECTED-":
        sel = values.get("-ANALYSIS_TABLE-", [])
        if sel and 0 <= sel[0] < len(displayed_records):
            sel_name = displayed_records[sel[0]].get("analysis_name", "")
            confirm = sg.popup_yes_no(
                f"Delete analysis '{sel_name}'?", title="Confirm Delete")
            if confirm == "Yes":
                try:
                    if delete_analysis(sel_name):
                        loaded_database, displayed_records = refresh_saved_list()
                        set_status(window, f"Deleted '{sel_name}'", "success")
                    else:
                        sg.popup_error(f"Analysis '{sel_name}' not found.")
                except Exception as e:
                    sg.popup_error(f"Error deleting analysis: {e}")

    # =Open File=
    elif event == "-OPEN_FILE-":
        sel = values.get("-ANALYSIS_TABLE-", [])
        if sel and 0 <= sel[0] < len(displayed_records):
            sel_name = displayed_records[sel[0]].get("analysis_name", "")
            path = analysis_path(sel_name)
            if os.path.exists(path):
                try:
                    open_path(path)
                except Exception as e:
                    sg.popup_error(f"Could not open file: {e}")
            else:
                sg.popup_error(f"File not found: {path}")

    # =Open Folder=
    elif event == "-OPEN_DIR-":
        try:
            open_path(DB_DIR)
        except Exception as e:
            sg.popup_error(f"Could not open folder: {e}")

window.close()
