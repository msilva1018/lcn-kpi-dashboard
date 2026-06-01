"""
LCN Consulting — 2026 KPI Dashboard
Streamlit app backed by a Google Sheet (durable). Edit values in the web UI;
changes persist to the Sheet and are always up to date on every visit.
Falls back to local data.json when Google Sheets secrets aren't configured.
"""
import json
import hashlib
import copy
from datetime import datetime

import pandas as pd
import streamlit as st

from storage import get_store, MONTHS, TIER_KEYS, _seed

# --------------------------------------------------------------------------- #
# Config & constants
# --------------------------------------------------------------------------- #
STATUS_OPTIONS = ["On track", "At risk", "Behind", "Achieved"]
SCORECARD_COLS = ["Metric", "Expected 0-6 mo", "Expected 6-12 mo", "Where we are now", "Status"]
STATUS_COLORS = {
    "On track": ("#E6F4EC", "#1A7F4B"),
    "At risk": ("#FBF1DD", "#B7791F"),
    "Behind": ("#FBE7E5", "#C0392B"),
    "Achieved": ("#E7EEF9", "#0A4595"),
}


def status_badge(status):
    bg, fg = STATUS_COLORS.get(status, ("#EEF1F5", "#4F6B8A"))
    return (f'<span style="background:{bg};color:{fg};padding:2px 9px;border-radius:999px;'
            f'font-size:.72rem;font-weight:700;white-space:nowrap;">{status}</span>')
STAGE_OPTIONS = ["Open", "Qualified", "Proposal", "Won", "Lost"]
CONFIDENCE_OPTIONS = ["High-confidence", "Medium", "At-risk"]

st.set_page_config(
    page_title="LCN Consulting · 2026 KPI Dashboard",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1300px;}
      #MainMenu, footer {visibility: hidden;}
      .lcn-band {background: linear-gradient(90deg, #0B2D5C 0%, #0A4595 100%);
          color:#fff; padding:22px 28px; border-radius:12px; margin-bottom:6px;}
      .lcn-band h1 {margin:0; font-size:1.7rem; font-weight:800; letter-spacing:.2px;}
      .lcn-band p  {margin:4px 0 0; color:#C9D8EF; font-size:.95rem;}
      .lcn-mark {float:right; text-align:right; font-weight:800; font-size:1.05rem; line-height:1.1;}
      .lcn-mark span {font-weight:400; color:#C9D8EF; font-size:.72rem; display:block;}
      .lcn-foot {color:#8A99B5; font-size:.78rem; text-align:center; margin-top:26px;
                 border-top:1px solid #E6EAF2; padding-top:12px;}
      .tier-card {border-radius:10px; padding:16px 18px; color:#fff; margin-bottom:10px;}
      .tier-sub {font-size:.72rem; letter-spacing:1.4px; opacity:.85; font-weight:700;}
      .tier-title {font-size:1.25rem; font-weight:800; margin-top:2px;}
      .goal-box {background:#F0F4FA; border:1px solid #D5E0F0; border-radius:8px;
                 padding:10px 12px; font-size:.84rem; color:#0B2D5C; margin-top:8px;}
      .goal-box b {color:#0A4595;}
      div[data-testid="stMetric"] {background:#F4F6FA; border:1px solid #E6EAF2;
                 border-radius:10px; padding:12px 16px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- #
# Storage / state
# --------------------------------------------------------------------------- #
def _hash(d):
    return hashlib.md5(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()


store, store_error = get_store()

if "data" not in st.session_state:
    st.session_state.data = store.load()
    st.session_state._last_saved_hash = _hash(st.session_state.data)
if "defaults" not in st.session_state:
    st.session_state.defaults = _seed()

data = st.session_state.data


def persist(toast=True):
    store.save(st.session_state.data)
    st.session_state._last_saved_hash = _hash(st.session_state.data)
    st.session_state["_saved_at"] = datetime.now().strftime("%b %d, %Y · %H:%M")
    if toast:
        st.toast("Saved", icon="💾")


# --------------------------------------------------------------------------- #
# H2 tracker computation
# --------------------------------------------------------------------------- #
def compute_h2_display(row):
    months = row.get("months", {}) or {}
    nums = [months[m] for m in MONTHS if isinstance(months.get(m), (int, float))]
    target = row.get("target")
    kind = row.get("type", "sum")
    if kind == "sum":
        total = sum(nums)
        disp_total = f"{total:,.0f}"
        var = total / (target * len(MONTHS)) - 1 if target else None
    elif kind == "avg":
        total = (sum(nums) / len(nums)) if nums else 0.0
        disp_total = f"{total:,.1f}%"
        var = (total / target - 1) if target else None
    else:
        total = nums[-1] if nums else 0
        disp_total = f"{total:,.0f}"
        var = None
    disp_var = f"{var * 100:+.0f}%" if var is not None else "—"
    return disp_total, disp_var


def h2_to_dataframe(rows):
    records = []
    for r in rows:
        rec = {"KPI": r["kpi"], "Monthly Target": r.get("target")}
        for m in MONTHS:
            rec[m] = (r.get("months", {}) or {}).get(m)
        total, var = compute_h2_display(r)
        rec["H2 Total / Avg"] = total
        rec["vs Target"] = var
        records.append(rec)
    return pd.DataFrame(records)


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <div class="lcn-band">
      <div class="lcn-mark">LCN<span>consulting</span></div>
      <h1>2026 KPI Dashboard</h1>
      <p>Tighter, decision-oriented KPIs aligned to pipeline creation, enterprise expansion, and net-new wins.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.subheader("Data source")
    if store.persistent:
        st.success("🟢 Connected to Google Sheets — edits save permanently.")
    else:
        st.warning("🟡 Local mode (no persistence). Add Google Sheets secrets to "
                   "make edits stick. See README.")
    if store_error:
        st.error(f"Google Sheets connection failed, using local file.\n\n{store_error}")

    st.divider()
    auto_save = st.toggle("Auto-save changes", value=store.persistent,
                          help="Write every change straight to the Sheet.")

    if st.button("💾 Save now", use_container_width=True, type="primary"):
        persist(toast=False)
        st.success("Saved.")

    if st.button("🔄 Refresh from source", use_container_width=True,
                 help="Re-pull the latest values (e.g. if the Sheet was edited directly)."):
        st.cache_resource.clear()
        for k in ("data", "defaults", "_last_saved_hash"):
            st.session_state.pop(k, None)
        st.rerun()

    if st.session_state.get("_saved_at"):
        st.caption(f"Last saved: {st.session_state['_saved_at']}")

    st.download_button(
        "⬇️ Export data.json (backup)",
        data=json.dumps(st.session_state.data, indent=2, ensure_ascii=False),
        file_name="data.json", mime="application/json", use_container_width=True,
    )

    with st.expander("Reset to seed values"):
        st.caption("Restores the original KPIs. Overwrites current data.")
        if st.button("↺ Reset", use_container_width=True):
            st.session_state.data = _seed()
            persist(toast=False)
            st.rerun()

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 KPI Scorecard", "📈 Open Bids Pipeline", "🎯 Account Strategy", "🗓️ H2 Monthly Tracker"]
)

# ----- Tab 1: KPI Scorecard ------------------------------------------------- #
with tab1:
    st.subheader("KPI Scorecard")
    st.caption("Expected targets for 0–6 and 6–12 months, alongside where we are now. "
               "Set each metric's Status to see how we're tracking.")
    df_sc = pd.DataFrame(data["scorecard"]).reindex(columns=SCORECARD_COLS).fillna("")
    edited_sc = st.data_editor(
        df_sc, key="sc_editor", use_container_width=True, hide_index=True, num_rows="dynamic",
        column_config={
            "Metric": st.column_config.TextColumn("Metric", width="medium"),
            "Expected 0-6 mo": st.column_config.TextColumn("Expected · 0–6 mo", width="medium"),
            "Expected 6-12 mo": st.column_config.TextColumn("Expected · 6–12 mo", width="medium"),
            "Where we are now": st.column_config.TextColumn("Where we are now", width="medium"),
            "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS, width="small"),
        },
    )
    st.session_state.data["scorecard"] = edited_sc.to_dict("records")
    counts = edited_sc["Status"].value_counts().to_dict() if "Status" in edited_sc else {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("On track", counts.get("On track", 0))
    c2.metric("At risk", counts.get("At risk", 0))
    c3.metric("Behind", counts.get("Behind", 0))
    c4.metric("Achieved", counts.get("Achieved", 0))

# ----- Tab 2: Open Bids Pipeline -------------------------------------------- #
with tab2:
    st.subheader("Open Bids Pipeline")
    st.caption("Editable working view for the monthly commercial review.")
    df_pl = pd.DataFrame(data["pipeline"])
    active = int((~df_pl["Stage"].isin(["Won", "Lost"])).sum()) if "Stage" in df_pl else len(df_pl)
    clients = int(df_pl["Client"].replace("", pd.NA).dropna().nunique()) if "Client" in df_pl else 0
    won = int((df_pl["Stage"] == "Won").sum()) if "Stage" in df_pl else 0
    lost = int((df_pl["Stage"] == "Lost").sum()) if "Stage" in df_pl else 0
    win_rate = f"{won / (won + lost) * 100:.0f}%" if (won + lost) > 0 else "—"
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Opps", active)
    m2.metric("Clients", clients)
    m3.metric("Win Rate", win_rate)
    edited_pl = st.data_editor(
        df_pl, key="pl_editor", use_container_width=True, hide_index=True, num_rows="dynamic",
        column_config={
            "Client": st.column_config.TextColumn("Client", width="small"),
            "Project": st.column_config.TextColumn("Project", width="medium"),
            "Stage": st.column_config.SelectboxColumn("Stage", options=STAGE_OPTIONS, width="small"),
            "Win Probability (%)": st.column_config.NumberColumn(
                "Win Probability (%)", min_value=0, max_value=100, step=5, format="%d%%"),
            "Confidence": st.column_config.SelectboxColumn("Confidence", options=CONFIDENCE_OPTIONS, width="small"),
            "Next Step": st.column_config.TextColumn("Next Step", width="large"),
        },
    )
    st.session_state.data["pipeline"] = edited_pl.to_dict("records")
    st.caption("🟢 High-confidence  🟠 Medium  🔴 At-risk — review stage movement, probability, "
               "and next step monthly; only count opps that are stage-defined and owner-assigned.")

# ----- Tab 3: Account Strategy ---------------------------------------------- #
with tab3:
    st.subheader("Where We Play — and How We Win in Every Tier")
    st.caption("2H 2026 · Account Strategy. Each tier shows its expected goal next to "
               "where we are now. One priority per line.")
    tier_colors = {"tier1": "#0A4595", "tier2": "#0B2D5C", "tier3": "#5C7AAE"}
    cols = st.columns(3)
    for col, key in zip(cols, TIER_KEYS):
        t = data["strategy"][key]
        with col:
            st.markdown(
                f"""<div class="tier-card" style="background:{tier_colors[key]};">
                    <div class="tier-sub">{t['tier_label'].upper()}</div>
                    <div class="tier-title">{t['title']}</div></div>""",
                unsafe_allow_html=True,
            )
            t["heading"] = st.text_input("Section heading", t["heading"], key=f"{key}_h")
            t["points"] = st.text_area("Priorities (one per line)", t["points"], height=180, key=f"{key}_p")
            st.markdown("**Goal**")
            t["goal_target"] = st.text_input("Expected", t.get("goal_target", ""), key=f"{key}_gt")
            t["goal_current"] = st.text_input("Where we are now", t.get("goal_current", ""), key=f"{key}_gc")
            cur_status = t.get("goal_status", "On track")
            t["goal_status"] = st.selectbox(
                "Status", STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(cur_status) if cur_status in STATUS_OPTIONS else 0,
                key=f"{key}_gs",
            )
            now = (t["goal_current"] or "").strip() or "—"
            st.markdown(
                f"""<div class="goal-box">
                    <div>Expected: <b>{t['goal_target']}</b></div>
                    <div style="margin-top:5px;">Now: {now} &nbsp; {status_badge(t['goal_status'])}</div>
                    </div>""",
                unsafe_allow_html=True,
            )
        st.session_state.data["strategy"][key] = t

# ----- Tab 4: H2 Monthly Tracker -------------------------------------------- #
with tab4:
    st.subheader("H2 2026 Monthly Tracker")
    st.caption("Enter each month from your LinkedIn analytics export. H2 Total/Avg and vs Target "
               "auto-calculate. Sums for counts, averages for rates; Total followers shows the latest month.")
    df_h2 = h2_to_dataframe(data["h2"])
    month_cfg = {m: st.column_config.NumberColumn(m, step=1) for m in MONTHS}
    edited_h2 = st.data_editor(
        df_h2, key="h2_editor", use_container_width=True, hide_index=True,
        disabled=["KPI", "H2 Total / Avg", "vs Target"],
        column_config={
            "KPI": st.column_config.TextColumn("KPI", width="medium"),
            "Monthly Target": st.column_config.NumberColumn("Monthly Target", step=1),
            **month_cfg,
            "H2 Total / Avg": st.column_config.TextColumn("H2 Total / Avg", width="small"),
            "vs Target": st.column_config.TextColumn("vs Target", width="small"),
        },
    )
    for i, r in enumerate(st.session_state.data["h2"]):
        row = edited_h2.iloc[i]
        tgt = row["Monthly Target"]
        r["target"] = None if pd.isna(tgt) else float(tgt)
        r["months"] = {m: (None if pd.isna(row[m]) else float(row[m])) for m in MONTHS}

# --------------------------------------------------------------------------- #
# Auto-save (one write per rerun, only if something changed)
# --------------------------------------------------------------------------- #
if auto_save and store.persistent:
    if _hash(st.session_state.data) != st.session_state.get("_last_saved_hash"):
        try:
            persist(toast=True)
        except Exception as e:  # noqa: BLE001
            st.warning(f"Auto-save failed: {e}")

st.markdown(
    f'<div class="lcn-foot">CONFIDENTIAL · Internal Use Only · © {datetime.now().year} LCN Consulting</div>',
    unsafe_allow_html=True,
)
