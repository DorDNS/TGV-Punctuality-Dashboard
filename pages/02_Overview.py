import streamlit as st
import numpy as np
import pandas as pd

from utils.filters import overview_sidebar
from utils.compute import (
    apply_overview_filters,
    kpis_overview,
    monthly_series,
    duration_small_multiples,
)
from utils.viz import line_monthly_enhanced, line_duration

# ---------- Small helpers ----------
def card(icon: str, title: str, body_md: str):
    with st.container(border=True):
        st.markdown(f"{icon} **{title}**")
        st.markdown(body_md)

def _tone_from_delta(delta: float | None):
    if delta is None or (isinstance(delta, float) and np.isnan(delta)):
        return "info"
    if delta >= 0.2:   # improving
        return "success"
    if delta <= -0.2:  # worsening
        return "warning"
    return "info"

def callout(tone: str, icon: str, text_md: str):
    box = getattr(st, tone, st.info)  # tone in {"info","success","warning","error"}
    box(f"{icon}  {text_md}")

def _fmt(v, unit):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.1f}{unit}"

# ---------- Page setup ----------
st.set_page_config(page_title="Overview", page_icon=":material/analytics:", layout="wide")
overview_sidebar()

st.markdown("# Overview")
st.caption("High-level trends for the selected scope.")

# ---------- Load & guardrails ----------
df = st.session_state.get("df_clean", None)
if df is None or df.empty:
    st.error("Data not loaded.")
    st.stop()

# Init date range once
if ("date_start" not in st.session_state or "date_end" not in st.session_state):
    opts = st.session_state.get("filters_catalog", {}).get("date_options", [])
    if opts:
        st.session_state["date_start"] = opts[0]
        st.session_state["date_end"] = opts[-1]

# Filtered data
dff = apply_overview_filters(df, st.session_state)

# ---------- Intro card ----------
card(
    icon=":material/explore:",
    title="What this page reveals",
    body_md="""
This page frames the **long-run behaviour** of TGV punctuality. Think of it as the spine of the story:
a current snapshot to set the scene, a time-series to understand shifts and cycles, and a split by journey
length to reveal structural differences. The goal isn’t just to show numbers, but to **understand how the
network behaves over time** and what that implies for the deeper dive that follows.
""",
)

st.divider()

# ======================
# HEADLINE KPI row
# ======================
st.subheader("Key indicators")
st.caption("Snapshot for your current selection. Adjust the **date range**, **Service**, and **Duration** filters in the sidebar.")

kpis = kpis_overview(dff)

# 12-month movement for on-time %
def _monthly_core(df_):
    if df_.empty:
        return pd.DataFrame(columns=["date", "on_time_pct"])
    ms_ = monthly_series(df_)
    return ms_[["date", "on_time_pct"]].dropna(subset=["on_time_pct"]).sort_values("date")

mcore = _monthly_core(dff)
delta_txt = None
if not mcore.empty and len(mcore) >= 24:
    last12 = mcore.tail(12)["on_time_pct"].mean()
    prev12 = mcore.tail(24).head(12)["on_time_pct"].mean()
    diff = last12 - prev12
    delta_txt = f"{diff:+.1f} pp vs prev. 12m"

c1, c2, c3 = st.columns(3)
c1.metric("On-time arrival %", _fmt(kpis["on_time_pct"], "%"), delta=delta_txt)
c2.metric("Cancel rate %", _fmt(kpis["cancel_rate_pct"], "%"))
c3.metric("Avg arrival delay (delayed trains)", _fmt(kpis["avg_arr_delay_delayed"], " min"))

with st.popover("What do these KPIs mean?"):
    st.markdown(
        """
- **On-time arrival %** = (circulated − late arrivals) / circulated.  
- **Cancel rate %** = canceled / planned.  
- **Avg arrival delay (delayed trains)** is a **weighted** mean over late trains (weights = number of late arrivals).
        """
    )

# --- Rich KPI callout (enhanced phrasing) ---
k_on, k_cancel, k_delay = kpis["on_time_pct"], kpis["cancel_rate_pct"], kpis["avg_arr_delay_delayed"]

kpi_bits = []
tone_hint = "info"

# On-time narrative
if pd.notna(k_on):
    if k_on >= 92:
        kpi_bits.append(f"**On-time** is **very strong** at **{k_on:.1f}%**.")
        tone_hint = "success"
    elif 89 <= k_on < 92:
        kpi_bits.append(f"**On-time** is **solid** at **{k_on:.1f}%**.")
        tone_hint = "success"
    elif 85 <= k_on < 89:
        kpi_bits.append(f"**On-time** is **acceptable** at **{k_on:.1f}%**, but there’s room to tighten operations.")
        tone_hint = "info"
    else:
        kpi_bits.append(f"**On-time** is **under pressure** at **{k_on:.1f}%**.")
        tone_hint = "warning"

# Cancel rate interaction
if pd.notna(k_cancel):
    if k_cancel >= 6:
        kpi_bits.append(f"**Cancel rate** is **elevated** (**{k_cancel:.1f}%**), suggesting lost capacity beyond mere delays.")
        tone_hint = "warning"
    elif 4 <= k_cancel < 6:
        kpi_bits.append(f"**Cancel rate** is **noticeable** (**{k_cancel:.1f}%**); cancellations contribute to perceived unreliability.")
    else:
        kpi_bits.append(f"**Cancel rate** is **contained** (**{k_cancel:.1f}%**); most pain is felt as delay, not suppression.")

# Delay level narrative
if pd.notna(k_delay):
    if k_delay >= 40:
        kpi_bits.append(f"When late, trains arrive **~{k_delay:.1f} minutes** behind—**material impact** on passengers.")
    elif 30 <= k_delay < 40:
        kpi_bits.append(f"When late, delays average **{k_delay:.1f} minutes**—**non-trivial** for travellers.")
    else:
        kpi_bits.append(f"When late, delays average **{k_delay:.1f} minutes**, relatively contained.")

if kpi_bits:
    callout(tone_hint, ":material/insights:", " ".join(kpi_bits))

# Explanatory card
card(
    icon=":material/info:",
    title="How to read the KPIs",
    body_md="""
Viewed over the full period of analysis, the network typically delivers **85–90% on-time arrivals**.
The **cancel rate**, around **3.4%**, stays moderate: most disruption is experienced as **delay**, not suppression
of service. And when a train is late, the **average delay** is about **33.9 minutes**, a level that matters
operationally and is clearly felt by passengers. These three numbers together anchor the rest of the page:
they describe the service as it is experienced today before we ask how we got here and where variance lives.
""",
)

st.divider()

# ==========================================
# Monthly series (driven by Primary metric)
# ==========================================
metric = st.session_state.get("metric", "On-time arrival %")
metric_map = {
    "On-time arrival %": ("on_time_pct", "Monthly on-time arrival %"),
    "Avg arrival delay (delayed trains)": ("avg_arr_delay_delayed", "Monthly avg arrival delay (delayed trains)"),
    "Cancel rate %": ("cancel_rate_pct", "Monthly cancel rate %"),
}

# Base monthly aggregation
ms = monthly_series(dff).sort_values("date")

# Weighted monthly avg for the delay metric
if metric == "Avg arrival delay (delayed trains)":
    def _wavg(g):
        w = g["late_arr_count"].fillna(0).astype(float).sum()
        if w <= 0:
            return np.nan
        num = (g["avg_delay_arr_delayed_min"].fillna(0).astype(float) * g["late_arr_count"].fillna(0).astype(float)).sum()
        return float(num / w)

    wseries = dff.groupby(dff["date"].dt.to_period("M")).apply(_wavg).reset_index(name="avg_arr_delay_delayed")
    wseries["date"] = wseries["date"].dt.to_timestamp()
    ms = ms.merge(wseries, on="date", how="left")

y_col, chart_title = metric_map.get(metric, metric_map["On-time arrival %"])

st.subheader("Long-run story")
st.caption(
    "This chart shows the long-run trajectory of your **Primary metric** "
    f"(**{metric}**). It’s the backbone of the narrative."
)

# (Removed the small grey dynamic sentence here — replaced by the colored callout below)

# Chart
if ms.empty:
    st.warning("No data for the selected filters.")
else:
    ref = 90 if y_col == "on_time_pct" else None
    fig1 = line_monthly_enhanced(
        ms,
        y_col=y_col,
        title=chart_title,
        ref_line=ref,
        annotate_extrema=True,
    )
    st.plotly_chart(fig1, width="stretch")

# --- Rich time-series callout (enhanced phrasing) ---
if not ms.empty and y_col in ms:
    s = ms.dropna(subset=[y_col]).sort_values("date")
    if not s.empty:
        i_min, i_max = s[y_col].idxmin(), s[y_col].idxmax()
        dmin, vmin = s.loc[i_min, "date"], s.loc[i_min, y_col]
        dmax, vmax = s.loc[i_max, "date"], s.loc[i_max, y_col]
        unit = "%" if y_col in ("on_time_pct", "cancel_rate_pct") else " min"

        cur12 = s[y_col].tail(12).mean() if len(s) >= 12 else np.nan
        prev12 = s[y_col].iloc[:-12].tail(12).mean() if len(s) >= 24 else np.nan
        delta12 = (cur12 - prev12) if (pd.notna(cur12) and pd.notna(prev12)) else np.nan

        # simple volatility read (last 12 months)
        vol = s[y_col].tail(12).std(ddof=0) if len(s) >= 12 else np.nan

        # ref-line read for on-time %
        band_msg = ""
        if y_col == "on_time_pct":
            last12 = s.tail(12)
            share_above = (last12[y_col] >= 90).mean() * 100 if len(last12) else np.nan
            if pd.notna(share_above):
                if share_above >= 70:
                    band_msg = f"Most recent months sit **at/above 90%** ({share_above:.0f}% of the last year)."
                elif share_above <= 30:
                    band_msg = f"Recent months are **mostly below 90%** ({share_above:.0f}% at/above)."

        # Build narrative
        bits = [
            f"**Low point:** {dmin:%b %Y} ({vmin:.1f}{unit}).",
            f"**High point:** {dmax:%b %Y} ({vmax:.1f}{unit}).",
        ]
        if pd.notna(delta12):
            bits.append(
                f"**Momentum (12m vs prior 12m):** {delta12:+.1f}{' pp' if unit=='%' else ' min'}."
            )
        if pd.notna(vol):
            if vol >= (2.0 if unit == "%" else 3.0):
                bits.append(f"**Volatility** is noticeable (σ≈{vol:.1f}{' pp' if unit=='%' else ' min'}).")
            else:
                bits.append(f"**Volatility** is limited (σ≈{vol:.1f}{' pp' if unit=='%' else ' min'}).")
        if band_msg:
            bits.append(band_msg)

        tone = _tone_from_delta(delta12)
        callout(":success" if tone == "success" else tone, ":material/trending_up:", " ".join(bits))

# Context card (full-period read)
card(
    icon=":material/bar_chart_4_bars:",
    title="Historical pattern (full period)",
    body_md="""
Over the full horizon, the system settles into a familiar band around **85–90% on-time** in ordinary years.
There is a marked **trough in 2020 (68.3%)** that aligns with the pandemic shock and the temporary
reconfiguration of operations, followed by an **exceptional rebound in 2021 (93.9%)** when a smaller,
tighter offering proved easier to stabilise. Since then, performance has **levelled near ~86%**: below the
post-COVID peak but without signs of structural erosion. The last twelve months add about **+1.4 percentage
points**, a nudge in the right direction despite weather and logistics headwinds.
""",
)

st.divider()

# ==========================================
# Small multiples (by duration class)
# ==========================================
ds = duration_small_multiples(dff).sort_values(["duration_class", "date"])

st.subheader("By duration class")
st.caption("Short, medium, and long journeys can behave differently: compare trends side by side.")

# (Removed the small grey 12-month per-class sentence — replaced by the colored callout below)

# Chart
if not ds.empty:
    fig2 = line_duration(ds, title="On-time arrival % by duration class")
    st.plotly_chart(fig2, width="stretch")
else:
    st.info("Not enough data in the current scope to compare duration classes.")

# --- Rich duration callout (enhanced phrasing) ---
if not ds.empty:
    # Last month snapshot
    latest_month = ds["date"].max()
    snap = ds[ds["date"] == latest_month].dropna(subset=["on_time_pct"])

    # 12-month averages per class
    read12 = (
        ds.dropna(subset=["on_time_pct"])
          .groupby("duration_class", sort=False)
          .apply(lambda g: g.tail(12)["on_time_pct"].mean() if len(g) >= 12 else np.nan)
          .rename("avg12")
          .reset_index()
    )

    bits = []
    tone = "info"

    # Snapshot message
    if not snap.empty:
        best = snap.loc[snap["on_time_pct"].idxmax()]
        worst = snap.loc[snap["on_time_pct"].idxmin()]
        gap = float(best["on_time_pct"] - worst["on_time_pct"])
        if gap >= 2.0:
            bits.append(
                f"**Latest month ({latest_month:%b %Y})** shows a **{gap:.1f} pp** spread: "
                f"best **{best['duration_class']}** ({best['on_time_pct']:.1f}%) vs. lowest **{worst['duration_class']}** ({worst['on_time_pct']:.1f}%)."
            )
            tone = "success" if gap > 0 else "info"
        else:
            bits.append(
                f"**Latest month ({latest_month:%b %Y})** shows **near parity** across classes (spread {gap:.1f} pp)."
            )

    # 12-month structure message
    if not read12.empty and read12["avg12"].notna().any():
        best12 = read12.loc[read12["avg12"].idxmax()]
        worst12 = read12.loc[read12["avg12"].idxmin()]
        gap12 = best12["avg12"] - worst12["avg12"]
        if gap12 >= 2.0:
            bits.append(
                f"Over the **last 12 months**, **{best12['duration_class']}** leads ({best12['avg12']:.1f}%), "
                f"while **{worst12['duration_class']}** trails ({worst12['avg12']:.1f}%) — a **{gap12:.1f} pp** structural gap."
            )
        else:
            bits.append("Over the **last 12 months**, classes are broadly aligned with only minor differences.")

    if bits:
        callout("success" if ("gap" in locals() and gap >= 2.0) or ("gap12" in locals() and gap12 >= 2.0) else "info",
                ":material/segment:",
                " ".join(bits))

# Context card (structural interpretation)
card(
    icon=":material/hourglass_bottom:",
    title="What journey length tells us",
    body_md="""
Journey length matters. **Short (< 1h30)** and **medium (1h30–3h)** trips usually cluster in the **85–90%** range,
while **long trips (> 3h)** are **consistently lower by roughly 2–3 percentage points** and fluctuate more.
That pattern is intuitive: longer distances accumulate more exposure: to infrastructure constraints,
traffic-management conflicts, rolling stock issues, weather. These small multiples are not a side note;
they show that punctuality differences are not just regional: they’re **structural**.
""",
)

st.divider()

st.subheader("To conclude")
card(
    icon=":material/summarize:",
    title="Synthesis & what to explore next",
    body_md="""
Taken together, the overview suggests a network that **absorbed a major shock**, rebounded, and now holds a
steady state with **meaningful variation by journey length**. Most pain for travellers happens as **delay**
rather than cancellations; the average delay when late is non-trivial, so outliers and recurrent weak spots matter.
The natural next question is **where** this variance concentrates and **why**: which lines sit at the extremes,
and what mechanisms drive them.  

We’ll answer that in **Routes Compare** (to locate the best and worst performers in your scope), then in
**Causes & Severity** (to decompose *why* and *how bad* delays get), before grounding the picture in **Geo View**
to see how geography shapes performance.
""",
)