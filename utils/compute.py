import streamlit as st
import pandas as pd
import numpy as np
from typing import Optional

def _between_ym(df: pd.DataFrame, start_ym: str, end_ym: str) -> pd.Series:
    start = pd.to_datetime(start_ym, format="%Y-%m", errors="coerce")
    end = pd.to_datetime(end_ym, format="%Y-%m", errors="coerce")
    return (df["date"] >= start) & (df["date"] <= end)

def _normalize_pair_cols(df: pd.DataFrame) -> pd.DataFrame:
    dep = df["departure"].astype(str)
    arr = df["arrival"].astype(str)
    left_first = (dep <= arr)
    df = df.copy()
    df["dep_norm"] = np.where(left_first, dep, arr)
    df["arr_norm"] = np.where(left_first, arr, dep)
    df["liaison_norm"] = df["dep_norm"] + " ↔ " + df["arr_norm"]
    return df

def apply_overview_filters(df: pd.DataFrame, session) -> pd.DataFrame:
    mask = _between_ym(df, session["date_start"], session["date_end"])
    if session.get("service"):
        mask &= df["service"].isin(session["service"])
    if session.get("duration_class"):
        mask &= df["duration_class"].isin(session["duration_class"])

    # Station filters
    dep_sel = session.get("departures", []) or []
    arr_sel = session.get("arrivals", []) or []
    treat_bi = bool(session.get("treat_bidirectional", False))

    if dep_sel or arr_sel:
        if treat_bi:
            # Match by endpoints regardless of direction
            m_dep = True if not dep_sel else (df["departure"].isin(dep_sel) | df["arrival"].isin(dep_sel))
            m_arr = True if not arr_sel else (df["departure"].isin(arr_sel) | df["arrival"].isin(arr_sel))
            mask &= (m_dep & m_arr)
        else:
            if dep_sel:
                mask &= df["departure"].isin(dep_sel)
            if arr_sel:
                mask &= df["arrival"].isin(arr_sel)

    return df.loc[mask].copy()

def kpis_overview(df_filt: pd.DataFrame) -> dict:
    if df_filt.empty:
        return {"on_time_pct": np.nan, "cancel_rate_pct": np.nan, "avg_arr_delay_delayed": np.nan}

    total_planned = df_filt["planned"].fillna(0).sum()
    total_canceled = df_filt["canceled"].fillna(0).sum()
    total_circulated = df_filt["circulated"].fillna(0).sum()
    total_late_arr = df_filt["late_arr_count"].fillna(0).sum()

    on_time_pct = ( (total_circulated - total_late_arr) / total_circulated * 100.0 ) if total_circulated > 0 else np.nan
    cancel_rate_pct = ( total_canceled / total_planned * 100.0 ) if total_planned > 0 else np.nan

    delays = df_filt["avg_delay_arr_delayed_min"].astype(float)
    weights = df_filt["late_arr_count"].fillna(0).astype(float)
    w = weights.sum()
    avg_arr_delay_delayed = float((delays * weights).sum() / w) if w > 0 else np.nan

    return {"on_time_pct": on_time_pct, "cancel_rate_pct": cancel_rate_pct, "avg_arr_delay_delayed": avg_arr_delay_delayed}

def monthly_series(df_filt: pd.DataFrame) -> pd.DataFrame:
    if df_filt.empty:
        return pd.DataFrame(columns=["date", "on_time_pct", "cancel_rate_pct"])
    g = df_filt.groupby(df_filt["date"].dt.to_period("M")).agg(
        planned=("planned","sum"), canceled=("canceled","sum"),
        circulated=("circulated","sum"), late_arr=("late_arr_count","sum"),
    )
    g.index = g.index.to_timestamp()
    g["on_time_pct"] = np.where(g["circulated"]>0,(g["circulated"]-g["late_arr"])/g["circulated"]*100.0,np.nan)
    g["cancel_rate_pct"] = np.where(g["planned"]>0,g["canceled"]/g["planned"]*100.0,np.nan)
    return g.reset_index()[["date","on_time_pct","cancel_rate_pct"]]

def duration_small_multiples(df_filt: pd.DataFrame) -> pd.DataFrame:
    if df_filt.empty:
        return pd.DataFrame(columns=["date","duration_class","on_time_pct"])
    gp = df_filt.groupby([df_filt["date"].dt.to_period("M"), "duration_class"]).agg(
        circulated=("circulated","sum"), late_arr=("late_arr_count","sum"),
    )
    gp["on_time_pct"] = np.where(gp["circulated"]>0,(gp["circulated"]-gp["late_arr"])/gp["circulated"]*100.0,np.nan)
    gp = gp.reset_index()
    gp["date"] = gp["date"].dt.to_timestamp()
    return gp[["date","duration_class","on_time_pct"]]

def liaison_ranking(df_filt: pd.DataFrame, metric: str, treat_bidirectional: bool, top_n: int = 10):
    if df_filt.empty:
        return pd.DataFrame(), pd.DataFrame()

    if treat_bidirectional:
        df = _normalize_pair_cols(df_filt)
        group_key = "liaison_norm"
    else:
        df = df_filt.copy()
        group_key = "liaison"

    g = df.groupby(group_key).agg(
        planned=("planned", "sum"),
        canceled=("canceled", "sum"),
        circulated=("circulated", "sum"),
        late_arr=("late_arr_count", "sum"),
        avg_delay_arr_delayed_min=("avg_delay_arr_delayed_min", "mean"),
    )

    g["on_time_pct"] = np.where(
        g["circulated"] > 0, (g["circulated"] - g["late_arr"]) / g["circulated"] * 100.0, np.nan
    )
    g["cancel_rate_pct"] = np.where(
        g["planned"] > 0, g["canceled"] / g["planned"] * 100.0, np.nan
    )

    metric_map = {
        "On-time arrival %": "on_time_pct",
        "Avg arrival delay (delayed trains)": "avg_delay_arr_delayed_min",
        "Cancel rate %": "cancel_rate_pct",
    }
    col = metric_map.get(metric, "on_time_pct")

    g.index.name = "liaison"

    g = g.sort_values(col, ascending=(col != "on_time_pct"))
    g["rank_metric"] = g[col]

    top = g.head(top_n).copy()
    bottom = g.tail(top_n).copy()
    return top, bottom

def delay_distribution(df_filt: pd.DataFrame) -> pd.DataFrame:
    if df_filt.empty:
        return pd.DataFrame()
    return df_filt[["duration_class", "avg_delay_arr_delayed_min"]].dropna()

def causes_composition(df_filt: pd.DataFrame, breakdown: str, top_n: Optional[int] = None): # Use Optional
    if df_filt.empty:
        return pd.DataFrame(columns=["group", "cause", "pct"])

    # weights
    w = df_filt["late_arr_count"].fillna(0).astype(float)

    # keep cause columns that exist
    cause_cols = [c for c in [
        "pct_cause_external", "pct_cause_infra", "pct_cause_traffic",
        "pct_cause_rollingstock", "pct_cause_station_reuse", "pct_cause_passengers"
    ] if c in df_filt.columns]

    if not cause_cols:
        return pd.DataFrame(columns=["group", "cause", "pct"])

    df = df_filt.copy()
    df["_w"] = w

    # Group key
    if breakdown == "Month":
        df["_group"] = df["date"].dt.to_period("M").dt.to_timestamp()
    else:  
        df["_group"] = df["liaison"]

    # Weighted mean per group: sum(pct * w) / sum(w)
    weighted = df[cause_cols].multiply(df["_w"], axis=0)
    num = weighted.groupby(df["_group"]).sum()
    den = df.groupby("_group")["_w"].sum().replace(0, np.nan)
    comp_wide = num.divide(den, axis=0) 

    liaison_volume = None
    if breakdown == "Liaison":
        liaison_volume = df.groupby("_group")["circulated"].sum().sort_values(ascending=False)

    if breakdown == "Liaison" and top_n is not None and liaison_volume is not None:
        keep = liaison_volume.index[:top_n]
        comp_wide = comp_wide.loc[comp_wide.index.intersection(keep)]
        # Ensure liaison_volume only contains the kept liaisons for sorting
        liaison_volume = liaison_volume.loc[keep]


    comp = comp_wide.reset_index().rename(columns={"_group": "group"})
    comp = comp.melt(id_vars="group", var_name="cause", value_name="pct")

    label_map = {
        "pct_cause_external": "External",
        "pct_cause_infra": "Infrastructure",
        "pct_cause_traffic": "Traffic management",
        "pct_cause_rollingstock": "Rolling stock",
        "pct_cause_station_reuse": "Station ops & reuse",
        "pct_cause_passengers": "Passengers / PSH / connections",
    }
    comp["cause"] = comp["cause"].map(label_map).fillna(comp["cause"])

    if breakdown == "Liaison" and liaison_volume is not None:
        ordered_liaisons = liaison_volume.index.tolist()
        comp['group'] = pd.Categorical(comp['group'], categories=ordered_liaisons, ordered=True)
        comp = comp.sort_values('group')

    return comp

def severe_counts(df_filt: pd.DataFrame, breakdown: str, bucket: str, top_n: int | None = None):
    if df_filt.empty:
        return pd.DataFrame(columns=["group", "count"])

    col_map = {"≥15": "late_over_15_count", "≥30": "late_over_30_count", "≥60": "late_over_60_count"}
    col = col_map.get(bucket) 

    # Ensure the target column exists before proceeding
    if not col or col not in df_filt.columns:
        st.warning(f"Column '{col}' for severity bucket '{bucket}' not found in data. Cannot compute severe counts.")
        return pd.DataFrame(columns=["group", "count"])

    df = df_filt.copy()
    if breakdown == "Month":
        df["_group"] = df["date"].dt.to_period("M").dt.to_timestamp()
    else: 
        df["_group"] = df["liaison"]

    # Perform the aggregation
    g = df.groupby("_group")[col].sum().reset_index().rename(columns={"_group": "group", col: "count"})

    # Filter for Top N 
    if breakdown == "Liaison" and top_n is not None:
        if "circulated" in df.columns:
            vol = df.groupby("_group")["circulated"].sum().sort_values(ascending=False)
            keep = list(vol.index[:top_n])
            g = g[g["group"].isin(keep)]
        else:
             st.warning("Cannot determine Top N liaisons by volume: 'circulated' column missing.")
             g = g.sort_values("count", ascending=False).head(top_n)

    g = g.sort_values("count", ascending=False)

    return g

def liaison_summary(df_filt: pd.DataFrame, treat_bidirectional: bool = False) -> pd.DataFrame:
    if df_filt.empty:
        return pd.DataFrame(columns=[
            "liaison","service","duration_class","planned","canceled","circulated","late_arr_count",
            "on_time_pct","cancel_rate_pct","late_rate_pct","avg_delay_arr_delayed_min"
        ])

    if treat_bidirectional:
        df = _normalize_pair_cols(df_filt)
        key = "liaison_norm"
    else:
        df = df_filt.copy()
        key = "liaison"

    # Helper for mode
    def _mode(s: pd.Series):
        return s.mode().iloc[0] if not s.mode().empty else None

    g = df.groupby(key).agg(
        planned=("planned","sum"),
        canceled=("canceled","sum"),
        circulated=("circulated","sum"),
        late_arr_count=("late_arr_count","sum"),
        avg_delay_arr_delayed_min=("avg_delay_arr_delayed_min","mean"),
        service=("service", _mode),
        duration_class=("duration_class", _mode),
    )

    g["on_time_pct"] = np.where(
        g["circulated"] > 0,
        (g["circulated"] - g["late_arr_count"]) / g["circulated"] * 100.0,
        np.nan
    )
    g["cancel_rate_pct"] = np.where(
        g["planned"] > 0, g["canceled"] / g["planned"] * 100.0, np.nan
    )
    g["late_rate_pct"] = np.where(
        g["circulated"] > 0, g["late_arr_count"] / g["circulated"] * 100.0, np.nan
    )

    g.index.name = "liaison"
    g = g.reset_index()
    return g[[
        "liaison","service","duration_class","planned","canceled","circulated","late_arr_count",
        "on_time_pct","cancel_rate_pct","late_rate_pct","avg_delay_arr_delayed_min"
    ]]

def _cause_cols_in(df):
    candidates = [
        "pct_cause_external", "pct_cause_infra", "pct_cause_traffic",
        "pct_cause_rollingstock", "pct_cause_station_reuse", "pct_cause_passengers"
    ]
    return [c for c in candidates if c in df.columns]

_CAUSE_LABELS = {
    "pct_cause_external": "External",
    "pct_cause_infra": "Infrastructure",
    "pct_cause_traffic": "Traffic",
    "pct_cause_rollingstock": "Rolling stock",
    "pct_cause_station_reuse": "Station ops & reuse",
    "pct_cause_passengers": "Passengers / PSH / connections",
}

def causes_pivot_monthly(df_filt: pd.DataFrame) -> pd.DataFrame:
    import numpy as np
    import pandas as pd

    if df_filt.empty:
        return pd.DataFrame()

    cause_cols = _cause_cols_in(df_filt)
    if not cause_cols:
        return pd.DataFrame()

    df = df_filt.copy()
    df["_month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    df["_w"] = df["late_arr_count"].fillna(0).astype(float)

    weighted = df[cause_cols].fillna(0).multiply(df["_w"], axis=0)
    num = weighted.groupby(df["_month"]).sum()
    den = df.groupby("_month")["_w"].sum().replace(0, np.nan)

    comp = num.divide(den, axis=0)

    # Normalize each month to 100%
    row_sum = comp.sum(axis=1).replace(0, np.nan)
    comp = comp.divide(row_sum, axis=0).multiply(100)

    comp = comp.rename(columns=_CAUSE_LABELS)
    comp.index.name = "month"
    return comp.reset_index()


def causes_by_attr(df_filt: pd.DataFrame, attr: str) -> pd.DataFrame:
    import numpy as np
    import pandas as pd

    if df_filt.empty or attr not in df_filt.columns:
        return pd.DataFrame(columns=["group", "cause", "pct"])

    cause_cols = _cause_cols_in(df_filt)
    if not cause_cols:
        return pd.DataFrame(columns=["group", "cause", "pct"])

    df = df_filt.copy()
    df["_w"] = df["late_arr_count"].fillna(0).astype(float)

    # Numerators: sum(pct * w) per group for each cause
    weighted = df[cause_cols].fillna(0).multiply(df["_w"], axis=0)
    num = weighted.groupby(df[attr]).sum()

    # Denominator: sum(w) per group (avoid /0)
    den = df.groupby(attr)["_w"].sum().replace(0, np.nan)

    # Weighted mean in %
    comp = num.divide(den, axis=0)

    row_sum = comp.sum(axis=1).replace(0, np.nan)
    comp = comp.divide(row_sum, axis=0).multiply(100)

    comp = comp.reset_index().rename(columns={attr: "group"})
    comp = comp.melt(id_vars="group", var_name="cause", value_name="pct")
    comp["cause"] = comp["cause"].map(_CAUSE_LABELS).fillna(comp["cause"])
    comp["pct"] = comp["pct"].fillna(0)

    comp["group"] = comp["group"].astype("category")
    return comp

def severity_profile_by_cause(df_filt: pd.DataFrame) -> pd.DataFrame:
    if df_filt.empty:
        return pd.DataFrame(columns=["cause", "bucket", "pct"])

    # Map causes
    cause_cols = [c for c in [
        "pct_cause_external", "pct_cause_infra", "pct_cause_traffic",
        "pct_cause_rollingstock", "pct_cause_station_reuse", "pct_cause_passengers"
    ] if c in df_filt.columns]
    if not cause_cols:
        return pd.DataFrame(columns=["cause", "bucket", "pct"])

    label_map = {
        "pct_cause_external": "External",
        "pct_cause_infra": "Infrastructure",
        "pct_cause_traffic": "Traffic",
        "pct_cause_rollingstock": "Rolling stock",
        "pct_cause_station_reuse": "Station ops & reuse",
        "pct_cause_passengers": "Passengers / PSH / connections",
    }

    # Severity buckets
    candidates = {
        "≥15": "late_over_15_count",
        "≥30": "late_over_30_count",
        "≥60": "late_over_60_count",
    }
    buckets = {k: v for k, v in candidates.items() if v in df_filt.columns}
    if not buckets:
        return pd.DataFrame(columns=["cause", "bucket", "pct"])

    df = df_filt.copy()
    # Weighted contribution of each cause to each bucket:
    out = []
    for b_name, b_col in buckets.items():
        for c in cause_cols:
            num = (df[c].fillna(0).astype(float) * df[b_col].fillna(0).astype(float)).sum()
            den = df[b_col].fillna(0).sum()
            pct = float(num / den * 100.0) if den > 0 else np.nan
            out.append({"cause": label_map.get(c, c), "bucket": b_name, "pct": round(pct, 1)})

    return pd.DataFrame(out)

def liaison_cause_dominance_summary(df_filt: pd.DataFrame, treat_bidirectional: bool = True) -> pd.DataFrame:
    if df_filt.empty:
        return pd.DataFrame()

    # Direction handling
    if treat_bidirectional and {"departure","arrival"}.issubset(df_filt.columns):
        dep = df_filt["departure"].astype(str)
        arr = df_filt["arrival"].astype(str)
        left_first = (dep <= arr)
        df = df_filt.copy()
        df["liaison_key"] = np.where(left_first, dep + " ↔ " + arr, arr + " ↔ " + dep)
    else:
        df = df_filt.copy()
        df["liaison_key"] = df.get("liaison", df["departure"].astype(str) + " → " + df["arrival"].astype(str))

    # KPIs
    g = df.groupby("liaison_key").agg(
        planned=("planned","sum"),
        canceled=("canceled","sum"),
        circulated=("circulated","sum"),
        late=("late_arr_count","sum"),
        avg_delay_arr_delayed_min=("avg_delay_arr_delayed_min","mean"),
    )
    g["on_time_pct"] = np.where(g["circulated"]>0,(g["circulated"]-g["late"])/g["circulated"]*100.0,np.nan)

    # Dominant cause
    cause_cols = [c for c in [
        "pct_cause_external","pct_cause_infra","pct_cause_traffic",
        "pct_cause_rollingstock","pct_cause_station_reuse","pct_cause_passengers"
    ] if c in df.columns]
    label_map = {
        "pct_cause_external": "External",
        "pct_cause_infra": "Infrastructure",
        "pct_cause_traffic": "Traffic",
        "pct_cause_rollingstock": "Rolling stock",
        "pct_cause_station_reuse": "Station ops & reuse",
        "pct_cause_passengers": "Passengers / PSH / connections",
    }

    if cause_cols:
        # weighted mean per liaison for each cause
        w = df["late_arr_count"].fillna(0).astype(float)
        w = np.where(np.isfinite(w), w, 0.0)
        wm = {}
        for c in cause_cols:
            val = (df[c].fillna(0).astype(float) * w).groupby(df["liaison_key"]).sum()
            den = pd.Series(w, index=df.index).groupby(df["liaison_key"]).sum().replace(0, np.nan)
            wm[c] = (val / den) * 100.0
        wm_df = pd.DataFrame(wm)
        dom = wm_df.idxmax(axis=1).map(label_map)
        g["dominant_cause"] = dom

    g = g.reset_index().rename(columns={"liaison_key":"liaison","late":"late_arr_count"})
    return g[["liaison","on_time_pct","avg_delay_arr_delayed_min","late_arr_count","dominant_cause"]]