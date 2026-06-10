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

from storage import get_store, MONTHS, WEEK_COLS, _seed

# --------------------------------------------------------------------------- #
# Config & constants
# --------------------------------------------------------------------------- #
STAGE_OPTIONS = ["Open", "Qualified", "Proposal", "Won", "Lost"]
CONFIDENCE_OPTIONS = ["High-confidence", "Medium", "At-risk"]

# H2 2026 horizon for the weekly scorecard month picker
MONTHS_KEYS = [f"2026-{m:02d}" for m in range(6, 13)]
_MONTH_NAMES = {6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
MONTH_LABELS = {k: f"{_MONTH_NAMES[int(k[5:])]} {k[:4]}" for k in MONTHS_KEYS}
AGG_TO_LABEL = {"sum": "Sum", "snapshot": "Snapshot"}
LABEL_TO_AGG = {"Sum": "sum", "Snapshot": "snapshot"}


def _default_month():
    key = f"{datetime.now().year}-{datetime.now().month:02d}"
    return key if key in MONTHS_KEYS else MONTHS_KEYS[0]


def weeks_index(weeks_rows):
    """(month, metric) -> {W1..W5: value}."""
    idx = {}
    for r in weeks_rows:
        idx[(r.get("Month"), r.get("Metric"))] = {w: r.get(w) for w in WEEK_COLS}
    return idx


def weeks_to_list(idx, metric_names):
    """Rebuild the flat week-rows for every month × current metric, keeping values."""
    out = []
    for mo in MONTHS_KEYS:
        for name in metric_names:
            vals = idx.get((mo, name), {})
            row = {"Month": mo, "Metric": name}
            for w in WEEK_COLS:
                row[w] = vals.get(w)
            out.append(row)
    return out


def week_rollup(metric, week_vals):
    """Return (mtd_number, gap_text, pct) for one metric's week values."""
    nums = [v for v in week_vals if isinstance(v, (int, float))]
    if metric.get("Agg", "sum") == "snapshot":
        mtd = nums[-1] if nums else 0
    else:
        mtd = sum(nums)
    e = metric.get("Expected")
    e = e if isinstance(e, (int, float)) else None
    if not e:
        return mtd, "—", 0
    if mtd >= e:
        return mtd, ("✓ Goal met" if mtd == e else f"✓ +{_g(mtd - e)} over"), 100
    return mtd, f"{_g(e - mtd)} to go", int(max(0, min(100, round(mtd / e * 100))))


def _g(x):
    """Tidy number formatting: 2 not 2.0, 2.5 stays 2.5."""
    return f"{x:g}" if isinstance(x, (int, float)) else "0"


def numbers_df(rows, label):
    """Build the Expected/Current/Gap/% dataframe for a numeric KPI table."""
    recs = []
    for r in rows:
        exp, cur = r.get("Expected"), r.get("Current")
        e = exp if isinstance(exp, (int, float)) else None
        c = cur if isinstance(cur, (int, float)) else 0
        if not e:  # no/zero target → nothing to measure against
            gap_txt, pct = "—", 0
        elif c >= e:
            gap_txt = "✓ Goal met" if c == e else f"✓ +{_g(c - e)} over"
            pct = 100
        else:
            gap_txt = f"{_g(e - c)} to go"
            pct = int(max(0, min(100, round(c / e * 100))))
        recs.append({label: r.get(label, ""), "Expected": exp, "Current": cur,
                     "Gap to goal": gap_txt, "% to goal": pct})
    return pd.DataFrame(recs)


def read_numbers(edited_df, label):
    """Read the editable columns back into the stored structure."""
    out = []
    for _, row in edited_df.iterrows():
        name = row[label]
        out.append({
            label: "" if pd.isna(name) else str(name),
            "Expected": None if pd.isna(row["Expected"]) else float(row["Expected"]),
            "Current": 0 if pd.isna(row["Current"]) else float(row["Current"]),
        })
    return out


def numbers_summary(rows):
    valid = [(r.get("Expected"), r.get("Current")) for r in rows
             if isinstance(r.get("Expected"), (int, float)) and r.get("Expected")]
    met = sum(1 for e, c in valid if (c or 0) >= e)
    att = round(sum(min(100, (c or 0) / e * 100) for e, c in valid) / len(valid)) if valid else 0
    return met, len(valid), att


def numbers_editor(rows, label, key):
    """Render a numbers table (Metric/Goal · Expected · Current · Gap · %)."""
    df = numbers_df(rows, label)
    return st.data_editor(
        df, key=key, use_container_width=True, hide_index=True, num_rows="dynamic",
        disabled=[label, "Gap to goal", "% to goal"],
        column_config={
            label: st.column_config.TextColumn(label, width="large"),
            "Expected": st.column_config.NumberColumn("Expected", step=1, width="small"),
            "Current": st.column_config.NumberColumn("Current", step=1, width="small"),
            "Gap to goal": st.column_config.TextColumn("How far from goal", width="small"),
            "% to goal": st.column_config.ProgressColumn(
                "% to goal", min_value=0, max_value=100, format="%d%%"),
        },
    )

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
tab1, tab_an, tab2, tab3, tab4 = st.tabs(
    ["📋 KPI Scorecard", "🧭 Analyst KPIs", "📈 Open Bids Pipeline",
     "🎯 Account Strategy", "🗓️ H2 Monthly Tracker"]
)

# ----- Tab 1: KPI Scorecard ------------------------------------------------- #
with tab1:
    st.subheader("Weekly KPI Scorecard")
    metrics = data["scorecard"]
    metric_names = [m["Metric"] for m in metrics]

    labels = [MONTH_LABELS[k] for k in MONTHS_KEYS]
    default_label = MONTH_LABELS[_default_month()]
    sel_label = st.selectbox("Month", labels, index=labels.index(default_label), key="sc_month")
    sel_month = MONTHS_KEYS[labels.index(sel_label)]
    st.caption("Log each week's number. **Sum** metrics add up toward the monthly target; "
               "**Snapshot** metrics (e.g. active opps) show the latest week's count. "
               "Month total, gap, and progress update automatically.")

    widx = weeks_index(data["scorecard_weeks"])
    rows = []
    for m in metrics:
        wk = widx.get((sel_month, m["Metric"]), {})
        rec = {"Metric": m["Metric"], "Type": AGG_TO_LABEL.get(m.get("Agg", "sum"), "Sum"),
               "Expected": m.get("Expected")}
        for w in WEEK_COLS:
            rec[w] = wk.get(w)
        mtd, gap, pct = week_rollup(m, [wk.get(w) for w in WEEK_COLS])
        rec["Month total"] = _g(mtd)
        rec["How far from goal"] = gap
        rec["% to goal"] = pct
        rows.append(rec)

    edited = st.data_editor(
        pd.DataFrame(rows), key=f"sc_grid_{sel_month}", use_container_width=True, hide_index=True,
        disabled=["Metric", "Type", "Expected", "Month total", "How far from goal", "% to goal"],
        column_config={
            "Metric": st.column_config.TextColumn("Metric", width="medium"),
            "Type": st.column_config.TextColumn("Type", width="small"),
            "Expected": st.column_config.NumberColumn("Monthly target", width="small"),
            **{w: st.column_config.NumberColumn(w, step=1, width="small") for w in WEEK_COLS},
            "Month total": st.column_config.TextColumn("Month total", width="small"),
            "How far from goal": st.column_config.TextColumn("How far from goal", width="small"),
            "% to goal": st.column_config.ProgressColumn("% to goal", min_value=0, max_value=100, format="%d%%"),
        },
    )
    # write this month's week values back, keeping all other months intact
    for i, m in enumerate(metrics):
        row = edited.iloc[i]
        widx[(sel_month, m["Metric"])] = {
            w: (None if pd.isna(row[w]) else float(row[w])) for w in WEEK_COLS
        }
    st.session_state.data["scorecard_weeks"] = weeks_to_list(widx, metric_names)

    # month summary
    computed = [week_rollup(m, [widx.get((sel_month, m["Metric"]), {}).get(w) for w in WEEK_COLS])
                for m in metrics]
    valid = [(m, c[0]) for m, c in zip(metrics, computed)
             if isinstance(m.get("Expected"), (int, float)) and m.get("Expected")]
    met = sum(1 for m, mtd in valid if mtd >= m["Expected"])
    att = round(sum(min(100, mtd / m["Expected"] * 100) for m, mtd in valid) / len(valid)) if valid else 0
    c1, c2, c3 = st.columns(3)
    c1.metric(f"On-target ({sel_label})", f"{met}/{len(valid)}")
    c2.metric("Below target", len(valid) - met)
    c3.metric("Avg attainment", f"{att}%")

    with st.expander("⚙️ Edit monthly targets & roll-up type"):
        st.caption("Set each KPI's monthly target and how weeks roll up. "
                   "Sum = weekly entries add together. Snapshot = latest week's value (for counts like active opps).")
        defs_df = pd.DataFrame([{"Metric": m["Metric"], "Monthly target": m.get("Expected"),
                                 "Roll-up": AGG_TO_LABEL.get(m.get("Agg", "sum"), "Sum")} for m in metrics])
        ed = st.data_editor(
            defs_df, key="sc_defs", use_container_width=True, hide_index=True, num_rows="dynamic",
            column_config={
                "Metric": st.column_config.TextColumn("Metric", width="large"),
                "Monthly target": st.column_config.NumberColumn("Monthly target", step=1, width="small"),
                "Roll-up": st.column_config.SelectboxColumn("Roll-up", options=["Sum", "Snapshot"], width="small"),
            },
        )
        new_defs = []
        for _, r in ed.iterrows():
            nm = "" if pd.isna(r["Metric"]) else str(r["Metric"]).strip()
            if not nm:
                continue
            new_defs.append({
                "Metric": nm,
                "Expected": None if pd.isna(r["Monthly target"]) else float(r["Monthly target"]),
                "Agg": LABEL_TO_AGG.get(r["Roll-up"], "sum"),
            })
        if new_defs:
            st.session_state.data["scorecard"] = new_defs

# ----- Tab: Analyst KPIs ---------------------------------------------------- #
with tab_an:
    st.subheader("Analyst KPIs")
    analysts = [a["Analyst"] for a in data["analysts"]]
    comp_names = [c["Component"] for c in data["components"]]

    a_labels = [MONTH_LABELS[k] for k in MONTHS_KEYS]
    a_sel_label = st.selectbox("Month", a_labels, index=a_labels.index(MONTH_LABELS[_default_month()]),
                               key="an_month")
    a_sel_month = MONTHS_KEYS[a_labels.index(a_sel_label)]

    # ---- System components: analysts (rows) x components (cols), counts in cells ----
    st.markdown("##### System components")
    st.caption("How many times each analyst performed each system component this month. "
               "Switch months from the dropdown to track month over month.")
    cidx = {(r["Month"], r["Analyst"], r["Component"]): r.get("Count") for r in data["analyst_components"]}
    crows = []
    for an in analysts:
        rec = {"Analyst": an}
        tot = 0
        for cn in comp_names:
            v = cidx.get((a_sel_month, an, cn))
            rec[cn] = v
            if isinstance(v, (int, float)):
                tot += v
        rec["Total"] = tot
        crows.append(rec)
    ccfg = {"Analyst": st.column_config.TextColumn("Analyst", width="small")}
    for cn in comp_names:
        ccfg[cn] = st.column_config.NumberColumn(cn, min_value=0, step=1, format="%d", width="small")
    ccfg["Total"] = st.column_config.NumberColumn("Total", format="%d", width="small")
    edited_c = st.data_editor(
        pd.DataFrame(crows), key=f"an_comp_{a_sel_month}", use_container_width=True, hide_index=True,
        disabled=["Analyst", "Total"], column_config=ccfg,
    )
    for i, an in enumerate(analysts):
        row = edited_c.iloc[i]
        for cn in comp_names:
            v = row[cn]
            cidx[(a_sel_month, an, cn)] = None if pd.isna(v) else float(v)
    st.session_state.data["analyst_components"] = [
        {"Month": mo, "Analyst": an, "Component": cn, "Count": cidx.get((mo, an, cn))}
        for mo in MONTHS_KEYS for an in analysts for cn in comp_names
    ]
    month_total = sum(v for v in (cidx.get((a_sel_month, an, cn)) for an in analysts for cn in comp_names)
                      if isinstance(v, (int, float)))
    st.metric(f"Total system actions ({a_sel_label})", int(month_total))

    # ---- Risk taken: 1 per analyst per month, with explanation ----
    st.markdown("##### Risk taken")
    st.caption("Target: **1 risk per analyst** this month. Log the count and explain the risk.")
    ridx = {(r["Month"], r["Analyst"]): {"Count": r.get("Count"), "Explanation": r.get("Explanation", "")}
            for r in data["analyst_risk"]}
    rrows = []
    for an in analysts:
        c = ridx.get((a_sel_month, an), {})
        rrows.append({"Analyst": an, "Risks taken": c.get("Count"), "Explanation": c.get("Explanation", "")})
    edited_r = st.data_editor(
        pd.DataFrame(rrows), key=f"an_risk_{a_sel_month}", use_container_width=True, hide_index=True,
        disabled=["Analyst"],
        column_config={
            "Analyst": st.column_config.TextColumn("Analyst", width="small"),
            "Risks taken": st.column_config.NumberColumn("Risks taken", min_value=0, step=1, format="%d", width="small"),
            "Explanation": st.column_config.TextColumn("Explanation", width="large"),
        },
    )
    for i, an in enumerate(analysts):
        row = edited_r.iloc[i]
        rt = row["Risks taken"]
        ridx[(a_sel_month, an)] = {
            "Count": None if pd.isna(rt) else float(rt),
            "Explanation": "" if pd.isna(row["Explanation"]) else str(row["Explanation"]),
        }
    st.session_state.data["analyst_risk"] = [
        {"Month": mo, "Analyst": an, "Count": ridx.get((mo, an), {}).get("Count"),
         "Explanation": ridx.get((mo, an), {}).get("Explanation", "")}
        for mo in MONTHS_KEYS for an in analysts
    ]
    risk_met = sum(1 for an in analysts if (ridx.get((a_sel_month, an), {}).get("Count") or 0) >= 1)
    st.metric("Met risk target (\u22651)", f"{risk_met}/{len(analysts)}")

    # ---- Things learned about client: 2 per analyst per month, two boxes each ----
    st.markdown("##### Things learned about client")
    st.caption("Target: **2 things per analyst** this month. Two boxes are provided for each analyst.")
    lidx = {(r["Month"], r["Analyst"]): {"Count": r.get("Count"),
                                         "L1": r.get("Learning 1", ""), "L2": r.get("Learning 2", "")}
            for r in data["analyst_learned"]}
    lrows = []
    for an in analysts:
        c = lidx.get((a_sel_month, an), {})
        lrows.append({"Analyst": an, "Things learned": c.get("Count"),
                      "Learning 1": c.get("L1", ""), "Learning 2": c.get("L2", "")})
    edited_l = st.data_editor(
        pd.DataFrame(lrows), key=f"an_learn_{a_sel_month}", use_container_width=True, hide_index=True,
        disabled=["Analyst"],
        column_config={
            "Analyst": st.column_config.TextColumn("Analyst", width="small"),
            "Things learned": st.column_config.NumberColumn("Things learned", min_value=0, step=1, format="%d", width="small"),
            "Learning 1": st.column_config.TextColumn("Learning 1", width="large"),
            "Learning 2": st.column_config.TextColumn("Learning 2", width="large"),
        },
    )
    for i, an in enumerate(analysts):
        row = edited_l.iloc[i]
        lt = row["Things learned"]
        lidx[(a_sel_month, an)] = {
            "Count": None if pd.isna(lt) else float(lt),
            "L1": "" if pd.isna(row["Learning 1"]) else str(row["Learning 1"]),
            "L2": "" if pd.isna(row["Learning 2"]) else str(row["Learning 2"]),
        }
    st.session_state.data["analyst_learned"] = [
        {"Month": mo, "Analyst": an, "Count": lidx.get((mo, an), {}).get("Count"),
         "Learning 1": lidx.get((mo, an), {}).get("L1", ""), "Learning 2": lidx.get((mo, an), {}).get("L2", "")}
        for mo in MONTHS_KEYS for an in analysts
    ]
    learn_met = sum(1 for an in analysts if (lidx.get((a_sel_month, an), {}).get("Count") or 0) >= 2)
    st.metric("Met learning target (\u22652)", f"{learn_met}/{len(analysts)}")

    with st.expander("\u2699\ufe0f Manage analysts"):
        adf = pd.DataFrame({"Analyst": analysts})
        ed_a = st.data_editor(adf, key="an_people", use_container_width=True, hide_index=True,
                              num_rows="dynamic",
                              column_config={"Analyst": st.column_config.TextColumn("Analyst", width="large")})
        new_people = [{"Analyst": str(r["Analyst"]).strip()} for _, r in ed_a.iterrows()
                      if not pd.isna(r["Analyst"]) and str(r["Analyst"]).strip()]
        if new_people:
            st.session_state.data["analysts"] = new_people

    with st.expander("\u2139\ufe0f What each system component means"):
        for c in data["components"]:
            st.markdown(f"- **{c['Component']}** \u2014 {c.get('desc', '')}")


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
    st.subheader("Account Strategy — Goals")
    st.caption("The strategic goals as numbers: expected vs current, and the gap left to close.")
    edited_st = numbers_editor(data["strategy"], "Goal", "st_editor")
    st.session_state.data["strategy"] = read_numbers(edited_st, "Goal")
    met, total, att = numbers_summary(st.session_state.data["strategy"])
    c1, c2, c3 = st.columns(3)
    c1.metric("Goals met", f"{met}/{total}")
    c2.metric("Below goal", total - met)
    c3.metric("Avg attainment", f"{att}%")

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
