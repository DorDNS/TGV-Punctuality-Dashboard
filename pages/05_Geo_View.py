import numpy as np
import pandas as pd
import streamlit as st
import pydeck as pdk
import plotly.express as px
from importlib.util import find_spec

from utils.filters import geo_sidebar
from utils.compute import apply_overview_filters
from utils.geo import (
    load_station_lookup,
    attach_coords,
    build_edges,
    add_edge_distance_km,
    station_metrics,
    late_points_for_density,
)

# Helpers
def _px_trendline_if_available():
    return "lowess" if find_spec("statsmodels") else None

def analysis_card(title: str, body_md: str, icon: str = ":material/analytics:"):
    with st.container(border=True):
        st.markdown(f"{icon} **{title}**")
        st.markdown(body_md)

def callout(tone: str, icon: str, text_md: str):
    box = getattr(st, tone, st.info)
    box(f"{icon}  {text_md}")

def _tone_delta(delta: float | None, *, good_when_down: bool,
                hi: float = 0.03, lo: float = -0.03) -> str:
    if delta is None or (isinstance(delta, float) and np.isnan(delta)):
        return "info"
    if good_when_down:
        if delta <= lo:  # down by >= 3 pp
            return "success"
        if delta >= hi:  # up by >= 3 pp
            return "warning"
    else:
        if delta >= hi:
            return "success"
        if delta <= lo:
            return "warning"
    return "info"

# Detect station columns or parse 'liaison' column
def _detect_station_cols_or_parse(edges: pd.DataFrame) -> tuple[pd.DataFrame, str | None, str | None]:
    if edges is None or edges.empty:
        return edges, None, None

    candidates = [
        ("departure", "arrival"),
        ("dep_station", "arr_station"),
        ("dep_name", "arr_name"),
        ("dep", "arr"),
    ]
    for a, b in candidates:
        if a in edges.columns and b in edges.columns:
            return edges, a, b

    # Fallback: parser 'liaison'
    if "liaison" not in edges.columns:
        return edges, None, None

    def _split_liaison(text: str) -> tuple[str, str]:
        s = str(text).strip()
        if "↔" in s:
            parts = s.split("↔", 1)
        elif "→" in s:
            parts = s.split("→", 1)
        elif "->" in s:
            parts = s.split("->", 1)
        elif " - " in s:
            parts = s.split(" - ", 1)
        else:
            return s, ""
        return parts[0].strip(), parts[1].strip()

    parsed = edges["liaison"].apply(_split_liaison)
    edges2 = edges.copy()
    edges2["__dep_name__"] = parsed.map(lambda t: t[0])
    edges2["__arr_name__"] = parsed.map(lambda t: t[1])
    return edges2, "__dep_name__", "__arr_name__"

# Merge bidirectional edges
def _merge_bidirectional_edges(edges: pd.DataFrame, lut: pd.DataFrame) -> pd.DataFrame:
    if edges is None or edges.empty:
        return edges

    gdf, dep_col, arr_col = _detect_station_cols_or_parse(edges)
    if not dep_col or not arr_col:
        return edges  # fail-silent si impossible

    loc = {}
    if lut is not None and not lut.empty and {"station", "lat", "lon"}.issubset(lut.columns):
        loc = lut.set_index("station")[["lat", "lon"]].to_dict(orient="index")

    def _row_from_group(g: pd.DataFrame) -> pd.Series:
        a = str(g[dep_col].iloc[0])
        b = str(g[arr_col].iloc[0])
        sta_min, sta_max = sorted([a, b])

        w = pd.to_numeric(g.get("circulated", 0), errors="coerce").fillna(0)
        w_sum = float(w.sum())

        def wavg(col: str) -> float:
            if col not in g.columns:
                return float("nan")
            s = pd.to_numeric(g[col], errors="coerce")
            if np.isfinite(s).any() and w_sum > 0:
                return float((s.fillna(0) * w).sum() / w_sum)
            return float(np.nanmean(s.to_numpy())) if s.size else float("nan")

        out = {}
        out["liaison"] = f"{sta_min} ↔ {sta_max}"

        for sta, prefix in [(sta_min, "dep"), (sta_max, "arr")]:
            lat = loc.get(sta, {}).get("lat", np.nan)
            lon = loc.get(sta, {}).get("lon", np.nan)
            out[f"{prefix}_lat"] = float(lat) if pd.notna(lat) else np.nan
            out[f"{prefix}_lon"] = float(lon) if pd.notna(lon) else np.nan

        out["circulated"] = float(pd.to_numeric(g.get("circulated", 0), errors="coerce").fillna(0).sum())
        out["severe_15_count"] = float(pd.to_numeric(g.get("severe_15_count", 0), errors="coerce").fillna(0).sum())
        out["on_time_pct"] = wavg("on_time_pct")
        out["cancel_rate_pct"] = wavg("cancel_rate_pct")
        out["distance_km"] = float("nan")

        for col in ["service", "duration_class"]:
            if col in g.columns:
                mode = g[col].mode(dropna=True)
                out[col] = mode.iloc[0] if not mode.empty else g[col].iloc[0]

        return pd.Series(out)

    g = gdf.copy()
    g["__k_min__"] = g[[dep_col, arr_col]].min(axis=1).astype(str)
    g["__k_max__"] = g[[dep_col, arr_col]].max(axis=1).astype(str)

    merged = (
        g.groupby(["__k_min__", "__k_max__"], group_keys=False)
         .apply(lambda x: _row_from_group(x.drop(columns=["__k_min__", "__k_max__"], errors="ignore")))
         .reset_index(drop=True)
    )
    return merged

# Page
st.set_page_config(page_title="Geo View", page_icon=":material/public:", layout="wide")

# Sidebar
geo_sidebar()

st.markdown("# Geo View")
st.caption("Origin–destination arcs colored by on-time performance and sized by traffic.")

# Load cleaned data from session
df = st.session_state.get("df_clean", None)
if df is None or df.empty:
    st.error("Data not loaded.")
    st.stop()

# Apply filters
dff = apply_overview_filters(df, st.session_state)
if dff.empty:
    st.warning("No data for the selected filters.")
    st.stop()

# Join station coordinates
lut = load_station_lookup("data/stations.csv")
dff2, missing = attach_coords(dff, lut)

if missing:
    with st.expander("Missing coordinates for stations (not shown on the map)"):
        st.write(", ".join(sorted(set(missing))))


edges = build_edges(dff2)

if st.session_state.get("treat_bidirectional", False):
    edges = _merge_bidirectional_edges(edges, lut)

edges = add_edge_distance_km(edges)

# Station-level metrics
stations = station_metrics(dff2)

# Points for density layers
late_pts = late_points_for_density(dff2)

if edges is None or edges.empty:
    st.info("No edges with coordinates to display. Add more stations to data/stations.csv.")
    st.stop()

# Map tabs
tab_map, tab_density, tab_hubs, tab_geo_perf = st.tabs(
    ["OD Arcs", "Late Density", "Hubs", "Geo ↔ Performance"]
)

# OD arcs
with tab_map:
    st.caption("Origin–destination arcs colored by on-time performance and sized by traffic.")

    try:
        n_edges = int(len(edges))
        avg_otp = float(edges["on_time_pct"].mean()) if n_edges else float("nan")
        worst = edges.sort_values("on_time_pct").iloc[0] if n_edges else None
        tone = ("success" if avg_otp >= 90 else "warning" if avg_otp >= 85 else "error") if n_edges else "info"
        msg = f"**{n_edges:,} corridors shown**. Average on-time **{(0 if np.isnan(avg_otp) else avg_otp):.1f}%**."
        if worst is not None and pd.notna(worst.get("on_time_pct")):
            msg += f" Weakest corridor: **{worst['liaison']}** ({worst['on_time_pct']:.1f}%)."
        callout(tone, ":material/alt_route:", msg)
    except Exception:
        pass

    edges_viz = edges.copy()

    def _fmt_pct(x):
        x = float(x) if pd.notna(x) else np.nan
        return f"{x:.1f}%" if np.isfinite(x) else "—"
    def _fmt_int(x):
        try:
            return f"{int(x):,}"
        except Exception:
            return "—"
    def _fmt_km(x):
        x = float(x) if pd.notna(x) else np.nan
        return f"{x:.0f} km" if np.isfinite(x) else "—"

    edges_viz["on_time_lbl"]    = edges_viz.get("on_time_pct", np.nan).map(_fmt_pct)
    edges_viz["cancel_lbl"]     = edges_viz.get("cancel_rate_pct", np.nan).map(_fmt_pct)
    edges_viz["severe15_lbl"]   = edges_viz.get("severe_15_count", np.nan).map(_fmt_int)
    edges_viz["circulated_lbl"] = edges_viz.get("circulated", np.nan).map(_fmt_int)
    edges_viz["distance_lbl"]   = edges_viz.get("distance_km", np.nan).map(_fmt_km)

    def _width_from_series(s: pd.Series) -> pd.Series:
        s = pd.to_numeric(s, errors="coerce").fillna(0).clip(lower=0)
        if s.max() <= 0 or s.quantile(0.9) == s.quantile(0.2):
            return pd.Series(6.0, index=s.index)
        z = (s - s.quantile(0.2)) / max(s.quantile(0.9) - s.quantile(0.2), 1e-6)
        return 2.0 + 10.0 * z.clip(0, 1)

    if "circulated" in edges_viz.columns:
        edges_viz["width_px"] = _width_from_series(edges_viz["circulated"])
    elif "severe_15_count" in edges_viz.columns:
        edges_viz["width_px"] = _width_from_series(edges_viz["severe_15_count"])
    else:
        edges_viz["width_px"] = 6.0

    otp = pd.to_numeric(edges_viz.get("on_time_pct", np.nan), errors="coerce")
    score = np.tanh((otp - 90.0) / 5.0)
    score = pd.Series(score, index=edges_viz.index).fillna(0.0).clip(-1, 1)

    def _rg(pa):
        x = float(pa)
        if x < 0:
            t = x + 1.0
            r, g, b = 255, int(60 + t*(215-60)), 60
        else:
            t = x
            r, g, b = int(255 - t*(255-60)), int(215 + t*(190-215)), int(60 + t*(90-60))
        return [int(r), int(g), int(b), 220]

    edges_viz["color_rgba"] = score.map(_rg)

    tooltip = {
        "html": """
        <div style="font-size:13px">
          <b>{liaison}</b><br/>
          On-time: {on_time_lbl}<br/>
          Cancel rate: {cancel_lbl}<br/>
          ≥15 min delays: {severe15_lbl}<br/>
          Circulated: {circulated_lbl}<br/>
          Distance: {distance_lbl}
        </div>
        """,
        "style": {"backgroundColor": "white", "color": "black"},
    }

    arc_layer = pdk.Layer(
        "ArcLayer",
        data=edges_viz,
        get_source_position=["dep_lon", "dep_lat"],
        get_target_position=["arr_lon", "arr_lat"],
        get_source_color="color_rgba",
        get_target_color="color_rgba",
        get_width="width_px",
        pickable=True,
        auto_highlight=True,
        id="od-arcs",
    )

    nodes_dep = edges.rename(columns={"dep_lon": "lon", "dep_lat": "lat"})[["lon", "lat"]]
    nodes_arr = edges.rename(columns={"arr_lon": "lon", "arr_lat": "lat"})[["lon", "lat"]]
    nodes = pd.concat([nodes_dep.dropna(), nodes_arr.dropna()], axis=0).drop_duplicates(ignore_index=True)
    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=nodes,
        get_position=["lon", "lat"],
        get_radius=5000,
        get_fill_color=[40, 40, 40, 160],
        pickable=False,
        id="stations",
    )

    lgv_layer = None
    try:
        import json, os
        if os.path.exists("data/lgv_fr.geojson"):
            with open("data/lgv_fr.geojson", "r", encoding="utf-8") as f:
                gj = json.load(f)
            paths = []
            for feat in gj.get("features", []):
                g = feat.get("geometry", {})
                if g.get("type") == "LineString":
                    paths.append({"path": g.get("coordinates", [])})
                elif g.get("type") == "MultiLineString":
                    for c in g.get("coordinates", []):
                        paths.append({"path": c})
            if paths:
                lgv_layer = pdk.Layer(
                    "PathLayer",
                    data=paths,
                    get_path="path",
                    get_color=[30, 30, 30, 140],
                    width_scale=1,
                    width_min_pixels=2,
                    id="lgv-overlay",
                )
    except Exception:
        lgv_layer = None

    lat0 = float(edges["dep_lat"].dropna().mean()) if edges["dep_lat"].notna().any() else 47.0
    lon0 = float(edges["dep_lon"].dropna().mean()) if edges["dep_lon"].notna().any() else 2.0
    initial_view = pdk.ViewState(latitude=lat0, longitude=lon0, zoom=5.2, pitch=45)

    layers = [arc_layer, scatter] if lgv_layer is None else [lgv_layer, arc_layer, scatter]

    st.caption("Color = on-time vs 90% target (±5 pp, tanh contrast). Width ∝ traffic (20–90th pct).")
    st.pydeck_chart(
        pdk.Deck(
            map_style=None,
            api_keys={"carto": "public"},
            initial_view_state=initial_view,
            layers=layers,
            tooltip=tooltip,
        ),
        use_container_width=True,
    )

    analysis_card(
        title="Flow and reliability per corridor",
        icon=":material/route:",
        body_md="""
    This map displays the 130 main TGV routes, with colors and line thickness providing a clear snapshot of punctuality and traffic levels. Each arc links two destinations: the color reflects how close the route is to the **90 % on-time target** (red = below, yellow = around, green = above), while the line width represents how many trains circulate on that corridor. The network’s overall on-time rate is **85.7 %**, below the target, and the **weakest corridor is ITALIE → PARIS LYON (67.7 %)**.

    Most lines radiate from Paris, confirming its role as the heart of the TGV network. The thickest arcs — such as **Paris–Lyon**, **Paris–Marseille**, and **Paris–Bordeaux** — handle the highest traffic but also experience more frequent delays, visible through orange and red shades. By contrast, thinner international links toward **London**, **Zurich**, or **Milan** often show lighter tones, indicating steadier performance.

    Overall, the map highlights a clear pattern: the busiest corridors tend to be the least punctual, while peripheral routes maintain better reliability. It underlines how the strong concentration of traffic around Paris amplifies delay risks across the French high-speed network.
    """
    )

# Late density
with tab_density:
    st.caption("Heatmap of late-arrival intensity (unweighted), robust alternative to 3D hex.")

    def _clean_points(df_pts: pd.DataFrame | None) -> pd.DataFrame | None:
        if df_pts is None or df_pts.empty:
            return None
        if not {"lon", "lat"}.issubset(df_pts.columns):
            return None
        out = df_pts[["lon", "lat"]].copy()
        out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
        out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
        out = out.dropna(subset=["lon", "lat"])
        return out if not out.empty else None

    pts = _clean_points(late_pts)

    if pts is None and edges is not None and not edges.empty:
        rows = []
        for _, r in edges.iterrows():
            if pd.notna(r.get("dep_lon")) and pd.notna(r.get("dep_lat")):
                rows.append({"lon": float(r["dep_lon"]), "lat": float(r["dep_lat"])})
            if pd.notna(r.get("arr_lon")) and pd.notna(r.get("arr_lat")):
                rows.append({"lon": float(r["arr_lon"]), "lat": float(r["arr_lat"])})
        pts = _clean_points(pd.DataFrame(rows))

    if pts is None:
        st.info("No geocoded points available for density. Check station coordinates or filters.")
    else:
        radius_px = st.slider("Heat radius (pixels)", 20, 150, 60, 5, key="geo_density_radius_only")

        try:
            n_pts = int(len(pts))
            tone = "success" if n_pts >= 200 else "warning" if n_pts < 50 else "info"
            msg = f"Heatmap built from **{n_pts:,} points** (radius **{radius_px}px**)."
            bins = pts.assign(lat_bin=pts["lat"].round(1), lon_bin=pts["lon"].round(1))
            top = (bins.groupby(["lat_bin", "lon_bin"]).size().sort_values(ascending=False).head(1))
            if not top.empty:
                (latb, lonb), _ = top.index[0], top.iloc[0]
                msg += f" Hottest area near **({latb:.1f}, {lonb:.1f})**."
            callout(tone, ":material/local_fire_department:", msg)
        except Exception:
            pass

        view = pdk.ViewState(
            latitude=float(pts["lat"].mean()),
            longitude=float(pts["lon"].mean()),
            zoom=5.2,
            pitch=0,
        )

        heat_layer = pdk.Layer(
            "HeatmapLayer",
            data=pts,
            id="late-heat",
            get_position="[lon, lat]",
            radius_pixels=radius_px,
        )

        st.pydeck_chart(
            pdk.Deck(
                map_style=None,
                initial_view_state=view,
                layers=[heat_layer],
            ),
            use_container_width=True,
            height=560,
        )

        analysis_card(
            title="Geographical concentration of delays",
            icon=":material/local_fire_department:",
            body_md="""
        This heatmap shows where late train arrivals are most concentrated across the network. Each point represents a station involved in at least one delayed arrival, with warmer colors indicating higher density.

        The map, built from over 21,000 points, shows a clear hotspot around Paris (48.8° N, 2.4° E), confirming that the majority of delays occur in and around the capital. This central peak reflects the dense concentration of departures, arrivals, and connections managed through the Paris hub. Smaller yellow zones appear near Lyon, Marseille, and Geneva, showing secondary centers of delay activity linked to regional or international routes.

        Overall, this visualization gives a spatial picture of delay intensity: Paris dominates, illustrating how the network’s high centralization leads to greater exposure to disruption. Peripheral areas show lighter activity, suggesting that delays are less frequent and more dispersed outside the capital’s core.
        """
        )

# Hubs
with tab_hubs:
    st.caption("Stations sized by number of distinct liaisons served; color = on-time (proxy).")
    if stations is None or stations.empty:
        st.info("No station metrics available.")
    else:
        df_pairs = dff2[["departure", "arrival"]].dropna()
        a = df_pairs.rename(columns={"departure": "station", "arrival": "partner"})
        b = df_pairs.rename(columns={"arrival": "station", "departure": "partner"})
        deg = pd.concat([a, b], axis=0, ignore_index=True)
        deg = deg[deg["station"].notna() & deg["partner"].notna()]
        deg = deg.groupby("station")["partner"].nunique().reset_index(name="liaisons_count")

        s = deg.merge(
            stations[["station", "on_time_pct", "late_arr_count", "circulated"]],
            on="station", how="left"
        ).merge(lut[["station", "lat", "lon"]], on="station", how="left")

        s = s.dropna(subset=["lat", "lon"]).copy()
        if s.empty:
            st.info("No geocoded stations available for hubs.")
        else:
            root = np.sqrt(s["liaisons_count"].clip(lower=0))
            denom = root.max() if np.isfinite(root.max()) and root.max() > 0 else 1.0
            s["radius"] = 1200 + 9000 * (root / denom)

            otp = s["on_time_pct"].clip(lower=0, upper=100).fillna(0.0)
            r = (255 - otp * 2.0).clip(0, 255).round().astype(int)
            g = (160 + otp * 0.95).clip(0, 255).round().astype(int)
            s["fill_r"], s["fill_g"] = r, g

            try:
                top_row = s.sort_values("liaisons_count", ascending=False).iloc[0]
                med_deg = float(s["liaisons_count"].median())
                tone = ("success" if float(top_row.get("on_time_pct", 0)) >= 90
                        else "warning" if float(top_row.get("on_time_pct", 0)) >= 85
                        else "error")
                msg = (f"**{top_row['station']}** serves **{int(top_row['liaisons_count']):,}** distinct liaisons "
                       f"(network median **{med_deg:.0f}**). On-time proxy **{float(top_row.get('on_time_pct', float('nan'))):.1f}%**.")
                callout(tone, ":material/hub:", msg)
            except Exception:
                pass

            hub_layer = pdk.Layer(
                "ScatterplotLayer",
                data=s,
                get_position=["lon", "lat"],
                get_radius="radius",
                get_fill_color=["fill_r", "fill_g", 90, 190],
                pickable=True,
                id="hub-scatter-degree",
            )

            tooltip_hub = {
                "html": """
                <div style="font-size:13px">
                  <b>{station}</b><br/>
                  Liaisons served: {liaisons_count:,}<br/>
                  On-time (proxy): {on_time_pct:.1f}%<br/>
                  Late arrivals: {late_arr_count:,}<br/>
                  Circulated: {circulated:,}
                </div>
                """,
                "style": {"backgroundColor": "white", "color": "black"},
            }

            v = pdk.ViewState(
                latitude=float(s["lat"].dropna().mean()),
                longitude=float(s["lon"].dropna().mean()),
                zoom=5.2,
                pitch=0,
            )

            deck3 = pdk.Deck(
                map_style=None,
                api_keys={"carto": "public"},
                initial_view_state=v,
                layers=[hub_layer],
                tooltip=tooltip_hub,
            )
            st.pydeck_chart(deck3, use_container_width=True)

            st.markdown("**Top stations by number of liaisons served**")
            top_n = st.slider("Top N", 5, 30, 12, key="geo_top_hubs_degree")
            top_h = s.sort_values("liaisons_count", ascending=False).head(top_n)
            fig_h = px.bar(top_h, x="station", y="liaisons_count", title=None)
            fig_h.update_layout(template="plotly_white", height=320)
            fig_h.update_yaxes(title="# liaisons")
            fig_h.update_xaxes(title=None)
            st.plotly_chart(fig_h, use_container_width=True)

            analysis_card(
                title="Network hubs and connectivity",
                icon=":material/hub:",
                body_md="""
            This visualization highlights the **core hubs** of the French TGV network, combining a geographic view and a ranking by number of connections served. Each green circle represents a station, its **size** proportional to the number of distinct liaisons it handles, and its **color** reflecting a proxy of on-time performance.

            The data confirm the **exceptional dominance of Paris Lyon station**, which serves **25 distinct liaisons**, far above the **network median of just 1**, with an on-time proxy of **86.6 %**. It is followed by **Paris Montparnasse**, **Marseille Saint-Charles**, **Lyon Part-Dieu**, **Paris Est**, and **Paris Nord**, all major pillars of national and regional mobility. The bar chart clearly shows the gap between Paris Lyon and the rest of the network: its connectivity level is more than double that of the next largest hubs.

            This hierarchy reveals the **strong concentration of connections around Paris**, where multiple departure stations distribute flows to every region. While this structure enhances accessibility and central coordination, it also exposes the network to congestion effects and punctuality challenges.

            Overall, the visualization offers a structural view of how the French high-speed network is organized: **a star-shaped system centered on Paris**, supported by a few key regional relays (Lyon, Marseille, Lille, Bordeaux). It shows how connectivity and performance are closely linked — the most connected stations drive the system’s efficiency but also bear its greatest operational pressure.
            """
            )

# Geo vs Performance
with tab_geo_perf:
    st.caption("Does geography matter? Explore distance vs. reliability and a risk table.")

    try:
        dfc = edges[["distance_km", "on_time_pct"]].dropna()
        r = float(np.corrcoef(dfc["distance_km"], dfc["on_time_pct"])[0, 1]) if len(dfc) >= 3 else float("nan")
        tone = ("info" if np.isnan(r)
                else "success" if abs(r) < 0.20
                else "warning" if abs(r) < 0.40
                else "error")
        callout(tone, ":material/trending_flat:",
                f"Correlation distance → on-time: **{(0 if np.isnan(r) else r):+.2f}** (|r|<0.20 ≈ weak).")
    except Exception:
        pass

    c1, c2 = st.columns((1.2, 1), gap="large")

    with c1:
        trend = _px_trendline_if_available()
        fig_s = px.scatter(
            edges,
            x="distance_km",
            y="on_time_pct",
            size="circulated",
            hover_name="liaison",
            title="On-time vs. distance between endpoints",
            trendline=trend,
        )
        fig_s.update_layout(template="plotly_white", height=420)
        fig_s.update_xaxes(title="Distance (km)")
        fig_s.update_yaxes(title="On-time arrival %", rangemode="tozero")
        st.plotly_chart(fig_s, use_container_width=True)
        if trend is None:
            st.caption("Install `statsmodels` to enable LOESS trendlines (pip install statsmodels).")

    with c2:
        risk = edges.copy()
        denom = risk["circulated"].replace(0, np.nan)
        risk["risk_score"] = (100 - risk["on_time_pct"].fillna(0)) * (risk["severe_15_count"].fillna(0) / denom)
        risk = risk.sort_values(["on_time_pct", "risk_score"], ascending=[True, False]).head(15)
        show = risk[
            ["liaison", "on_time_pct", "severe_15_count", "circulated", "distance_km"]
        ].rename(
            columns={
                "on_time_pct": "On-time %",
                "severe_15_count": "≥15 count",
                "circulated": "Trains",
                "distance_km": "km",
            }
        )
        st.dataframe(show, use_container_width=True, hide_index=True)

    analysis_card(
        title="Distance versus reliability",
        icon=":material/insights:",
        body_md="""
    This visualization examines how the distance between cities influences TGV punctuality. Each point represents a corridor, with **distance on the x-axis**, **on-time arrival rate on the y-axis**, and **bubble size** reflecting traffic volume.

    The correlation between distance and punctuality is **–0.21**, which indicates a **weak negative relationship**: longer routes tend to be slightly less reliable, but distance alone does not account for most of the variations. Most connections, short or long, cluster between 80 % and 90 % on-time, showing that geography is not the main factor affecting delays.

    The risk table confirms this trend by listing the weakest routes, such as *Italie → Paris Lyon* (67.7 %) and *Lyon Part Dieu → Lille* (73.7 %). These lines combine lower punctuality with frequent long delays, often linked to heavy traffic or international operations.

    Overall, this analysis suggests that **distance has only a marginal effect** on performance. The main causes of delay seem tied instead to **network congestion, connection density, and operational complexity**, especially on major national axes.
    """
    )