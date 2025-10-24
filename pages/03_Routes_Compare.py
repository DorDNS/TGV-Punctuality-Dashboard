import streamlit as st
import math
import numpy as np
import pandas as pd
from utils.filters import routes_sidebar
from utils.compute import (
    apply_overview_filters,
    liaison_ranking,
    delay_distribution,
    liaison_summary,
)
from utils.viz import (
    bar_ranking,
    box_delay_distribution,
    scatter_performance,
    lorenz_late_share,
)

st.set_page_config(page_title="Routes Compare", page_icon=":material/route:", layout="wide")

# ---------- small helpers: narrative cards ----------
def card(title: str, body_md: str, icon: str = ":material/insights:"):
    with st.container(border=True):
        st.markdown(f"{icon} **{title}**")
        st.markdown(body_md)

# --- colored callouts (same spirit as Overview) ----------------------------
def _tone_from(value: float | None, *, good: bool = True, lo: float | None = None, hi: float | None = None) -> str:
    """
    Heuristic: choose a tone depending on whether higher is good or bad.
    - If good=True, higher is better; else lower is better.
    - lo/hi optional thresholds to bias success/warning.
    """
    if value is None:
        return "info"
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return "info"
    if hi is not None and value >= hi:
        return "success" if good else "warning"
    if lo is not None and value <= lo:
        return "warning" if good else "success"
    return "info"

def callout(tone: str, icon: str, text_md: str):
    """Show a colored box with an icon and markdown text."""
    box = getattr(st, tone, st.info)
    box(f"{icon}  {text_md}")

def _pct(x: float | None) -> str:
    return "—" if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) else f"{x:.1f}%"

# ---------- sidebar & header ----------
routes_sidebar()
st.markdown("# Routes Compare")
st.caption("Compare punctuality and delay severity across TGV liaisons.")

# ---------- load & filter ----------
df = st.session_state.get("df_clean", None)
if df is None or df.empty:
    st.error("Data not loaded.")
    st.stop()

dff = apply_overview_filters(df, st.session_state)
if dff.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

metric = st.session_state["metric"]
treat_bi = bool(st.session_state.get("treat_bidirectional", False))
color_by = st.session_state.get("color_by", "service")  # enforced to "service" or "duration_class" in sidebar

# =====================================================
# A) Top / Bottom rankings
# =====================================================
st.subheader("Top & Bottom rankings")
st.caption(
    "Identify the strongest and weakest liaisons for the **selected metric**. "
    "Use the sidebar to switch the ranking metric, scope, and A→B vs A↔B."
)

top_df, bottom_df = liaison_ranking(dff, metric, treat_bidirectional=treat_bi)
if not top_df.empty and not bottom_df.empty:
    fig_top, fig_bottom = bar_ranking(top_df, bottom_df, metric)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(fig_top, use_container_width=True)
    with c2:
        st.plotly_chart(fig_bottom, use_container_width=True)
else:
    st.warning("Not enough data to compute rankings.")

# ---- dynamic local read for rankings (colored callout — rich prose) ------
try:
    top_name  = str(top_df["rank_metric"].idxmax())
    top_value = float(top_df.loc[top_name, "rank_metric"])
except Exception:
    top_name, top_value = None, np.nan

try:
    bot_name  = str(bottom_df["rank_metric"].idxmin())
    bot_value = float(bottom_df.loc[bot_name, "rank_metric"])
except Exception:
    bot_name, bot_value = None, np.nan

gap = (top_value - bot_value) if (np.isfinite(top_value) and np.isfinite(bot_value)) else np.nan

if metric == "On-time arrival %":
    tone = "success" if np.isfinite(top_value) and top_value >= 90 else ("warning" if np.isfinite(bot_value) and bot_value < 80 else "info")
    msg = (
        f"With the current scope, **{top_name}** leads the table at **{top_value:.1f}% on-time**, whereas "
        f"**{bot_name}** closes it at **{bot_value:.1f}%**. The **{gap:.1f}-point** gap suggests that performance "
        f"is not evenly distributed across corridors. "
        f"{'Merging A↔B smooths some directional swings; persistent gaps are therefore structural.' if treat_bi else 'Because A→B and B→A are distinct, part of this spread can come from real directional asymmetries.'}"
    )
elif metric == "Cancel rate %":
    tone = "warning" if np.isfinite(bot_value) and bot_value >= 5 else "info"
    msg = (
        f"On cancellations, the best performer **{top_name}** sits at **{top_value:.1f}%**, while **{bot_name}** reaches "
        f"**{bot_value:.1f}%**. Above **5%**, cancellations start to distort the customer experience; targeting those "
        f"routes first will likely yield visible gains."
    )
else:  # Avg delay (delayed trains)
    tone = "warning" if np.isfinite(bot_value) and bot_value >= 35 else "info"
    msg = (
        f"Considering **average delay when late**, **{top_name}** is most manageable (≈ **{top_value:.1f} min**), "
        f"while **{bot_name}** faces heavier severity (≈ **{bot_value:.1f} min**). Once the mean delay exceeds "
        f"**35 minutes**, even punctual lines feel unreliable when disruption occurs."
    )

callout(tone, ":material/flag:", msg)

# Narrative — Rankings
if treat_bi:
    card(
        title="What the rankings say (A↔B merged)",
        icon=":material/leaderboard:",
        body_md=(
            """
Grouping connections in a **bidirectional** format (A ↔ B) helps to smooth out the directional effects observed previously.
The **best performance** remains centred on the major **Parisian** routes, with pairs such as *Nancy ↔ Paris Est*, *Brest ↔ Paris Montparnasse* and *Dijon Ville ↔ Paris Lyon*, all above **90% punctuality**. The ranking is now dominated by **stable connections in both directions**, a sign of operational balance: local asymmetries are neutralised when considering the line as a whole.

The **bottom 10** remains largely composed of routes in the **south-east** (*Lyon ↔ Marseille*, *Lyon ↔ Montpellier*) or **long, cross-country connections** such as *Marseille ↔ Tourcoing* or *Italy ↔ Paris Lyon*. These lines often have punctuality rates below **80%**, confirming that length and geographical complexity remain major factors of vulnerability.
Overall, the A↔B merger has **raised the extreme scores**: some connections that were previously very unbalanced in one direction now compensate for each other, revealing a more homogeneous picture, but one that still varies greatly depending on the area of the network.
            """
        ),
    )
else:
    card(
        title="What the rankings say (A→B distinct)",
        icon=":material/leaderboard:",
        body_md=(
            """
The two ranking charts highlight a **strong polarisation** between the best and worst connections in terms of punctuality.
The **Top 10** connections are almost all concentrated around **Paris**, with well-established routes such as *Paris Est → Nancy* or *Paris Lyon → Dijon Ville*, generally exceeding **90% punctuality**. These results reflect robust organisation on high-frequency routes, where operational margins and equipment redundancy reduce the risk of disruption.

Conversely, the **Bottom 10** shows routes that are often long or more complex, such as *Lyon Part Dieu → Marseille St Charles* or *Italy → Paris Lyon*, with rates close to **75–80%**. These routes combine **infrastructure and inter-network coordination constraints**, particularly on international or very busy lines. The contrast of around **10 to 15 points** between the extremes highlights that performance is not uniform: some connections remain structurally more vulnerable than others.
            """
        ),
    )

st.divider()

# =====================================================
# B) Reliability vs Severity (scatter)
# =====================================================
st.subheader("Reliability vs. severity")
st.caption(
    "Each bubble is a liaison (or a bidirectional pair). **X** = on-time %, **Y** = average delay when late. "
    "Dashed guides mark **90%** on-time and **30 min** severity. Coloring is set in the sidebar."
)

summ = liaison_summary(dff, treat_bidirectional=treat_bi)
if not summ.empty:
    fig_scatter = scatter_performance(summ, color_by=color_by, x_ref=90.0, y_ref=30.0)
    if fig_scatter:
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Not enough data to plot the scatter.")
else:
    st.info("No liaison summary could be computed for the current scope.")

# ---- dynamic local read for scatter (rich prose) --------------------------
on_col  = "on_time_pct" if "on_time_pct" in summ.columns else None
sev_col = "avg_delay_arr_delayed_min" if "avg_delay_arr_delayed_min" in summ.columns else None

good_share = None
if on_col and sev_col and len(summ):
    mask = summ[on_col].ge(90) & summ[sev_col].le(30)
    good_share = float(mask.mean() * 100.0)

extra = ""
if color_by == "service" and on_col and sev_col:
    comp = (summ.groupby("service")[[on_col, sev_col]]
                 .median()
                 .rename(columns={on_col:"med_on", sev_col:"med_sev"}))
    if "National" in comp.index and "International" in comp.index:
        n_on, n_sev = comp.loc["National", ["med_on","med_sev"]]
        i_on, i_sev = comp.loc["International", ["med_on","med_sev"]]
        extra = (
            f" Median profile — **National**: ~**{n_on:.0f}%** on-time, **{n_sev:.0f} min**; "
            f"**International**: ~**{i_on:.0f}%**, **{i_sev:.0f} min**. "
            f"{'The gap narrows once A↔B are merged.' if treat_bi else 'The split is clearer when directions are separated.'}"
        )
elif color_by == "duration_class" and on_col and sev_col:
    comp = (summ.groupby("duration_class")[[on_col, sev_col]]
                 .median()
                 .rename(columns={on_col:"med_on", sev_col:"med_sev"}))
    short_on = comp.get("med_on", {}).get("< 1h30", np.nan)
    short_se = comp.get("med_sev", {}).get("< 1h30", np.nan)
    mid_on   = comp.get("med_on", {}).get("1h30–3h", np.nan)
    mid_se   = comp.get("med_sev", {}).get("1h30–3h", np.nan)
    long_on  = comp.get("med_on", {}).get("> 3h", np.nan)
    long_se  = comp.get("med_sev", {}).get("> 3h", np.nan)
    extra = (
        f" Median by distance — **<1h30**: ~**{short_on:.0f}%**, **{short_se:.0f} min**; "
        f"**1h30–3h**: ~**{mid_on:.0f}%**, **{mid_se:.0f} min**; **>3h**: ~**{long_on:.0f}%**, **{long_se:.0f} min**. "
        f"Severity scales with distance, which remains the most powerful discriminator."
    )

if good_share is not None:
    tone = "success" if good_share >= 40 else ("warning" if good_share < 20 else "info")
    callout(
        tone,
        ":material/trending_up:",
        f"**{good_share:.0f}%** of liaisons currently **meet both targets** (≥90% on-time & ≤30-min severity). "
        f"{extra}"
    )

# Narrative — Scatter by active color_by
if not summ.empty:
    if color_by == "service":
        if treat_bi:
            card(
                title="Reliability vs. severity — colored by service (A↔B merged)",
                icon=":material/bubble_chart:",
                body_md=(
                    """
By colouring according to **service**, distribution becomes more compact than in the directional version.
**National** connections form a **dense core around 85–90% of arrivals on time** and **average delays of around 30 minutes**. The A↔B merger reduces extremes: connections that were efficient in one direction but fragile in the other are rebalanced, reducing vertical and horizontal dispersion.
**International connections** remain more diffuse, with slightly higher average delays. However, the difference between them and the national service is less marked: intra-service variability now dominates the separation between services.

In other words, the aggregation of directions mitigates the differences: the distinction between *National / International* remains visible, but the map reveals above all an **overall stability of the national network** and a **slight fragility of international corridors**, without any isolated excesses.
                    """
                ),
            )
        else:
            card(
                title="Reliability vs. severity — colored by service (A→B distinct)",
                icon=":material/bubble_chart:",
                body_md=(
                    """
Coloring by **service** makes the split explicit. **National** routes form a dense nucleus around **85–90% on-time**
and **~30 min delay**, signalling **predictable reliability**.  
**International** routes spread left/up (punctuality < **80%** more often, delays **> 35–40 min**), reflecting
cross-network coordination and border effects. Here, the **service type** is a clear structural discriminator.
                    """
                ),
            )
    else:  # color_by == "duration_class"
        if treat_bi:
            card(
                title="Reliability vs. severity — colored by duration class (A↔B merged)",
                icon=":material/timeline:",
                body_md=(
                    """
When colour-coded according to **journey time**, the structure remains similar to the previous version but is clearer.
**Short journeys (< 1 hour 30 minutes)** still appear to be the most stable category: they exceed **90% punctuality** and have the most limited delays, often less than **25 minutes**.
**Medium journeys (1 hour 30 minutes–3 hours)** fall in the middle range, between **85% and 90%**, with moderate variability.
**Long journeys (> 3 hours)** show higher delays and a noticeable dispersion above the **30-minute** line, confirming their greater exposure.

The major difference here is the **clarity of the groupings**: by merging the directions, the cloud becomes more readable and less noisy, making the performance gradient according to duration almost continuous. This highlights that **journey time remains the main explanatory variable**, even more robust than the nature of the service.
                    """
                ),
            )
        else:
            card(
                title="Reliability vs. severity — colored by duration class (A→B distinct)",
                icon=":material/timeline:",
                body_md=(
                    """
By colouring this time according to **journey duration**, the graph reveals another type of structure: performance **decreases with distance**.
**Short journeys (< 1h30)** are concentrated in the upper right-hand corner: **punctuality above 90%** and **limited delays**, demonstrating greater resilience in the face of unforeseen circumstances.
**Medium journeys (1.5–3 hours)** form an intermediate zone, fluctuating between **85% and 90%**, while **long journeys (> 3 hours)** are clearly grouped below the **85%** mark, with higher average delays and greater variability.

This gradient highlights a **near-linear relationship between operational complexity and loss of reliability**. The longer the journey, the greater the likelihood of incidents, traffic conflicts or cumulative effects. The ‘duration class’ variable therefore proves to be an **excellent predictor of stability**, at least as much as the nature of the service.
                    """
                ),
            )

st.divider()

# =====================================================
# C) Concentration curve (Lorenz)
# =====================================================
st.subheader("Concentration of late arrivals")
st.caption("How late arrivals distribute across liaisons. A bowed curve ⇒ **few routes drive most delays**.")

if not summ.empty:
    fig_lorenz = lorenz_late_share(summ)
    if fig_lorenz:
        st.plotly_chart(fig_lorenz, use_container_width=True)
    else:
        st.info("No late-arrival concentration could be computed.")
else:
    st.info("No liaison summary available for concentration curve.")

# ---- dynamic local read for concentration (rich prose) --------------------
share_20 = None
weight_col = next((c for c in ["late_arr_count","late_arrivals","late_count","late_weight"] if c in summ.columns), None)

if weight_col:
    s = summ[[weight_col]].copy().fillna(0).sort_values(weight_col, ascending=False)
    if len(s) > 0:
        k20 = max(1, int(round(0.2 * len(s))))
        k10 = max(1, int(round(0.1 * len(s))))
        share_20 = 100.0 * s.head(k20)[weight_col].sum() / max(1.0, s[weight_col].sum())
        share_10 = 100.0 * s.head(k10)[weight_col].sum() / max(1.0, s[weight_col].sum())
        tone = "warning" if share_20 >= 45 else ("info" if share_20 >= 30 else "success")
        callout(
            tone,
            ":material/area_chart:",
            f"The concentration curve implies **{share_20:.0f}% of late arrivals** come from the **top 20%** of liaisons "
            f"(and **{share_10:.0f}%** from the **top 10%**). In practice, a limited shortlist of routes would capture "
            f"most of the improvement potential{', even after A↔B merging' if treat_bi else ''}."
        )

# Narrative — Lorenz
if not summ.empty:
    if treat_bi:
        card(
            title="Where delays concentrate (A↔B merged)",
            icon=":material/area_chart:",
            body_md=(
                """
The concentration curve retains its strongly concave shape: approximately **20% of connections account for 50% of delays**, as before.
However, the A↔B merger slightly reduces the inequality: the curve moves a little closer to the diagonal, indicating that delays are **slightly better distributed** once the two directions are aggregated.
This phenomenon can be explained by **natural compensation between directions**: a connection that is unbalanced in one direction (e.g. significant delays on the outward journey) is often compensated for by better performance on the return journey, which reduces its relative weight in the cumulative distribution.
Nevertheless, the diagnosis remains the same: **a minority of connections account for the majority of delays**, making them the priority target for network improvement.
                """
            ),
        )
    else:
        card(
            title="Where delays concentrate (A→B distinct)",
            icon=":material/area_chart:",
            body_md=(
                """
The concentration curve shows **significant inequality in the distribution of delays**.
Approximately **20% of routes account for nearly 50% of late arrivals**, indicating that a minority of journeys are responsible for the majority of the problem. The actual curve (in blue) deviates significantly from the red diagonal line representing a uniform distribution, suggesting **significant asymmetry in risk**.
This diagnosis justifies targeted policies: **taking action on the few problematic routes** could be enough to significantly improve the overall punctuality of the network.
                """
            ),
        )

st.divider()

# =====================================================
# D) Delay distribution (boxplot)
# =====================================================
st.subheader("Distribution of arrival delays (delayed trains)")
st.caption("Boxplots by **duration class** quantify severity and outliers.")

dd = delay_distribution(dff)
if not dd.empty:
    st.plotly_chart(box_delay_distribution(dd), use_container_width=True)
else:
    st.info("No delay data to display.")

# ---- dynamic local read for boxplots (rich prose) -------------------------
if "duration_class" in dd.columns and "avg_delay_arr_delayed_min" in dd.columns:
    stats = (dd.groupby("duration_class")["avg_delay_arr_delayed_min"]
               .agg(median="median", p90=lambda s: s.quantile(0.90))
               .round(0))
    short_m = float(stats.loc["< 1h30","median"]) if "< 1h30" in stats.index else np.nan
    mid_m   = float(stats.loc["1h30–3h","median"]) if "1h30–3h" in stats.index else np.nan
    long_m  = float(stats.loc["> 3h","median"])     if "> 3h"   in stats.index else np.nan
    long_p90 = float(stats.loc["> 3h","p90"]) if "> 3h" in stats.index else np.nan

    tone = "warning" if np.isfinite(long_m) and long_m >= 40 else ("success" if np.isfinite(short_m) and short_m <= 22 else "info")
    callout(
        tone,
        ":material/align_center:",
        f"Delays increase with distance: **short** trips centre around **{short_m:.0f} min**, "
        f"**medium** around **{mid_m:.0f} min**, and **long** near **{long_m:.0f} min**. "
        f"The long-haul **90th percentile** reaches ~**{long_p90:.0f} min**, confirming that a small tail of "
        f"events drives much of the perceived pain."
    )

# Narrative — Boxplot
if not dd.empty:
    if treat_bi:
        card(
            title="How delays distribute by journey length (A↔B merged)",
            icon=":material/align_center:",
            body_md=(
                """
The distributions of delays by **duration class** confirm the structural differences.
**Long journeys (> 3 hours)** remain the **highest median (around 40 minutes)**, with extreme outliers exceeding 2 to 3 hours.
**Medium journeys (1.5–3 hours)** stabilise around 30 minutes, while **short journeys (< 1.5 hours)** remain the most compact and lowest distribution, centred around **20 minutes**.
The A↔B merger does not alter these hierarchies but slightly reduces the overall dispersion, proving that some of the noise came from one-off directional effects.
                """
            ),
        )
    else:
        card(
            title="How delays distribute by journey length (A→B distinct)",
            icon=":material/align_center:",
            body_md=(
                """
The distribution of **average delays by duration class** quantitatively confirms the trends observed on the scatter plot.
**Long journeys (> 3 hours)** show a **median of around 40 minutes**, with numerous **outliers exceeding 100 minutes**, reflecting increased exposure to major incidents.
**Average journeys (1.5–3 hours)** are more stable, centred around 30 minutes, while **short journeys (< 1.5 hours)** show modest delays with little dispersion.

This statistical reading illustrates the **gradation of risks according to journey time**: long journeys amplify the cumulative effects of micro-disruptions, and every minute lost tends to have an impact on the entire traffic plan.
                """
            ),
        )

# =====================================================
# Closing synthesis
# =====================================================
st.divider()

st.subheader("To conclude")

if treat_bi:
    card(
        title="Synthesis & where to look next",
        icon=":material/summarize:",
        body_md=(
            """
This *bidirectional* configuration provides a **more comprehensive and stable** overview of the performance of the TGV network.
Average punctuality remains high (around **86–87%**), but differences between the main lines persist: the **Paris routes** remain the most reliable, while the **southern and international corridors** remain the most vulnerable.
Integrating both directions makes it possible to identify **sustainable structural trends** by eliminating cyclical factors: performance depends above all on **distance travelled** and **type of service**, not on the direction of travel.

This approach therefore highlights the **overall robustness of the network** and its **systemic coherence**, but also emphasises that **future reliability gains will come from stabilising long distances** rather than optimising already high-performing lines.
By merging the directions, we obtain a strategic reading: the priority is no longer to correct local asymmetries, but to **reduce structural variability between journey classes** and between services.
            """
        ),
    )
else:
    card(
        title="Synthesis & where to look next",
        icon=":material/summarize:",
        body_md=(
            """
Taken together, these visuals show a **network that is generally efficient** but **heterogeneous in terms of stability**.
Average performance remains high, but **certain isolated routes undermine the perception of service**. Cross-analyses indicate that **distance and the nature of the service** (domestic/international) are two key factors explaining the differences: the former acts through the accumulation of contingencies, the latter through organisational complexity.

By considering A → B and B → A separately, we can identify real **directional asymmetries**: a connection may be smooth in one direction and fragile in the other, depending on train path management or timetable constraints. These disparities justify further analysis in the following pages (*Causes & Severity*, *Geo View*), where we will seek to identify **the specific sources of these imbalances**.
            """
        ),
    )
