"""
Storage layer for the LCN KPI dashboard.

Two backends, same interface (load() -> dict, save(dict)):
  * SheetsStore  — Google Sheet (durable; edits persist forever). Used when
                   `gcp_service_account` and `sheet_url` are present in st.secrets.
  * JSONStore    — local data.json fallback (no persistence on Streamlit Cloud).
                   Used automatically when secrets are not configured, so the
                   app still runs for local development / preview.

The Google Sheet is auto-bootstrapped on first load: missing worksheets are
created and empty ones are seeded from data.json, so you only need to create a
blank Sheet and share it with the service account.
"""
from __future__ import annotations

import json
import os
import copy

import streamlit as st

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
MONTHS = ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TIER_KEYS = ["tier1", "tier2", "tier3"]

# Worksheet name -> header row
SHEETS = {
    "scorecard": ["Metric", "Target 0-6 mo", "Target 6-12 mo", "Status", "Current / Notes", "Why it matters"],
    "pipeline": ["Client", "Project", "Stage", "Win Probability (%)", "Confidence", "Next Step"],
    "strategy": ["tier", "tier_label", "title", "heading", "points", "goal"],
    "h2": ["kpi", "type", "target"] + MONTHS,
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


# ---- dict <-> sheet-rows converters --------------------------------------- #
def _rows_scorecard(data):
    h = SHEETS["scorecard"]
    return [[r.get(c, "") for c in h] for r in data["scorecard"]]


def _parse_scorecard(records):
    out = []
    for r in records:
        out.append({c: (r.get(c) if r.get(c) is not None else "") for c in SHEETS["scorecard"]})
    return out


def _rows_pipeline(data):
    h = SHEETS["pipeline"]
    rows = []
    for r in data["pipeline"]:
        row = []
        for c in h:
            if c == "Win Probability (%)":
                row.append(_to_num(r.get(c)) or 0)
            else:
                row.append(r.get(c, ""))
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
    rows = []
    for k in TIER_KEYS:
        t = data["strategy"][k]
        rows.append([k, t["tier_label"], t["title"], t["heading"], t["points"], t["goal"]])
    return rows


def _parse_strategy(records, fallback):
    out = copy.deepcopy(fallback["strategy"])
    for r in records:
        k = r.get("tier")
        if k in TIER_KEYS:
            out[k] = {
                "tier_label": r.get("tier_label", "") or "",
                "title": r.get("title", "") or "",
                "heading": r.get("heading", "") or "",
                "points": r.get("points", "") or "",
                "goal": r.get("goal", "") or "",
            }
    return out


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

        # scorecard
        ws = self._ws("scorecard")
        vals = ws.get_all_values()
        if len(vals) < 2:
            self._write(ws, SHEETS["scorecard"], _rows_scorecard(seed))
            data["scorecard"] = seed["scorecard"]
        else:
            data["scorecard"] = _parse_scorecard(ws.get_all_records())

        # pipeline
        ws = self._ws("pipeline")
        vals = ws.get_all_values()
        if len(vals) < 2:
            self._write(ws, SHEETS["pipeline"], _rows_pipeline(seed))
            data["pipeline"] = seed["pipeline"]
        else:
            data["pipeline"] = _parse_pipeline(ws.get_all_records())

        # strategy
        ws = self._ws("strategy")
        vals = ws.get_all_values()
        if len(vals) < 2:
            self._write(ws, SHEETS["strategy"], _rows_strategy(seed))
            data["strategy"] = seed["strategy"]
        else:
            data["strategy"] = _parse_strategy(ws.get_all_records(), seed)

        # h2
        ws = self._ws("h2")
        vals = ws.get_all_values()
        if len(vals) < 2:
            self._write(ws, SHEETS["h2"], _rows_h2(seed))
            data["h2"] = seed["h2"]
        else:
            data["h2"] = _parse_h2(ws.get_all_records())

        return data

    def save(self, data: dict):
        self._write(self._ws("scorecard"), SHEETS["scorecard"], _rows_scorecard(data))
        self._write(self._ws("pipeline"), SHEETS["pipeline"], _rows_pipeline(data))
        self._write(self._ws("strategy"), SHEETS["strategy"], _rows_strategy(data))
        self._write(self._ws("h2"), SHEETS["h2"], _rows_h2(data))

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
