import pandas as pd
import numpy as np
import unicodedata

# --- Name normalization (robust match: case-insensitive, remove accents/spaces) ---
def _norm_name(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = s.replace("-", " ").replace("’", "'")
    return " ".join(s.upper().split())

def load_station_lookup(path: str = "data/stations.csv") -> pd.DataFrame:
    """
    Read station coordinates (station, lat, lon). Return with a normalized key for joining.
    Expected columns: station, lat, lon
    """
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        return pd.DataFrame(columns=["station", "lat", "lon", "key"])
    cols = {c.lower(): c for c in df.columns}
    need = {"station", "lat", "lon"}
    if not need.issubset(set(cols.keys()) | set(df.columns.str.lower())):
        # Return empty with proper columns if file shape is wrong
        return pd.DataFrame(columns=["station", "lat", "lon", "key"])
    # Standardize columns
    df = df.rename(columns={cols.get("station", "station"): "station",
                            cols.get("lat", "lat"): "lat",
                            cols.get("lon", "lon"): "lon"})
    df["key"] = df["station"].map(_norm_name)
    return df[["station", "lat", "lon", "key"]]

def attach_coords(df: pd.DataFrame, lut: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Join coordinates for departure and arrival. Return (df_with_coords, missing_stations).
    """
    if df.empty or lut.empty:
        return df.assign(dep_lat=np.nan, dep_lon=np.nan, arr_lat=np.nan, arr_lon=np.nan), []

    d = df.copy()
    d["dep_key"] = d["departure"].map(_norm_name)
    d["arr_key"] = d["arrival"].map(_norm_name)

    lut_dep = lut[["key", "lat", "lon"]].rename(columns={"lat": "dep_lat", "lon": "dep_lon"})
    lut_arr = lut[["key", "lat", "lon"]].rename(columns={"lat": "arr_lat", "lon": "arr_lon"})

    d = d.merge(lut_dep, left_on="dep_key", right_on="key", how="left").drop(columns=["key"])
    d = d.merge(lut_arr, left_on="arr_key", right_on="key", how="left").drop(columns=["key"])

    missing = set()
    missing.update(d.loc[d["dep_lat"].isna(), "departure"].unique().tolist())
    missing.update(d.loc[d["arr_lat"].isna(), "arrival"].unique().tolist())
    missing = [m for m in missing if isinstance(m, str)]
    return d, sorted(missing)

def build_edges(df_filt: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate to one row per liaison with coordinates and KPIs:
    - source/target (lon/lat)
    - on_time_pct, cancel_rate_pct, severe_15_count, circulated
    - precomputed RGBA color and line width
    """
    if df_filt.empty:
        return pd.DataFrame(columns=[
            "liaison", "dep_lon", "dep_lat", "arr_lon", "arr_lat",
            "on_time_pct", "cancel_rate_pct", "severe_15_count", "circulated",
            "color", "width"
        ])

    grp = df_filt.groupby("liaison", as_index=False).agg(
        planned=("planned", "sum"),
        canceled=("canceled", "sum"),
        circulated=("circulated", "sum"),
        late_arr=("late_arr_count", "sum"),
        late_over_15=("late_over_15_count", "sum"),
        dep_lat=("dep_lat", "first"),
        dep_lon=("dep_lon", "first"),
        arr_lat=("arr_lat", "first"),
        arr_lon=("arr_lon", "first"),
        avg_delay_arr_delayed_min=("avg_delay_arr_delayed_min","mean"),
    )

    grp["on_time_pct"] = np.where(grp["circulated"] > 0, (grp["circulated"] - grp["late_arr"]) / grp["circulated"] * 100, np.nan)
    grp["cancel_rate_pct"] = np.where(grp["planned"] > 0, grp["canceled"] / grp["planned"] * 100, np.nan)
    grp["severe_15_count"] = grp["late_over_15"]

    # Drop rows without coordinates
    grp = grp.dropna(subset=["dep_lat", "dep_lon", "arr_lat", "arr_lon"])

    # Edge styling
    # Color ramp: 0% -> red, 100% -> green (simple linear)
    def pct_to_rgba(p):
        if pd.isna(p):  # gray fallback
            return [150, 150, 150, 180]
        p = max(0, min(100, float(p)))
        r = int(round(255 * (100 - p) / 100))
        g = int(round(180 + (75 * p / 100)))  # 180..255, avoids neon
        b = int(round(80 * (100 - p) / 100))  # a bit of blue in low scores
        return [r, g, b, 180]

    grp["color"] = grp["on_time_pct"].map(pct_to_rgba)

    # Width scaling: sqrt(circulated) in [2..12] px
    if len(grp) > 0 and grp["circulated"].max() > 0:
        s = np.sqrt(grp["circulated"].clip(lower=0))
        grp["width"] = 2 + 10 * (s - s.min()) / (s.max() - s.min() + 1e-9)
    else:
        grp["width"] = 4.0

    return grp[[
        "liaison", "dep_lon", "dep_lat", "arr_lon", "arr_lat",
        "on_time_pct", "cancel_rate_pct", "severe_15_count", "circulated",
        "avg_delay_arr_delayed_min",
        "color", "width"
    ]]

# --- Distance helpers (vectorized great-circle) ----------------------------
import numpy as np
from math import radians, sin, cos, asin, sqrt  # kept if you need scalar later

def add_edge_distance_km(edges: pd.DataFrame) -> pd.DataFrame:
    """Vectorized great-circle distance in km between dep and arr; adds 'distance_km'."""
    if edges is None or edges.empty:
        return edges
    e = edges.copy()

    # Prepare arrays
    lat1 = e["dep_lat"].astype(float)
    lon1 = e["dep_lon"].astype(float)
    lat2 = e["arr_lat"].astype(float)
    lon2 = e["arr_lon"].astype(float)

    valid = lat1.notna() & lon1.notna() & lat2.notna() & lon2.notna()
    dist = np.full(len(e), np.nan, dtype=float)
    if valid.any():
        r = 6371.0088  # Earth radius (km)
        φ1 = np.radians(lat1[valid])
        φ2 = np.radians(lat2[valid])
        Δφ = np.radians((lat2 - lat1)[valid])
        Δλ = np.radians((lon2 - lon1)[valid])

        a = np.sin(Δφ/2.0)**2 + np.cos(φ1) * np.cos(φ2) * np.sin(Δλ/2.0)**2
        dist_valid = 2.0 * r * np.arcsin(np.sqrt(a))
        dist[valid.to_numpy()] = dist_valid

    e["distance_km"] = dist
    return e

# --- Station-level metrics --------------------------------------------------
def station_metrics(df_with_coords: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate KPIs at station level (both as departure and arrival).
    Returns columns: [station, lat, lon, circulated, late_arr_count, on_time_pct, late_rate_pct]
    """
    if df_with_coords is None or df_with_coords.empty:
        return pd.DataFrame(columns=["station","lat","lon","circulated","late_arr_count",
                                     "on_time_pct","late_rate_pct"])

    # Build long table of "events" pinned on a station (dep + arr)
    dep = df_with_coords.rename(columns={"departure":"station","dep_lat":"lat","dep_lon":"lon"}).copy()
    arr = df_with_coords.rename(columns={"arrival":"station","arr_lat":"lat","arr_lon":"lon"}).copy()
    keep = ["station","lat","lon","circulated","late_arr_count"]
    dep = dep[keep]
    arr = arr[keep]
    long = pd.concat([dep, arr], axis=0, ignore_index=True)
    long = long.dropna(subset=["lat","lon"])

    g = long.groupby(["station","lat","lon"]).agg(
        circulated=("circulated","sum"),
        late_arr_count=("late_arr_count","sum"),
    ).reset_index()
    g["late_rate_pct"] = np.where(g["circulated"]>0, g["late_arr_count"]/g["circulated"]*100.0, np.nan)
    # Proxy on-time at station: 100 - late_rate (station-level)
    g["on_time_pct"] = 100.0 - g["late_rate_pct"]
    return g

# --- Points for density layers (Hexagon) -----------------------------------
def late_points_for_density(df_with_coords: pd.DataFrame) -> pd.DataFrame:
    """
    Returns per-record points duplicated on dep & arr with weights (= late_arr_count) for HexagonLayer.
    Columns: [lat, lon, weight]
    """
    if df_with_coords is None or df_with_coords.empty:
        return pd.DataFrame(columns=["lat","lon","weight"])
    dep = df_with_coords[["dep_lat","dep_lon","late_arr_count"]].rename(
        columns={"dep_lat":"lat","dep_lon":"lon","late_arr_count":"weight"}
    )
    arr = df_with_coords[["arr_lat","arr_lon","late_arr_count"]].rename(
        columns={"arr_lat":"lat","arr_lon":"lon","late_arr_count":"weight"}
    )
    pts = pd.concat([dep, arr], axis=0, ignore_index=True).dropna(subset=["lat","lon"])
    pts["weight"] = pts["weight"].fillna(0).astype(float)
    return pts