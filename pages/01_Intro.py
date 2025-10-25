import streamlit as st
from pathlib import Path
from utils.filters import intro_sidebar

st.set_page_config(page_title="Intro & Context", page_icon=":material/train:", layout="wide")

# Page-specific sidebar
intro_sidebar()

st.write("# Introduction & Context")

# Hook
left, right = st.columns([3, 1], vertical_alignment="center")
with left:
    st.markdown(
        """
**Hi!** I'm Doryan Denis, the secretary of **EFREI TC**, our school's student community about public transport.  
We gather students who enjoy discussing networks, planning trips, and advocating for better transit.  

This dashboard comes from that passion: exploring **TGV performance** — not just *if* trains are on time,
but **where, when, and why they aren’t** so we can reason about improvements.
        """
    )
with right:
    logo_path = Path("assets/efrei_tc.png")
    if logo_path.exists():
        st.image(str(logo_path), width=200, output_format="PNG")
    else:
        st.caption("EFREI TC logo missing (assets/efrei_tc.png).")

st.divider()

# Quick context
st.subheader("Context")
st.markdown(
    """
This analysis follows **AQST** (Agence Qualité de Service dans les Transports) rules used for
performance monitoring. We work at the liaison level (origin–destination pair) and per month,
with a focus on three journey duration classes: `< 1h30`, `1h30–3h`, `> 3h`.
"""
)

# Objectives
st.subheader("Objectives")
st.markdown(
    """
1. **Measure** TGV punctuality at a glance and over time.  
2. **Compare** routes to identify **best** and **worst** performing liaisons.  
3. **Explain** delays via **cause composition** and **severity** (≥15/30/60 min).  
4. **Visualize** the network on a map to spot geographic patterns.
"""
)

# Audience & Key Takeaways
st.subheader("Audience & Key Takeaways")
st.markdown(
    """
This dashboard is intended for **data analysts, transport planners, and public transport enthusiasts**
(like my EFREI TC colleagues) interested in the operational realities of a high-speed rail network.

**The key takeaways are:**
- **Performance is not uniform:** A single "on-time" number hides vast differences between routes.
- **Complexity is a key driver:** Long-distance, international, and cross-country routes face structural challenges
  that shorter, high-frequency routes do not.
- **The "Why" matters:** `Infrastructure` and `Traffic Management` are often the dominant causes of delays,
  not passenger-related issues.
- **Problems are concentrated:** A small number of routes and hubs (especially Paris)
  can be responsible for a disproportionate share of network-wide delays.
"""
)

# Data caveats & scope
st.subheader("Data caveats & scope")
st.warning(
    "**Do not recompute a single 'global TGV punctuality' here.** "
    "A train can appear in multiple liaisons; the official KPI uses unique trains.",
    icon=":material/warning:",
)
st.markdown(
    """
- **Granularity:** monthly by liaison; KPIs are aggregated with appropriate denominators (e.g., weighted means for delayed-train averages).  
- **Durations:** duration classes are categorical, they’re not continuous time bins.  
- **Coverage:** some stations may lack coordinates initially; these liaisons won’t appear in the Geo view.  
- **Interpretation:** cancel rates and severe-delay counts can move independently from on-time %, consider them together.
"""
)

# Narrative roadmap
st.subheader("How to read this dashboard")
st.markdown(
    """
- Start with **Overview** to see trends and duration-class differences.  
- Go to **Routes Compare** to rank liaisons by a chosen KPI and spot outliers.  
- Open **Causes & Severity** to understand *why* delays happen and how severe they get.  
- Use **Geo View** to relate performance to geography (hubs, long-haul vs cross-country, etc.).  
- **Data Quality** helps inspect coverage and potential issues in the source.
"""
)

# Understanding the visuals (same design language as other pages)
st.markdown("### Understanding the visuals")

# Colored box
st.success(
    """
:material/auto_graph: **Colored boxes and charts = dynamic analysis.** These elements **react to your selections** in the sidebar (date range, service, duration class, A↔B merge…).  
What you see is the **live view** of the filtered data. Change a filter, and they **update instantly**.
"""
)

# Plain bordered card
with st.container(border=True):
    st.markdown(
        """
:material/description: **Plain, bordered cards = baseline narratives.** These summaries are written from the **default results** (no custom filters applied).  
They provide a **stable reference** for interpretation, so you can compare your dynamic view
to the **unchanged baseline** shown in these neutral cards.
        """
    )

st.divider()

st.subheader("Tips")
st.markdown(
    """
- The **left sidebar** always shows **only the relevant filters** for the current page.  
- Use the **date range** (months) and **Service** / **Duration class** to scope your view.  
- On some pages you can **treat A→B and B→A as the same** liaison to merge bidirectional traffic.
"""
)

# show current data coverage
opts = st.session_state.get("filters_catalog", {}).get("date_options", [])
if opts:
    st.caption(f"Data coverage: **{opts[0]} → {opts[1]}** (monthly).")