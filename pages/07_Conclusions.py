import streamlit as st
from utils.filters import conclusions_sidebar

st.set_page_config(page_title="Conclusions", page_icon=":material/check_circle:", layout="wide")
conclusions_sidebar()

def analysis_card(title: str, body_md: str, icon: str = ":material/analytics:"):
    """Creates a plain bordered container with an icon, bold title, and markdown body."""
    with st.container(border=True):
        st.markdown(f"{icon} **{title}**")
        st.markdown(body_md)

# Header
st.markdown("# Conclusions & Next Steps")
st.markdown(
    """
This analysis set out to explore TGV performance not just *if* trains are on time,
but **where, when, and why they aren’t**. After navigating through the dashboard, from the
high-level trends to the granular causes, we can now synthesize the key findings.
"""
)

st.divider()

# Insights
st.subheader("Key Insights: The Story in Four Acts")
st.markdown(
    """
Across the various pages, four major themes emerged that define the TGV network's performance.
"""
)

c1, c2 = st.columns(2)

with c1:
    analysis_card(
        icon=":material/compare_arrows:",
        title="Insight 1: Performance is stable but polarized",
        body_md="""
        The network-wide baseline is a respectable **85-90% on-time rate**, with most disruption
        felt as delay (avg. ~34 mins) rather than cancellation. However, this average masks a
        strong polarization.
        
        As seen in **Routes Compare**, the **Top 10 routes** (mostly high-frequency, Paris-centric)
        achieve >90% punctuality, while the **Bottom 10** (long-haul, cross-country, or international)
        struggle at 75-80%.
        """
    )

with c2:
    analysis_card(
        icon=":material/route:",
        title="Insight 2: It's about *Complexity*, not distance",
        body_md="""
        The **Overview** page immediately showed that **long journeys (> 3h) are structurally 2-3 percentage
        points less punctual** than shorter trips.
        
        However, the **Geo View** analysis revealed that simple distance has only a **weak negative correlation (r = -0.21)**
        with punctuality. The *real* drivers are journey **complexity**:
        - **Service Type:** International routes suffer more from `Traffic Management`.
        - **Exposure:** Long-haul routes accumulate more risk from `Rolling Stock` and `External` causes.
        """
    )

c3, c4 = st.columns(2)

with c3:
    analysis_card(
        icon=":material/target:",
        title="Insight 3: Delays are highly concentrated",
        body_md="""
        The problem is not evenly spread. The **Routes Compare** concentration curve
        was definitive: **the top 20% of problematic liaisons account for nearly 50% of all late
        arrivals**.
        
        Geographically, the **Geo View** "Late Density" map identified a primary hotspot:
        the **Paris hub**. Paris Lyon station, in particular, is the network's critical node,
        serving 25 distinct liaisons—more than double the next-closest hub.
        """
    )

with c4:
    analysis_card(
        icon=":material/construction:",
        title="Insight 4: The *Why* is clear: Infrastructure & Traffic",
        body_md="""
        These two categories consistently dominate the delay mix. Crucially, they also
        drive the **most severe delays (≥60 minutes)**.
        
        The most telling visual is the "Reliability × severity" scatter plot in
        **Causes & Severity**. It shows that liaisons dominated by **`Traffic Management`**
        are clustered in the worst-performing quadrant (low punctuality, high severity).
        """
    )


st.divider()

# Implications
st.subheader("Implications & Diagnosis")

st.markdown(
    """
These insights lead to a clear diagnosis of the network:

1.  **The TGV network is generally robust but has predictable, structural vulnerabilities.** The passenger experience is not uniform. A traveler on a *Paris → Nancy* route has a fundamentally different (and better) experience than one on an *Italy → Paris Lyon* route.

2.  **The network's star-shaped, Paris-centric design is its greatest strength and greatest weakness.** It enables massive connectivity (as seen in **Geo View**) but also creates a central bottleneck where delays can easily cascade. The busiest corridors are not the most punctual.

3.  **The problem is not a thousand small cuts; it's a few deep ones.** The concentration of delays implies that solving issues on a small number of key corridors and tackling core `Traffic Management` issues would have an outsized, network-wide positive impact.
"""
)

st.divider()

# Limitations
st.subheader("Limitations & Known Issues")
st.markdown("For full transparency, the following limitations should be considered when interpreting these results:")

analysis_card(
    icon=":material/warning:",
    title="Data Scope, Quality, and Proxies",
    body_md="""
- **Scope:** This analysis is at the **liaison-month level**. As noted in the **Intro**, the KPIs here (like on-time %) cannot be re-aggregated to calculate a single "global TGV punctuality" figure, as official KPIs use unique train IDs which are not present in this dataset.

- **Logical Inconsistency:** The **Data Quality** page revealed a recurring issue where `avg_delay_all_min > avg_delay_arr_delayed_min`. This suggests an upstream data calculation error and means that "Average arrival delay" metrics should be treated with caution.

- **Missing Data:**
    - **Historical:** Several core metrics (like `late_arr_count` and `late_over_15_count`) have missing data for older periods, as seen in the "Missingness" tab of the **Data Quality** page.
    - **Contextual:** All free-text comment fields are >93% empty and provide no qualitative insight.
"""
)

st.divider()

# Next Steps
st.subheader("Recommendations & Next Steps")

st.markdown(
    """
Based on this analysis, we can propose targeted actions for both operations and future analysis.
"""
)

c1_next, c2_next = st.columns(2)

with c1_next:
    with st.container(border=True):
        st.markdown("#### 1. For Operations & Strategy")
        st.markdown(
            """
            - **Prioritize the "Red Zone":** Focus resources on the **top 20% of liaisons**
              driving 50% of delays, as identified in **Routes Compare**.
            
            - **Tackle Traffic Management:** The `Traffic Management` cause is the strongest
              predictor of poor performance. This should be the primary focus for
              internal improvement, far ahead of passenger or station-related issues.
            
            - **De-risk Long-Haul & International:** Since these routes are structurally
              vulnerable to `Rolling Stock` and `Traffic` issues, increase
              maintenance buffers, resilience planning (e.g., for winter), and
              cross-border coordination.
            
            - **Manage the Paris Hub:** Given its role as the primary delay hotspot,
              any effort to de-conflict schedules or improve infrastructure resilience in the Paris
              region will benefit the entire network.
            """
        )

with c2_next:
    with st.container(border=True):
        st.markdown("#### 2. For Future Analysis & Communication")
        st.markdown(
            """
            - **Deconstruct "Traffic Management":** This category is too broad. A
              deeper analysis is needed: is this due to signaling, crew scheduling, or
              conflicts with regional/freight traffic?
            
            - **Set Transparent Expectations:** Use these insights for passenger communication.
              Be transparent that for a trip like *Paris ↔ Geneva* (a frequent outlier),
              the risk of delay is higher and explain *why* (e.g., cross-border coordination).
            
            - **Improve Data Quality:** The logical inconsistency where
              `avg(all) > avg(delayed)` should be investigated and corrected upstream
              to improve the accuracy of mean delay metrics.
            
            - **Track Interventions:** Use this dashboard as a baseline. If an intervention
              is made on `Traffic Management`, we should be able to see its impact in the
              **Causes & Severity** charts in the following year.
            """
        )

st.divider()
st.success(
    """
    **Final Thought:** The TGV network's performance is a complex system, but its
    weaknesses are not random. They are structural, concentrated, and—most importantly—
    identifiable. By focusing on the specific corridors and root causes highlighted in this
    dashboard, targeted improvements can be made to enhance reliability for millions of passengers.
    """
)