import json
import os
from datetime import date
from pathlib import Path

from schema import PERSISTED_FIELDS, _META


DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reit_db")
os.makedirs(DB_DIR, exist_ok=True)

_NOISE_PARTS = {"__pycache__", "node_modules", ".venv"}


def analysis_path(name: str, directory: str = None) -> str:
    safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in name)
    safe = os.path.basename(safe)
    return os.path.join(directory or DB_DIR, f"{safe}.json")


def _discover_jsons(root: Path) -> list:
    return sorted(
        p for p in root.rglob("*.json")
        if not any(part.startswith(".") or part in _NOISE_PARTS
                   for part in p.relative_to(root).parts)
    )


def load_database():
    root = Path(DB_DIR)
    database, skipped = [], []
    for p in _discover_jsons(root):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            rec = {k: v for k, v in raw.items() if not k.startswith("_")}
            rec["_path"] = str(p)
            loc = p.relative_to(root).parent
            rec["_location"] = "/" if not loc.parts else f"/{loc}/"
            database.append(rec)
        except Exception as e:
            print(f"[load_database] Skipping '{p}': {e}", flush=True)
            skipped.append(p.name)
    names = [a.get("analysis_name", "N/A") for a in database]
    return database, names, skipped


def save_analysis(analysis_name: str, record: dict, directory: str = None) -> None:
    full = {"analysis_name": analysis_name}
    for k in PERSISTED_FIELDS:
        full[k] = record.get(k, "")
    full["analysis_date"] = date.today().strftime("%Y-%m-%d")
    full.update(_META)
    with open(analysis_path(analysis_name, directory), "w", encoding="utf-8") as fh:
        json.dump(full, fh, indent=2)


def delete_analysis(path: str) -> bool:
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True
