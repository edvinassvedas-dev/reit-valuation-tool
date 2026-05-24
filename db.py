"""JSON-file persistence for analyses. No GUI dependency.

Schema definitions (field list, metadata) live in schema.py; this module
only owns reading, writing, and deleting files.
"""

import glob
import json
import os
from datetime import date

from schema import PERSISTED_FIELDS, _META


DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reit_db")
os.makedirs(DB_DIR, exist_ok=True)


def analysis_path(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
    safe = os.path.basename(safe)
    return os.path.join(DB_DIR, f"{safe}.json")


def load_database():
    files = sorted(glob.glob(os.path.join(DB_DIR, "*.json")))
    database, skipped = [], []
    for filepath in files:
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            database.append({k: v for k, v in raw.items() if not k.startswith("_")})
        except Exception as e:
            print(f"[load_database] Skipping '{filepath}': {e}", flush=True)
            skipped.append(os.path.basename(filepath))
    names = [a.get("analysis_name", "N/A") for a in database]
    return database, names, skipped


def save_analysis(analysis_name: str, record: dict) -> None:
    full = {"analysis_name": analysis_name}
    for k in PERSISTED_FIELDS:
        full[k] = record.get(k, "")
    full["analysis_date"] = date.today().strftime("%Y-%m-%d")
    full.update(_META)
    with open(analysis_path(analysis_name), "w", encoding="utf-8") as fh:
        json.dump(full, fh, indent=2)


def delete_analysis(analysis_name: str) -> bool:
    path = analysis_path(analysis_name)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True
