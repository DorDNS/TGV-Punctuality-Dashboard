import streamlit as st
import numpy as np 
import pandas as pd
from utils.filters import causes_sidebar
from utils.compute import (
    apply_overview_filters,
    causes_composition,
    severe_counts,
    causes_pivot_monthly,          
    causes_by_attr,                
    severity_profile_by_cause,     
    liaison_cause_dominance_summary 
)
from utils.viz import (
    stacked_causes,
    grouped_severity,
    heatmap_causes_month,          
    stacked_100_by_attr,           
    grouped_severity_by_cause,     
    scatter_dominant_cause         
)

st.set_page_config(page_title="Causes & Severity", page_icon=":material/stacked_bar_chart:", layout="wide")

# helper: info card
def card(title: str, body_md: str, icon: str = ":material/insights:"):
    with st.container(border=True):
        st.markdown(f"{icon} **{title}**")
        st.markdown(body_md)

# colored callout box
def callout(tone: str, icon: str, text_md: str):
    box = getattr(st, tone, st.info)
    box(f"{icon}  {text_md}")

def _tone_delta(delta: float | None, *, good_when_down: bool, hi: float = 0.03, lo: float = -0.03) -> str:
    if delta is None or (isinstance(delta, float) and np.isnan(delta)):
        return "info"
    if good_when_down:
        if delta <= lo:  
            return "success"
        if delta >= hi:  # up by >= 3 pp
            return "warning"
    else:
        if delta >= hi:
            return "success"
        if delta <= lo:
            return "warning"
    return "info"

def _weighted_cause_shares(df):
    """
    Weighted average cause shares over the given dataframe using late_arr_count as weights.
    Returns a pandas Series indexed by pretty cause labels in [0..1] share.
    """
    if df is None or df.empty:
        return None
    cause_cols = [c for c in [
        "pct_cause_external","pct_cause_infra","pct_cause_traffic",
        "pct_cause_rollingstock","pct_cause_station_reuse","pct_cause_passengers"
    ] if c in df.columns]
    if not cause_cols or "late_arr_count" not in df.columns:
        return None
    w = df["late_arr_count"].fillna(0).astype(float)
    den = w.sum()
    if den <= 0:
        return None
    num = df[cause_cols].multiply(w, axis=0).sum() / den
    label_map = {
        "pct_cause_external": "External",
        "pct_cause_infra": "Infrastructure",
        "pct_cause_traffic": "Traffic management",
        "pct_cause_rollingstock": "Rolling stock",
        "pct_cause_station_reuse": "Station ops & reuse",
        "pct_cause_passengers": "Passengers / PSH / connections",
    }
    num.index = [label_map.get(i, i) for i in num.index]
    return num.sort_values(ascending=False)

# Sidebar
causes_sidebar()

st.markdown("# Causes & Severity")
st.caption("What drives delays and how severe they are in the selected scope.")

df = st.session_state.get("df_clean", None)
if df is None or df.empty:
    st.error("Data not loaded.")
    st.stop()

dff = apply_overview_filters(df, st.session_state)
if dff.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

breakdown = st.session_state.get("causes_breakdown", "Month")
top_n = st.session_state.get("causes_top_n", 10) if breakdown == "Liaison" else None
bucket = st.session_state.get("severity_bucket", "≥15")

# Cause mix (stacked)
st.subheader("Cause mix in context")
st.caption("Weighted composition of delay causes by the selected breakdown "
           "(Month or Liaison). Percentages sum to 100% within each group.")

comp = causes_composition(dff, breakdown=breakdown, top_n=top_n)
if comp.empty:
    st.info("No cause composition data available.")
else:
    horizontal = (breakdown == "Liaison")
    fig_c = stacked_causes(comp, title=f"Delay causes composition by {breakdown.lower()}", horizontal=horizontal)
    if fig_c:
        st.plotly_chart(fig_c, use_container_width=True)

try:
    # last-12m vs prior-12m 
    if "date" in dff.columns:
        dff_sorted = dff.sort_values("date")
        last_date = dff_sorted["date"].max()
        cut_12 = last_date - pd.DateOffset(months=12)
        cut_24 = last_date - pd.DateOffset(months=24)

        s_last12 = _weighted_cause_shares(dff_sorted[dff_sorted["date"] > cut_12])
        s_prev12 = _weighted_cause_shares(dff_sorted[(dff_sorted["date"] > cut_24) & (dff_sorted["date"] <= cut_12)])

        if s_last12 is not None:
            top_cause, top_share = s_last12.index[0], float(s_last12.iloc[0])
            msg = f"**Last 12 months** — dominant cause: **{top_cause}** (**{top_share*100:.0f}%** of late-arrival share)."
            if s_prev12 is not None and top_cause in s_prev12.index:
                delta = float(s_last12[top_cause] - s_prev12[top_cause])
                tone = _tone_delta(delta, good_when_down=False, hi=0.03, lo=-0.03)
                sign = f"{delta:+.1%}".replace("%"," pp")
                msg += f" Change vs prior 12m: **{sign}**."
            else:
                tone = "info"
            callout(tone, ":material/insights:", msg)
except Exception:
    pass

card(
    title="How to read the monthly cause mix",
    icon=":material/timeline:",
    body_md="""
This first graph provides an overview of the monthly evolution of the **overview of causes of delays** since 2018.
We can see that the **overall structure is relatively stable**, with a regular alternation between **infrastructure** causes (light blue) and **traffic** causes (red), which together account for the majority of delays.
However, certain specific episodes stand out: for example, **peaks in external causes** (dark blue) in 2020 and 2023 suggest disruptions linked to climatic or social events.
The proportion of **causes related to rolling stock** (pink) remains high and stable over time, reflecting a structural component of the network.
Finally, the growing proportion of **causes related to passengers or connections** (light green) in the recent period indicates a post-Covid effect: a resumption of traffic and pressure on connections.
This graph thus establishes the temporal basis: delays on the TGV network result from a complex balance between **structural** factors (infrastructure, rolling stock) and **operational** factors (traffic, passengers).
"""
)

st.divider()

# Cause seasonality (heatmap)
st.subheader("Seasonality of causes")
st.caption("Weighted cause mix by month (shares over late arrivals). Look for winter spikes, summer maintenance, etc.")

pivot = causes_pivot_monthly(dff)
if pivot.empty:
    st.info("No monthly cause breakdown available.")
else:
    fig_hm = heatmap_causes_month(pivot, title="Cause mix over time")
    if fig_hm:
        st.plotly_chart(fig_hm, use_container_width=True)

try:
    if not pivot.empty:
        # find the (cause, month) cell with the highest share
        tidy = pivot.reset_index().melt(id_vars="date", var_name="cause", value_name="share")
        tidy = tidy.dropna(subset=["share"])
        if not tidy.empty:
            idx = tidy["share"].idxmax()
            row = tidy.loc[idx]
            tone = "warning" if float(row["share"]) >= 0.35 else "info"  
            callout(
                tone,
                ":material/trending_up:",
                f"**Seasonal spike** — **{row['cause']}** peaked around **{row['date']:%b %Y}** "
                f"(~**{row['share']*100:.0f}%** of the monthly mix)."
            )
except Exception:
    pass

card(
    title="What the heatmap adds",
    icon=":material/calendar_month:",
    body_md="""
This heat map refines the previous reading by highlighting the **seasonality of causes**.
The **darker shades** represent higher monthly shares: we can see **winter periods with a higher density of external causes**, often linked to bad weather, and **summer lows** where these disruptions shift towards the *infrastructure* category — consistent with summer maintenance work.
Other causes, notably *traffic* and *rolling stock*, remain diffuse and less seasonal, confirming their continuous nature.
This visualisation therefore illustrates that, even if the annual distribution remains stable, **internal dynamics vary according to the seasons**, a key factor for resource planning and maintenance.
"""
)

st.divider()

# Composition by segment
st.subheader("Cause structure by segment")
st.caption("Compare cause mix across services and journey lengths (100% stacked).")

comp_service = causes_by_attr(dff, "service")
comp_duration = causes_by_attr(dff, "duration_class")

c1, c2 = st.columns(2)
with c1:
    if comp_service.empty:
        st.info("No service-level cause composition.")
    else:
        st.plotly_chart(stacked_100_by_attr(comp_service, "Cause composition by service", horizontal=True),
                        use_container_width=True)
with c2:
    if comp_duration.empty:
        st.info("No duration-class cause composition.")
    else:
        st.plotly_chart(stacked_100_by_attr(comp_duration, "Cause composition by duration class", horizontal=True),
                        use_container_width=True)

try:
    # Build quick contrasts on External / Rolling stock between >3h and <1h30
    if not comp_duration.empty and "group" in comp_duration and "pct" in comp_duration:
        w = comp_duration.pivot_table(index="group", columns="cause", values="pct", aggfunc="mean")
        if ("> 3h" in w.index) and ("< 1h30" in w.index):
            for cause in ["External", "Rolling stock"]:
                if cause in w.columns:
                    diff = float(w.loc["> 3h", cause] - w.loc["< 1h30", cause])
                    tone = _tone_delta(diff, good_when_down=False, hi=0.03, lo=-0.03)
                    callout(
                        tone,
                        ":material/compare_arrows:",
                        f"**{cause}** share is **{diff:+.1%}** higher on **long trips (>3h)** than **short (<1h30)**."
                        .replace("%"," pp")
                    )
                    break
except Exception:
    pass

card(
    title="Cause structure by segment — service & journey length",
    icon=":material/segment:",
    body_md="""
This double graph compares the composition of causes according to **type of service (domestic vs international)** and **journey length**.
The differences between services are small but noticeable: **international** lines have a higher proportion of **traffic-related delays (≈30%)**, reflecting coordination constraints between national networks, while **domestic** lines show a more even balance between internal and external causes.
On the other hand, the criterion of **duration** reveals a clear hierarchy:

* **Short journeys (< 1h30)** are dominated by *traffic* and *infrastructure* causes, reflecting the density of traffic on suburban routes.
* **Long journeys (> 3 hours)** see an increase in the proportion of *external causes* and *rolling stock*, reflecting increased sensitivity to climatic and technical hazards.

This breakdown highlights a gradient of complexity: **the longer the journey, the more structural and difficult to reduce the causes of delays become**.
"""
)

st.divider()

# Severity profile by cause
st.subheader("Which causes drive severe delays?")
st.caption("Share of each severity bucket attributed to causes (weighted by late arrivals).")

sev_profile = severity_profile_by_cause(dff)
if sev_profile.empty:
    st.info("No severity-by-cause profile available.")
else:
    st.plotly_chart(grouped_severity_by_cause(sev_profile, "Severity profile by cause"),
                    use_container_width=True)

try:
    if not sev_profile.empty and {"bucket","cause","pct"}.issubset(sev_profile.columns):
        # find dominant cause within ≥60 bucket
        tail = sev_profile[sev_profile["bucket"] == "≥60"]
        if not tail.empty:
            r = tail.sort_values("pct", ascending=False).iloc[0]
            callout(
                "warning",
                ":material/more_time:",
                f"In the **≥60 min** tail, the dominant driver is **{r['cause']}** "
                f"(~**{float(r['pct'])*100:.0f}%** of that bucket)."
            )
except Exception:
    pass

card(
    title="Which causes push delays into severe territory?",
    icon=":material/more_time:",
    body_md="""
This visualisation answers a key question: *what causes the longest delays?*
We can see that the categories **External**, **Infrastructure** and **Traffic** top each severity level, with almost identical shares for the three thresholds (≥15, ≥30, ≥60 min).
This suggests that these causes are distinguished not only by their frequency but also by their **ability to generate significant delays**, which are often correlated: an infrastructure failure can cause a chain reaction of congestion and diversions.
Conversely, the causes *Station ops & reuse* and *Passengers/Connections* appear infrequently in the most severe delays — their impact remains localised and limited in time.
This graph therefore allows priorities to be ranked: the main levers for reducing **serious delays** lie primarily in **infrastructure resilience and traffic management**.
"""
)

# Where and when severe delays occur
st.subheader("Where and when severe delays occur")
st.caption(f"Counts of severe late arrivals ({bucket}) by the selected breakdown "
           "(Month or Liaison). Use this alongside the cause profile above to prioritize actions.")

sev = severe_counts(dff, breakdown=breakdown, bucket=bucket, top_n=top_n)
if sev.empty:
    st.info("No severe delays data available.")
else:
    horizontal = (breakdown == "Liaison")
    fig_s = grouped_severity(sev, title=f"Severe delays {bucket} by {breakdown.lower()}", horizontal=horizontal)
    if fig_s:
        st.plotly_chart(fig_s, use_container_width=True)

try:
    if not sev.empty and "group" in sev and "count" in sev:
        # If monthly: groups are datetimes; else counts by liaison
        s = sev.sort_values("group")
        if s["group"].dtype.kind in ("M",): 
            last12 = s["count"].tail(12).sum()
            prev12 = s["count"].iloc[:-12].tail(12).sum() if len(s) >= 24 else np.nan
        else:
            last12 = s.sort_values("count", ascending=False)["count"].head(12).sum()
            prev12 = s.sort_values("count", ascending=False)["count"].iloc[12:24].sum() if len(s) >= 24 else np.nan
        if not np.isnan(prev12) and prev12 > 0:
            delta = (last12 - prev12) / prev12
            tone = _tone_delta(delta, good_when_down=True, hi=0.10, lo=-0.10)  
            sign = f"{delta:+.0%}"
            callout(tone, ":material/auto_graph:", f"**Severe events momentum** (latest vs prior window): **{sign}**.")
except Exception:
    pass

card(
    title="Where and when severe delays occur",
    icon=":material/bar_chart:",
    body_md="""
The timeline graph of severe delays puts the evolution of disruption volumes since 2018 into perspective.
The overall trend remains **relatively stable**, at around 3,000 to 4,000 delays per month, but a few notable episodes stand out:

* **Sharp peaks in 2018–2019** (social unrest and extreme weather conditions).
* A **sharp drop in 2020**, linked to the pandemic and reduced traffic.
* A **gradual recovery from 2021**, followed by a **sharp peak in early 2023**, probably correlated with major works or incidents on the south-eastern routes.

This representation highlights that, despite efforts to improve reliability, the frequency of significant delays remains **structurally high**, suggesting a **recurring vulnerability** of the network to external and logistical disruptions.
"""
)

st.divider()

# Reliability × severity by dominant cause
st.subheader("Reliability × severity by dominant cause")
st.caption("Each liaison is colored by its dominant cause (weighted by late arrivals). "
           "Bubble size ∝ number of late arrivals. Use the quadrant lines as rough targets (90% / 30 min).")

dom = liaison_cause_dominance_summary(dff, treat_bidirectional=bool(st.session_state.get("treat_bidirectional", True)))
if dom.empty:
    st.info("No liaison-level dominant cause summary available.")
else:
    fig_dom = scatter_dominant_cause(dom, title="On-time vs. severity by dominant cause")
    if fig_dom:
        st.plotly_chart(fig_dom, use_container_width=True)

try:
    if dom is not None and not dom.empty:
        cols = set(dom.columns)

        # Accept either naming
        ycol = None
        for c in ("avg_arr_delay_delayed", "avg_delay_arr_delayed_min"):
            if c in cols:
                ycol = c
                break

        count_col = None
        for c in ("late_arr_count", "late_arrivals", "late_count"):
            if c in cols:
                count_col = c
                break

        # Require on-time and ycol
        if "on_time_pct" in cols and ycol is not None and count_col is not None:
            dfq = dom[["on_time_pct", ycol, count_col]].dropna()
            if not dfq.empty:
                bad = dfq[(dfq["on_time_pct"] < 90.0) & (dfq[ycol] > 30.0)]
                n_bad = int(bad.shape[0])
                total_late = dfq[count_col].sum()
                share_bad = (bad[count_col].sum() / total_late) if total_late > 0 else float("nan")

                tone = "warning" if n_bad >= 8 or (not np.isnan(share_bad) and share_bad >= 0.30) else "info"
                msg = f"**{n_bad} liaison(s)** sit in the **risk quadrant** (on-time < 90% & severity > 30 min)"
                if not np.isnan(share_bad):
                    msg += f", representing ~**{share_bad*100:.0f}%** of late arrivals."
                callout(tone, ":material/priority_high:", msg)
except Exception:
    pass

card(
    title="Reliability × severity by dominant cause",
    icon=":material/bubble_chart:",
    body_md="""
Finally, the scatter plot links **reliability (punctuality rate)** and **average severity of delays**, colouring each connection according to its dominant cause.
The trends are clear:

* Connections dominated by **traffic (red)** are concentrated in the most fragile area — **low punctuality (< 85%) and high delays (> 35 min)**.
* Connections linked to **infrastructure (light blue)** or **rolling stock (dark blue)** show moderate dispersion but significant average delays (~30 min), typical of occasional but serious breakdowns.
* Finally, a few connections with **external causes** appear to be highly variable, with some performing very well and others being severely affected.
  
This reading highlights a clear inverse correlation: **the more the dominant cause is internal to the system (traffic, rolling stock, infrastructure), the more overall performance is penalised**.
This is a powerful diagnostic tool for targeting areas of fragility: the **red lines on the left** (dominant traffic, low reliability) are the **priorities for action** to improve the regularity of the network.
"""
)
