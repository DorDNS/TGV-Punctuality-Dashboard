import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

from utils.filters import dq_sidebar
from utils.compute import apply_overview_filters
from utils.quality import (
    missingness_table,
    duplicate_keys,
    bounds_issues,
    logical_consistency,
    outlier_months,
)

# Helpers
def analysis_card(title: str, body_md: str, icon: str = ":material/analytics:"):
    with st.container(border=True):
        st.markdown(f"{icon} **{title}**")
        st.markdown(body_md)

def _normalize_missing_table(miss_raw: pd.DataFrame | None, n_rows: int) -> pd.DataFrame:
    if miss_raw is None or (isinstance(miss_raw, pd.DataFrame) and miss_raw.empty):
        return pd.DataFrame(columns=["Column", "Missing %", "Missing count", "Non-null %"])

    m = miss_raw.copy()

    # Column name field
    col_candidates = [c for c in m.columns if str(c).lower() in {"column", "col", "field", "name"}]
    if col_candidates:
        m = m.rename(columns={col_candidates[0]: "Column"})
    else:
        m = m.reset_index().rename(columns={"index": "Column"})
        if "Column" not in m.columns:
            m["Column"] = m.columns.astype(str)

    def _first(columns, predicates):
        for c in columns:
            lc = str(c).lower()
            if any(p(lc) for p in predicates):
                return c
        return None

    cols = list(m.columns)
    pct_col = _first(
        cols,
        [
            lambda s: "missing" in s and "%" in s,
            lambda s: "missing_pct" in s,
            lambda s: "pct_missing" in s,
            lambda s: "missing_percent" in s,
            lambda s: "missing_ratio" in s,
            lambda s: s == "missing%",
        ],
    )
    cnt_col = _first(
        cols,
        [
            lambda s: "n_missing" in s,
            lambda s: "missing_count" in s,
            lambda s: s == "missing",
            lambda s: "null" in s and "count" in s,
            lambda s: "na" in s and "count" in s,
        ],
    )

    m["Missing %"] = np.nan
    m["Missing count"] = np.nan

    if pct_col is not None:
        pct = pd.to_numeric(m[pct_col], errors="coerce")
        if pct.max(skipna=True) is not None and pct.max(skipna=True) <= 1.0:
            pct = pct * 100.0
        m["Missing %"] = pct

    if cnt_col is not None:
        m["Missing count"] = pd.to_numeric(m[cnt_col], errors="coerce")

    if m["Missing %"].isna().all() and not m["Missing count"].isna().all() and n_rows:
        m["Missing %"] = 100.0 * m["Missing count"] / float(n_rows)
    if m["Missing count"].isna().all() and not m["Missing %"].isna().all() and n_rows:
        m["Missing count"] = (m["Missing %"] * float(n_rows) / 100.0).round().astype("Int64")

    m["Non-null %"] = 100.0 - pd.to_numeric(m["Missing %"], errors="coerce")
    m["Missing %"] = pd.to_numeric(m["Missing %"], errors="coerce")
    m["Missing count"] = pd.to_numeric(m["Missing count"], errors="coerce").astype("Int64")

    keep = ["Column", "Missing %", "Missing count", "Non-null %"]
    extras = [c for c in m.columns if c not in keep]
    return m[keep + extras]

def _dq_bounds_info_md() -> str:
    return """
**Bounds checked** (hard limits on numeric values):

- **Counts ≥ 0 (integers)** — scheduled circulations, canceled trains, delayed departures/arrivals, and delay buckets (≥15 / ≥30 / ≥60 min).
- **Percentages in [0, 100]** — all *delay cause percentage* columns, plus `on_time_pct` and `cancel_rate_pct` when present.
- **Durations / delays ≥ 0 minutes** — mean delay columns (for all trains and for delayed trains, departure and arrival).
- **Distances ≥ 0 km** — `distance_km` when present.
"""

def _dq_logical_info_md() -> str:
    return """
**Logical rules** (cross-field consistency checks):

- **Hierarchy of delay counts:** `≥60 ≤ ≥30 ≤ ≥15 ≤ circulated`.
- **Capacity constraints:**
  - `late_arr_count ≤ circulated`
  - `late_dep_count ≤ circulated` (if available)
  - `cancel_count ≤ circulated`
- **Average consistency:**
  - `average_delay_all ≤ average_delay_delayed` (both departure and arrival).
- **Cause percentages sanity:**
  - Sum of *delay cause percentages* ≈ 100 % (allow small rounding tolerance).
- **Rate consistency:**
  - `on_time_pct` and `cancel_rate_pct` are 0–100 and coherent with volumes.
"""

def _extract_month_col(dd: pd.DataFrame) -> pd.Series | None:
    """Try to standardize a YYYY-MM month column."""
    for c in ["month", "Month", "date", "Date"]:
        if c in dd.columns:
            try:
                s = pd.to_datetime(dd[c].astype(str), errors="coerce")
                if s.notna().any():
                    return s.dt.to_period("M").astype(str)
            except Exception:
                pass
    return None

def _dq_score(n, miss_tbl, dup_df, bdf, ldf, odf) -> int:
    """Lightweight DQ score out of 100."""
    score = 100.0
    if not miss_tbl.empty and "Missing %" in miss_tbl.columns:
        score -= 0.5 * float(miss_tbl["Missing %"].mean())  # avg missing% weighted 0.5
    if n > 0 and not dup_df.empty:
        score -= min(10.0, 100.0 * len(dup_df) / n)        # cap at 10
    for df_issues, cap in [(bdf, 15.0), (ldf, 15.0), (odf, 15.0)]:
        if n > 0 and df_issues is not None and not df_issues.empty:
            score -= min(cap, 100.0 * len(df_issues) / n)
    return max(0, int(round(score)))

# Page
st.set_page_config(page_title="Data Quality", page_icon=":material/award_star:", layout="wide")

# Sidebar
dq_sidebar()
with st.sidebar.expander("Data Quality options", expanded=False):
    show_samples = st.checkbox("Show sample rows in each tab", value=True)
    max_rows_preview = st.number_input("Max preview rows per issue table", 200, 5000, 1000, step=100)

# Title
st.markdown("# Data Quality")
st.caption("Validation on **completeness**, **uniqueness**, **ranges**, **logical rules**, and **outliers**.")

# Data load
df = st.session_state.get("df_clean", None)
if df is None or df.empty:
    st.error("Data not loaded.")
    st.stop()

# Scope
dff = apply_overview_filters(df, st.session_state)
if dff.empty:
    st.info("No data in current filter. Adjust the filters on the left.")
    st.stop()

month_str = _extract_month_col(dff)
IQR_K = 1.5 

# Summary calculations
n_rows, n_cols = dff.shape
cols_missing = _normalize_missing_table(missingness_table(dff), len(dff))
dup_keys = duplicate_keys(dff)
b_issues = bounds_issues(dff)
logic = logical_consistency(dff)
outs = outlier_months(dff, method="iqr", threshold=IQR_K)

score = _dq_score(n_rows, cols_missing, dup_keys, b_issues, logic, outs)
tone = "success" if score >= 90 else "warning" if score >= 75 else "error"

# Snapshot header
st.markdown("### Quality snapshot")
with st.container(border=True):
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Rows (scope)", f"{n_rows:,}")
    c2.metric("Columns", f"{n_cols:,}")
    c3.metric("Time span", f"{pd.Series(month_str).min()} → {pd.Series(month_str).max()}" if month_str is not None else "—")
    c4.metric("Missing cols", f"{(cols_missing['Missing %'] > 0).sum() if not cols_missing.empty else 0}")
    c5.metric("Dup keys", f"{0 if dup_keys.empty else len(dup_keys)}")
    c6.metric("DQ score", f"{score}/100")

    msg = (
        "Data quality is **excellent**." if tone == "success"
        else "Data quality is **acceptable**, some checks need attention." if tone == "warning"
        else "Data quality is **at risk**. Please review the issues below."
    )
    getattr(st, tone)(f":material/verified:  {msg}")

st.divider()

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Missingness", "Duplicates", "Bounds", "Logical rules", "Outliers"])

# Missingness
with tab1:
    st.subheader("Missingness by column")
    miss = cols_missing.copy()
    if miss.empty:
        st.success("No missing values detected.")
    else:
        if "Missing %" in miss.columns:
            miss = miss.sort_values("Missing %", ascending=False)
        st.dataframe(miss, use_container_width=True, hide_index=True)

        try:
            if {"Column", "Missing %"}.issubset(miss.columns):
                fig_m = px.bar(miss, x="Column", y="Missing %", title=None)
                fig_m.update_layout(template="plotly_white", height=360, margin=dict(l=8, r=8, t=10, b=8))
                fig_m.update_xaxes(title=None, tickangle=45)
                fig_m.update_yaxes(title="% missing", rangemode="tozero")
                st.plotly_chart(fig_m, use_container_width=True)
        except Exception:
            pass

        if month_str is not None:
            try:
                dfm = dff.copy()
                dfm["_month"] = month_str
                heat = []
                for col in dff.columns:
                    pct_by_m = dfm.groupby("_month")[col].apply(lambda s: s.isna().mean() * 100).rename(col)
                    heat.append(pct_by_m)
                heat_df = pd.concat(heat, axis=1).sort_index()
                if not heat_df.empty:
                    fig_hm = px.imshow(
                        heat_df.T,
                        aspect="auto",
                        title="Missingness heatmap by month & column (%)",
                        color_continuous_scale="Reds",
                    )
                    fig_hm.update_layout(template="plotly_white", height=420, margin=dict(l=8, r=8, t=32, b=8))
                    st.plotly_chart(fig_hm, use_container_width=True)
            except Exception:
                pass

        analysis_card(
            title="Missing data patterns",
            icon=":material/indeterminate_question_box:",
            body_md="""
        From these views, the gaps are very clear. The three free-text comment fields are almost always empty (two at 100% missing and arrival comments ~93%), so they add little value today. Most core metrics (service, duration, counts, cause percents) are complete, with only a tiny hole in `cancel_rate_pct` (~0.7%). The heatmap shows a few columns that are missing for every month—`canceled`, `late_depart_count`, `avg_delay_dep_all_min`, and `late_arr_count`—which likely means those fields were never populated or were renamed upstream. We also see time-pattern gaps: `late_over_15_count` has missing data early on and then becomes complete, and `circulated` has a small patch of missing values around 2019.
        """
        )

# Duplicates
with tab2:
    st.subheader("Potential duplicates")
    st.caption("Checked on key: **(date, service, departure, arrival)**. Also scans for full-row duplicates.")
    dups_key = dup_keys
    try:
        dup_full = dff[dff.duplicated(keep=False)].copy()
    except Exception:
        dup_full = pd.DataFrame()

    if dups_key.empty and (dup_full.empty or len(dup_full) == 0):
        st.success("No duplicates detected.")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Key duplicates", f"{0 if dups_key.empty else len(dups_key)}")
        c2.metric("Exact-row duplicates", f"{0 if dup_full.empty else len(dup_full)}")

        if not dups_key.empty:
            st.warning(f"{len(dups_key)} duplicated key rows.")
            if show_samples:
                st.dataframe(dups_key.head(max_rows_preview), use_container_width=True, hide_index=True)
                st.caption(f"Showing up to {max_rows_preview} rows.")
            else:
                st.caption("Preview hidden (toggle in Data Quality options).")

        if not dup_full.empty:
            if show_samples:
                with st.expander("Exact-row duplicates (all columns match)"):
                    st.dataframe(dup_full.head(max_rows_preview), use_container_width=True, hide_index=True)
            else:
                st.caption("Exact-row duplicates detected (preview hidden).")

# Bounds
with tab3:
    st.subheader("Bounds & impossible values")
    st.info(_dq_bounds_info_md())
    b = b_issues
    if b.empty:
        st.success("No bounds issues detected.")
    else:
        st.warning(f"{len(b)} rows with bounds issues.")
        if "column" in b.columns:
            grp = b.groupby("column").size().reset_index(name="rows").sort_values("rows", ascending=False)
            st.markdown("**Issues by column**")
            st.dataframe(grp, use_container_width=True, hide_index=True)
        if show_samples:
            st.dataframe(b.head(max_rows_preview), use_container_width=True, hide_index=True)
            st.caption(f"Showing up to {max_rows_preview} rows.")
        else:
            st.caption("Bounds issues detected (preview hidden).")

# Logical rules
with tab4:
    st.subheader("Logical consistency")
    st.info(_dq_logical_info_md())
    l = logic
    if l.empty:
        st.success("All logical rules passed.")
    else:
        st.warning(f"{len(l)} violations of business rules.")
        if "rule" in l.columns:
            per_rule = l.groupby("rule").size().reset_index(name="violations").sort_values("violations", ascending=False)
            st.markdown("**Violations by rule**")
            st.dataframe(per_rule, use_container_width=True, hide_index=True)
        if show_samples:
            st.dataframe(l.head(max_rows_preview), use_container_width=True, hide_index=True)
            st.caption(f"Showing up to {max_rows_preview} rows.")
        else:
            st.caption("Logical rule violations detected (preview hidden).")

    analysis_card(
            title="Logical rules analysis",
            icon=":material/cognition:",
            body_md="""
        This table shows that most logical rule violations come from a single condition: the average delay of all trains being greater than the average delay among delayed trains. There are 83 cases of this, meaning that for some routes or months, the mean delay value was computed incorrectly or includes rounding or aggregation errors. In theory, the average of all trains should always be lower since it includes many on-time trains with zero delay. Only four other violations appear—two where the number of trains delayed over 15 minutes exceeds the total number of circulated trains, and two where the hierarchy between ≥30 and ≥15-minute delays is broken. These isolated cases might come from data entry mistakes or mismatched counts during merges. Overall, the logical checks reveal that numerical relationships are mostly consistent, but the computation of average delays deserves attention, as it systematically breaks an expected rule and likely points to an upstream calculation or unit handling issue.
        """
        )

# Outliers
with tab5:
    st.subheader("Outlier months (unusually low on-time % per liaison)")
    st.caption(f"Method: **IQR (interquartile range)** — threshold **k = {IQR_K}**")
    out = outlier_months(dff, method="iqr", threshold=IQR_K)

    if out.empty:
        st.info("No outlier months flagged with current parameters.")
    else:
        if "liaison" in out.columns:
            counts = out.groupby("liaison").size().reset_index(name="outlier_months").sort_values("outlier_months", ascending=False)
            st.markdown("**Liaisons with most outlier months**")
            st.dataframe(counts.head(30), use_container_width=True, hide_index=True)
        if show_samples:
            st.dataframe(out, use_container_width=True, hide_index=True)
        else:
            st.caption("Outliers detected (preview hidden).")

    analysis_card(
            title="Outlier months analysis",
            icon=":material/output_circle:",
            body_md="""
        This table lists the train routes that most often experienced unusually low on-time performance compared with their normal trend. The **GENEVA → PARIS LYON** line stands out clearly, with **9 outlier months**, meaning it had repeated drops in punctuality that deviate from the expected range. Several other international or long-distance routes such as **ZURICH → PARIS LYON**, **BELLEGARDE (AIN) → PARIS LYON**, and **TOULOUSE → PARIS MONTPARNASSE** follow closely with 8 outlier months each, showing consistent reliability challenges. Interestingly, both directions between **PARIS LYON ↔ GENEVA** appear on the list, suggesting that disruptions affected the corridor as a whole rather than isolated segments. Other frequent connections like **FRANKFURT → PARIS EST** and **LYON → PARIS** also show several atypical months, possibly linked to cross-border or high-traffic operations. Overall, most of the problematic lines are long routes entering or leaving Paris, which hints that weather, congestion, or international coordination could explain the instability. These results point to a need for deeper investigation into punctuality fluctuations on key transnational and southern corridors.
        """
        )