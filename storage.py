"""
Storage layer for the LCN KPI dashboard.

Two backends, same interface (load() -> dict, save(dict)):
  * SheetsStore  — Google Sheet (durable; edits persist forever). Used when
                   `gcp_service_account` and `sheet_url` are present in st.secrets.
  * JSONStore    — local data.json fallback (no persistence on Streamlit Cloud).

The Google Sheet is auto-bootstrapped on first load: missing worksheets are
created and seeded from data.json. Worksheets whose header row no longer matches
the expected columns are rebuilt from the seed, so schema changes apply cleanly.
"""
from __future__ import annotations

import json
import os
import copy

import streamlit as st

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
MONTHS = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEK_COLS = ["W1", "W2", "W3", "W4", "W5"]
TIER_KEYS = ["tier1", "tier2", "tier3"]

# Worksheet name -> header row
SHEETS = {
    "scorecard": ["Metric", "Expected", "Agg"],
    "scorecard_weeks": ["Month", "Metric"] + WEEK_COLS,
    "pipeline": ["Client", "Project", "Stage", "Win Probability (%)", "Confidence", "Next Step"],
    "strategy": ["Goal", "Expected", "Current"],
    "h2": ["kpi", "type", "target"] + MONTHS,
    "analysts": ["Analyst"],
    "tasks": ["Task", "desc"],
    "analyst_tasks": ["Month", "Analyst", "Task", "Action", "Outcome", "Why"],
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _seed() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _to_num(v):
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return None


def _needs_seed(existing_values, expected_header) -> bool:
    """True if the worksheet is empty or its header row doesn't match."""
    if not existing_values:
        return True
    header = [str(c).strip() for c in existing_values[0]]
    return header[: len(expected_header)] != expected_header or len(existing_values) < 2


# ---- dict <-> sheet-rows converters --------------------------------------- #
def _rows_numbers(rows, label):
    return [[r.get(label, ""), _blank(r.get("Expected")), _blank(r.get("Current"))] for r in rows]


def _parse_numbers(records, label):
    out = []
    for r in records:
        out.append({
            label: r.get(label, "") or "",
            "Expected": _to_num(r.get("Expected")),
            "Current": _to_num(r.get("Current")) or 0,
        })
    return out


def _blank(v):
    return "" if v is None else v


def _rows_scorecard(data):
    return [[m.get("Metric", ""), _blank(m.get("Expected")), m.get("Agg", "sum")]
            for m in data["scorecard"]]


def _parse_scorecard(records):
    out = []
    for r in records:
        out.append({
            "Metric": r.get("Metric", "") or "",
            "Expected": _to_num(r.get("Expected")),
            "Agg": (r.get("Agg") or "sum"),
        })
    return out


def _rows_scorecard_weeks(data):
    rows = []
    for r in data.get("scorecard_weeks", []):
        rows.append([r.get("Month", ""), r.get("Metric", "")]
                    + [_blank(r.get(w)) for w in WEEK_COLS])
    return rows


def _parse_scorecard_weeks(records):
    out = []
    for r in records:
        row = {"Month": r.get("Month", "") or "", "Metric": r.get("Metric", "") or ""}
        for w in WEEK_COLS:
            row[w] = _to_num(r.get(w))
        out.append(row)
    return out


def _rows_pipeline(data):
    h = SHEETS["pipeline"]
    rows = []
    for r in data["pipeline"]:
        row = []
        for c in h:
            row.append((_to_num(r.get(c)) or 0) if c == "Win Probability (%)" else r.get(c, ""))
        rows.append(row)
    return rows


def _parse_pipeline(records):
    out = []
    for r in records:
        out.append({
            "Client": r.get("Client", "") or "",
            "Project": r.get("Project", "") or "",
            "Stage": r.get("Stage", "") or "Open",
            "Win Probability (%)": _to_num(r.get("Win Probability (%)")) or 0,
            "Confidence": r.get("Confidence", "") or "Medium",
            "Next Step": r.get("Next Step", "") or "",
        })
    return out


def _rows_strategy(data):
    return _rows_numbers(data["strategy"], "Goal")


def _parse_strategy(records, fallback):
    return _parse_numbers(records, "Goal")


def _rows_h2(data):
    rows = []
    for r in data["h2"]:
        target = r.get("target")
        months = r.get("months", {}) or {}
        row = [r["kpi"], r.get("type", "sum"), "" if target is None else target]
        row += ["" if months.get(m) is None else months.get(m) for m in MONTHS]
        rows.append(row)
    return rows


def _parse_h2(records):
    out = []
    for r in records:
        out.append({
            "kpi": r.get("kpi", "") or "",
            "type": r.get("type", "sum") or "sum",
            "target": _to_num(r.get("target")),
            "months": {m: _to_num(r.get(m)) for m in MONTHS},
        })
    return out


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().lower() in ("true", "1", "yes", "y", "x", "✓", "checked")


def _rows_analysts(data):
    return [[a.get("Analyst", "")] for a in data.get("analysts", [])]


def _parse_analysts(records):
    return [{"Analyst": (r.get("Analyst") or "").strip()}
            for r in records if (r.get("Analyst") or "").strip()]


def _rows_tasks(data):
    return [[t.get("Task", ""), t.get("desc", "")] for t in data.get("tasks", [])]


def _parse_tasks(records):
    return [{"Task": (r.get("Task") or "").strip(), "desc": (r.get("desc") or "")}
            for r in records if (r.get("Task") or "").strip()]


def _rows_analyst_tasks(data):
    return [[r.get("Month", ""), r.get("Analyst", ""), r.get("Task", ""),
             r.get("Action", "") or "", bool(r.get("Outcome")), r.get("Why", "") or ""]
            for r in data.get("analyst_tasks", [])]


def _parse_analyst_tasks(records):
    return [{"Month": r.get("Month", "") or "", "Analyst": r.get("Analyst", "") or "",
             "Task": r.get("Task", "") or "", "Action": (r.get("Action") or ""),
             "Outcome": _to_bool(r.get("Outcome")), "Why": (r.get("Why") or "")}
            for r in records]


PARSERS = {
    "scorecard": lambda recs, seed: _parse_scorecard(recs),
    "scorecard_weeks": lambda recs, seed: _parse_scorecard_weeks(recs),
    "pipeline": lambda recs, seed: _parse_pipeline(recs),
    "strategy": lambda recs, seed: _parse_strategy(recs, seed),
    "h2": lambda recs, seed: _parse_h2(recs),
    "analysts": lambda recs, seed: _parse_analysts(recs),
    "tasks": lambda recs, seed: _parse_tasks(recs),
    "analyst_tasks": lambda recs, seed: _parse_analyst_tasks(recs),
}
ROW_BUILDERS = {
    "scorecard": _rows_scorecard,
    "scorecard_weeks": _rows_scorecard_weeks,
    "pipeline": _rows_pipeline,
    "strategy": _rows_strategy,
    "h2": _rows_h2,
    "analysts": _rows_analysts,
    "tasks": _rows_tasks,
    "analyst_tasks": _rows_analyst_tasks,
}


# --------------------------------------------------------------------------- #
# JSON backend
# --------------------------------------------------------------------------- #
class JSONStore:
    name = "Local file (data.json)"
    persistent = False

    def load(self) -> dict:
        return _seed()

    def save(self, data: dict):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Google Sheets backend
# --------------------------------------------------------------------------- #
class SheetsStore:
    name = "Google Sheets"
    persistent = True

    def __init__(self, spreadsheet):
        self.sh = spreadsheet

    def _ws(self, name):
        import gspread
        try:
            return self.sh.worksheet(name)
        except gspread.WorksheetNotFound:
            return self.sh.add_worksheet(title=name, rows=200, cols=20)

    def load(self) -> dict:
        seed = _seed()
        data = {}
        for name, header in SHEETS.items():
            if name not in ROW_BUILDERS or name not in PARSERS:
                data[name] = seed.get(name, [])
                continue
            ws = self._ws(name)
            try:
                values = ws.get_all_values()
                if _needs_seed(values, header):
                    self._write(ws, header, ROW_BUILDERS[name](seed))
                    data[name] = seed.get(name, [])
                else:
                    data[name] = PARSERS[name](ws.get_all_records(), seed)
            except Exception:
                # Self-heal: if a worksheet is malformed or from an older schema,
                # rebuild it from the packaged seed rather than crashing the app.
                try:
                    self._write(ws, header, ROW_BUILDERS[name](seed))
                except Exception:
                    pass
                data[name] = seed.get(name, [])
        return data

    def save(self, data: dict):
        for name, header in SHEETS.items():
            self._write(self._ws(name), header, ROW_BUILDERS[name](data))

    @staticmethod
    def _write(ws, headers, rows):
        ws.clear()
        ws.update([headers] + rows, value_input_option="USER_ENTERED")


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def _secrets_configured() -> bool:
    try:
        return "gcp_service_account" in st.secrets and "sheet_url" in st.secrets
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _open_spreadsheet():
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    return gc.open_by_url(st.secrets["sheet_url"])


def get_store():
    """Return (store, error). Falls back to JSONStore if Sheets is unavailable."""
    if _secrets_configured():
        try:
            return SheetsStore(_open_spreadsheet()), None
        except Exception as e:  # noqa: BLE001
            return JSONStore(), str(e)
    return JSONStore(), None
