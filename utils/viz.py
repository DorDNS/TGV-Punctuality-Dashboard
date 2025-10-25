import plotly.express as px
import plotly.graph_objects as go
import numpy as np

def theme():
    return {"template": "plotly_white", "height": 380}

def line_monthly_enhanced(df, y_col: str, title: str, ref_line: float | None = None, annotate_extrema: bool = True):
    """
    Courbe mensuelle avec:
      - suffixe unités (% si pertinent)
      - ligne de référence optionnelle (ex: 90% pour on-time)
      - annotations min/max optionnelles
    """
    cfg = theme()
    fig = px.line(df, x="date", y=y_col, markers=True, title=title)
    fig.update_layout(template=cfg["template"], height=cfg["height"], legend_title_text="")
    if y_col in ("on_time_pct", "cancel_rate_pct"):
        fig.update_yaxes(title=None, ticksuffix=" %")
    else:
        fig.update_yaxes(title=None)
    fig.update_xaxes(title=None)

    # Ligne de référence (ex: 90% sur l’on-time)
    if ref_line is not None:
        fig.add_hline(y=ref_line, line_dash="dot", line_width=1, opacity=0.6)
        fig.add_annotation(
            xref="paper", x=1.005, y=ref_line, yref="y",
            text=f"{ref_line:g}" + ("%" if y_col in ("on_time_pct", "cancel_rate_pct") else ""),
            showarrow=False, font=dict(size=11), xanchor="left"
        )

    # Annotations min / max pour guider l’œil
    if annotate_extrema and df[y_col].notna().any():
        y_min = df.loc[df[y_col].idxmin()]
        y_max = df.loc[df[y_col].idxmax()]
        unit = "%" if y_col in ("on_time_pct", "cancel_rate_pct") else " min"

        fig.add_annotation(
            x=y_max["date"], y=y_max[y_col],
            text=f"max {y_max[y_col]:.1f}{unit}",
            showarrow=True,
            arrowhead=2,
            yshift=10,
            font=dict(size=11)
        )

        fig.add_annotation(
            x=y_min["date"], y=y_min[y_col],
            text=f"min {y_min[y_col]:.1f}{unit}",
            showarrow=True,
            arrowhead=2,
            ax=-40, ay=0,       
            standoff=6,         
            xanchor="right",  
            align="right", 
            font=dict(size=11),
        )


    return fig

def line_duration(df, title: str):
    cfg = theme()
    fig = px.line(
        df, x="date", y="on_time_pct", color="duration_class",
        markers=True,
        title=title,
    )
    fig.update_layout(template=cfg["template"], height=cfg["height"], legend_title_text="Duration")
    fig.update_yaxes(title=None, ticksuffix=" %")
    fig.update_xaxes(title=None)
    return fig

def bar_ranking(top_df, bottom_df, metric_label: str):
    # turn index into a column named 'liaison' even if index name differs
    top_plot = top_df.reset_index().rename(columns={"index": "liaison"})
    bottom_plot = bottom_df.reset_index().rename(columns={"index": "liaison"})

    fig_top = px.bar(
        top_plot,
        x="rank_metric",
        y="liaison",
        orientation="h",
        title=f"Top 10 liaisons by {metric_label}",
    )
    fig_top.update_layout(template="plotly_white", height=450, yaxis=dict(autorange="reversed"))
    fig_top.update_xaxes(title=None)
    fig_top.update_yaxes(title=None)

    fig_bottom = px.bar(
        bottom_plot,
        x="rank_metric",
        y="liaison",
        orientation="h",
        title=f"Bottom 10 liaisons by {metric_label}",
    )
    fig_bottom.update_layout(template="plotly_white", height=450, yaxis=dict(autorange="reversed"))
    fig_bottom.update_xaxes(title=None)
    fig_bottom.update_yaxes(title=None)

    return fig_top, fig_bottom


def box_delay_distribution(df):
    """Boxplot of average delay per duration class."""
    fig = px.box(
        df,
        x="duration_class",
        y="avg_delay_arr_delayed_min",
        points="outliers",
        title="Distribution of arrival delays (delayed trains)",
    )
    fig.update_layout(template="plotly_white", height=400)
    fig.update_yaxes(title="Delay (min)")
    fig.update_xaxes(title="Duration class")
    return fig

def stacked_causes(df_long, title: str, horizontal: bool = False):
    """
    Stacked bar of cause composition (%).
    If horizontal=True, group (liaison) on y-axis for better readability.
    """
    if df_long.empty:
        return None

    if horizontal:
        fig = px.bar(df_long, x="pct", y="group", color="cause", orientation="h", title=title)
    else:
        fig = px.bar(df_long, x="group", y="pct", color="cause", title=title)

    fig.update_layout(template="plotly_white", height=420, legend_title_text="Cause")
    fig.update_yaxes(title=None if horizontal else "Percentage", ticksuffix="" if horizontal else " %")
    fig.update_xaxes(title=None)
    if not horizontal:
        fig.update_yaxes(ticksuffix=" %")
    return fig


def grouped_severity(df_counts, title: str, horizontal: bool = False):
    """
    Grouped bars for severe counts.
    When breakdown is Month, we just plot bars over time (single series).
    When breakdown is Liaison Top N, we make a horizontal bar chart.
    """
    if df_counts.empty:
        return None

    if horizontal:
        fig = px.bar(df_counts, x="count", y="group", orientation="h", title=title)
        fig.update_yaxes(title=None)
        fig.update_xaxes(title="Count")
    else:
        fig = px.bar(df_counts, x="group", y="count", title=title)
        fig.update_yaxes(title="Count")
        fig.update_xaxes(title=None)

    fig.update_layout(template="plotly_white", height=380)
    return fig

def scatter_performance(df, color_by: str = "service", x_ref: float | None = 90.0, y_ref: float | None = 30.0):
    """
    Scatter: on_time_pct (x) vs avg_delay_arr_delayed_min (y), size=circulated, color=<color_by>.
    Adds optional reference lines at x_ref (e.g., 90%) and y_ref (e.g., 30 min).
    """
    if df.empty:
        return None

    cfg = theme()
    color_col = color_by if color_by in df.columns else None

    fig = px.scatter(
        df, x="on_time_pct", y="avg_delay_arr_delayed_min",
        size="circulated", color=color_col,
        hover_name="liaison",
        hover_data={"circulated":":,", "late_arr_count":":,", "cancel_rate_pct":":.1f", "late_rate_pct":":.1f"},
        title=f"Reliability vs. severity ({'color: ' + color_col if color_col else 'no grouping'})",
    )
    fig.update_layout(template=cfg["template"], height=420, legend_title_text=color_col or "")
    fig.update_xaxes(title="On-time arrival %", rangemode="tozero")
    fig.update_yaxes(title="Avg delay (late trains, min)", rangemode="tozero")

    if x_ref is not None:
        fig.add_vline(x=x_ref, line_dash="dot", line_width=1, opacity=0.6)
        fig.add_annotation(x=x_ref, yref="paper", y=1.02, showarrow=False, text=f"{x_ref:g}% target", xanchor="left")
    if y_ref is not None:
        fig.add_hline(y=y_ref, line_dash="dot", line_width=1, opacity=0.6)
        fig.add_annotation(y=y_ref, xref="paper", x=1.01, showarrow=False, text=f"{y_ref:g} min", yanchor="bottom")

    return fig

def lorenz_late_share(df):
    """
    Lorenz-style curve of late arrivals by liaison:
    - Sort liaisons by late_arr_count descending
    - Plot cumulative share of late_arr_count vs cumulative share of liaisons
    """
    if df.empty or "late_arr_count" not in df.columns:
        return None

    d = df[["liaison","late_arr_count"]].dropna().sort_values("late_arr_count", ascending=False).reset_index(drop=True)
    total = d["late_arr_count"].sum()
    if total <= 0:
        return None

    d["cum_liaisons"] = (np.arange(len(d)) + 1) / len(d) * 100.0
    d["cum_late_share"] = d["late_arr_count"].cumsum() / total * 100.0

    cfg = theme()
    fig = px.line(d, x="cum_liaisons", y="cum_late_share", title="Concentration of late arrivals across liaisons")
    fig.update_layout(template=cfg["template"], height=380, showlegend=False)
    fig.update_xaxes(title="Cumulative liaisons (%)", range=[0,100])
    fig.update_yaxes(title="Cumulative late arrivals (%)", range=[0,100])

    # 45° equality line
    fig.add_trace(go.Scatter(x=[0,100], y=[0,100], mode="lines", line=dict(dash="dot"), showlegend=False))

    return fig

# === NEW: Heatmap month × cause ===========================================
def heatmap_causes_month(pivot_df, title: str):
    if pivot_df.empty:
        return None
    # long format for px.imshow or px.density_heatmap; we’ll use imshow for control
    mat = pivot_df.set_index("month").sort_index()
    fig = px.imshow(
        mat.T,  # causes as rows
        aspect="auto",
        color_continuous_scale="Blues",
        title=title,
        labels=dict(color="% share"),
    )
    fig.update_layout(template="plotly_white", height=420)
    fig.update_yaxes(title=None)
    fig.update_xaxes(title=None)
    return fig

import plotly.express as px

_CAUSE_COLORS = {
    "External": "#1f77b4",
    "Infrastructure": "#7fb3ff",
    "Traffic": "#e45756",  # Note: Votre code original utilisait 'Traffic', j'utilise ça. Si c'est 'Traffic management', ajustez ici.
    "Rolling stock": "#f1a6a5",
    "Station ops & reuse": "#2ca02c",
    "Passengers / PSH / connections": "#9be39b",
}

def stacked_100_by_attr(df_long, title: str, horizontal: bool = False):
    """
    Proper 100% stacked bar chart by attribute (service/duration).
    Expects df_long with columns: [group, cause, pct] where pct in 0..100.
    """
    if df_long is None or df_long.empty:
        return None

    df_plot = df_long.copy()
    # Clamp & clean
    df_plot["pct"] = df_plot["pct"].fillna(0).clip(lower=0, upper=100)

    # Utiliser le mapping de couleurs défini
    color_map = {k: _CAUSE_COLORS.get(k, '#808080') for k in df_plot["cause"].unique()} # #808080 = gris par défaut

    if horizontal:
        fig = px.bar(
            df_plot,
            x="pct", y="group", color="cause",
            orientation="h", title=title, barmode="stack",
            color_discrete_map=color_map, # Utiliser le mapping ici
        )
        fig.update_xaxes(range=[0, 100], ticksuffix=" %", title=None)
        fig.update_yaxes(title=None)
        hover_template = "<b>%{y}</b><br>%{fullData.name}: %{x:.1f}%<extra></extra>"
        text_template = "%{x:.0f}%"
    else:
        fig = px.bar(
            df_plot,
            x="group", y="pct", color="cause",
            title=title, barmode="stack",
            color_discrete_map=color_map, # Utiliser le mapping ici
        )
        fig.update_yaxes(range=[0, 100], ticksuffix=" %", title=None)
        fig.update_xaxes(title=None)
        hover_template = "<b>%{x}</b><br>%{fullData.name}: %{y:.1f}%<extra></extra>"
        text_template = "%{y:.0f}%"

    fig.update_traces(
        texttemplate=text_template,
        textposition="inside",
        insidetextanchor="middle",
        hovertemplate=hover_template # Utiliser le template corrigé
    )

    fig.update_layout(
        template="plotly_white",
        height=420,
        legend_title_text="Cause",
        margin=dict(l=40, r=40, t=60, b=40),
        bargap=0.15,
        uniformtext_minsize=9,
        uniformtext_mode="hide",
    )
    return fig

# === NEW: Grouped bars — severity share by cause ==========================
def grouped_severity_by_cause(df_long, title: str):
    if df_long.empty:
        return None
    fig = px.bar(df_long, x="cause", y="pct", color="bucket", barmode="group", title=title)
    fig.update_layout(template="plotly_white", height=420, legend_title_text="Bucket")
    fig.update_yaxes(title="Share within bucket (%)", ticksuffix=" %")
    fig.update_xaxes(title=None)
    return fig

# === NEW: Scatter with dominant cause =====================================
def scatter_dominant_cause(df, title: str, x_ref: float = 90.0, y_ref: float = 30.0):
    if df.empty:
        return None
    fig = px.scatter(
        df, x="on_time_pct", y="avg_delay_arr_delayed_min",
        color="dominant_cause", size="late_arr_count", hover_name="liaison",
        title=title
    )
    fig.update_layout(template="plotly_white", height=420, legend_title_text="Dominant cause")
    fig.update_xaxes(title="On-time %", range=[min(60, df["on_time_pct"].min()-2), 100], ticksuffix=" %")
    fig.update_yaxes(title="Avg delay when late (min)")
    # refs
    fig.add_vline(x=x_ref, line_dash="dot", opacity=0.5)
    fig.add_hline(y=y_ref, line_dash="dot", opacity=0.5)
    return fig
