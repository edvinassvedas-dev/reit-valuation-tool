"""Single source of truth for the input schema.

The Inputs dataclass declares every numeric field the app cares about, with
per-field metadata (default value, optional, integer). DEFAULTS, OPTIONAL,
INT_FIELDS, and PERSISTED_FIELDS are derived from fields(Inputs) so adding a
new field requires only one edit here.
"""

from dataclasses import dataclass, field, fields
from typing import Optional


def gui_key(field_name: str) -> str:
    return f"-{field_name.upper()}-"


# `default` is the initial string shown in the GUI widget.
# `optional=True` means an empty string parses to None.
# `int=True` means the value parses as int rather than float.
@dataclass
class Inputs:
    """Parsed snapshot of every numeric input."""
    shares:               float = field(metadata={"default": ""})
    market_price: Optional[float] = field(metadata={"default": "", "optional": True})
    dps:                  float = field(metadata={"default": ""})
    ddm_stage1_years:     int   = field(metadata={"default": "5",   "int": True})

    ddm_worst_growth:     float = field(metadata={"default": "2"})
    ddm_worst_terminal:   float = field(metadata={"default": "1.5"})
    ddm_worst_rate:       float = field(metadata={"default": "9"})
    ddm_base_growth:      float = field(metadata={"default": "4"})
    ddm_base_terminal:    float = field(metadata={"default": "2"})
    ddm_base_rate:        float = field(metadata={"default": "8"})
    ddm_best_growth:      float = field(metadata={"default": "6"})
    ddm_best_terminal:    float = field(metadata={"default": "2.5"})
    ddm_best_rate:        float = field(metadata={"default": "7"})

    affo:                 float = field(metadata={"default": ""})
    affo_debt:            float = field(metadata={"default": ""})
    affo_cash:            float = field(metadata={"default": ""})
    affo_years:           int   = field(metadata={"default": "10", "int": True})
    affo_worst_growth:    float = field(metadata={"default": "1"})
    affo_worst_wacc:      float = field(metadata={"default": "9"})
    affo_worst_terminal:  float = field(metadata={"default": "1.5"})
    affo_base_growth:     float = field(metadata={"default": "3"})
    affo_base_wacc:       float = field(metadata={"default": "8"})
    affo_base_terminal:   float = field(metadata={"default": "2"})
    affo_best_growth:     float = field(metadata={"default": "5"})
    affo_best_wacc:       float = field(metadata={"default": "7"})
    affo_best_terminal:   float = field(metadata={"default": "2.5"})

    gav:                  float = field(metadata={"default": ""})
    nav_debt:             float = field(metadata={"default": ""})
    nav_other:            float = field(metadata={"default": "0"})
    noi:        Optional[float] = field(metadata={"default": "", "optional": True})

    w_ddm:                float = field(metadata={"default": "33"})
    w_affo:               float = field(metadata={"default": "34"})
    w_nav:                float = field(metadata={"default": "33"})

    def ddm_scenario(self, sc):
        return (getattr(self, f"ddm_{sc}_growth") / 100,
                getattr(self, f"ddm_{sc}_terminal") / 100,
                getattr(self, f"ddm_{sc}_rate") / 100)

    def affo_scenario(self, sc):
        return (getattr(self, f"affo_{sc}_growth") / 100,
                getattr(self, f"affo_{sc}_wacc") / 100,
                getattr(self, f"affo_{sc}_terminal") / 100)

    @classmethod
    def from_window(cls, values):
        """Parse all widget values. Raises ValueError naming the bad field."""
        kwargs = {}
        for f in fields(cls):
            raw = (values.get(gui_key(f.name), "") or "").strip()
            optional = f.metadata.get("optional", False)
            is_int   = f.metadata.get("int", False)
            if not raw:
                if optional:
                    kwargs[f.name] = None
                    continue
                raise ValueError(f"{f.name} is required")
            try:
                kwargs[f.name] = int(float(raw)) if is_int else float(raw)
            except ValueError:
                raise ValueError(f"{f.name}: '{raw}' is not a number")
        return cls(**kwargs)


# Derived constants. Built once at import.

PERSISTED_FIELDS = [f.name for f in fields(Inputs)] + ["notes"]

# Default string values for every GUI widget, including non-Inputs fields.
DEFAULTS = {gui_key(f.name): f.metadata.get("default", "") for f in fields(Inputs)}
DEFAULTS["-ANALYSIS_NAME-"] = ""
DEFAULTS["-NOTES-"] = ""


# Documentation embedded into each saved JSON file.
_META = {
    "_meta": {
        "analysis_name":    "User-defined label for this analysis",
        "shares":           "Diluted shares outstanding in millions",
        "market_price":     "Current market price per share (optional)",
        "dps":              "Annual dividend per share in dollars",
        "ddm_stage1_years": "Years for DDM Stage 1 high-growth phase",
        "ddm_*_growth":     "Stage 1 dividend growth rate as a percentage",
        "ddm_*_terminal":   "Stage 2 perpetual growth rate (must be < discount rate)",
        "ddm_*_rate":       "Discount rate as a percentage",
        "affo":             "AFFO in millions",
        "affo_debt":        "Total debt in millions for AFFO DCF equity bridge",
        "affo_cash":        "Cash & equivalents in millions",
        "affo_years":       "Projection horizon for AFFO DCF",
        "affo_*_growth":    "AFFO growth rate per scenario as a percentage",
        "affo_*_wacc":      "WACC per scenario as a percentage (must exceed terminal)",
        "affo_*_terminal":  "AFFO terminal growth rate per scenario as a percentage",
        "gav":              "Gross Asset Value in millions",
        "nav_debt":         "Total debt for NAV calculation",
        "nav_other":        "Other liabilities (use 0 if none)",
        "noi":              "Net Operating Income (optional, enables cap rate sensitivity)",
        "w_ddm":            "Weight for DDM in weighted average (target sum = 100)",
        "w_affo":           "Weight for AFFO DCF",
        "w_nav":            "Weight for NAV",
        "notes":            "Free-text notes",
        "analysis_date":    "Save date in YYYY-MM-DD; set automatically",
    }
}
