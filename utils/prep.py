import pandas as pd
import numpy as np

FR_TO_EN = {
    "Date": "date",
    "Service": "service",
    "Gare de départ": "departure",
    "Gare d'arrivée": "arrival",
    "Durée moyenne du trajet": "avg_duration_min",
    "Nombre de circulations prévues": "planned",
    "Nombre de trains annulés": "canceled",
    "Commentaire annulations": "cancel_comment",
    "Nombre de trains en retard au départ": "late_depart_count",
    "Retard moyen des trains en retard au départ": "avg_delay_dep_delayed_min",
    "Retard moyen de tous les trains au départ": "avg_delay_dep_all_min",
    "Commentaire retards au départ": "dep_delay_comment",
    "Nombre de trains en retard à l'arrivée": "late_arr_count",
    "Retard moyen des trains en retard à l'arrivée": "avg_delay_arr_delayed_min",
    "Retard moyen de tous les trains à l'arrivée": "avg_delay_arr_all_min",
    "Commentaire retards à l'arrivée": "arr_delay_comment",
    "Nombre trains en retard > 15min": "late_over_15_count",
    "Retard moyen trains en retard > 15 (si liaison concurrencée par vol)": "avg_delay_over15_min",
    "Nombre trains en retard > 30min": "late_over_30_count",
    "Nombre trains en retard > 60min": "late_over_60_count",
    "Prct retard pour causes externes": "pct_cause_external",
    "Prct retard pour cause infrastructure": "pct_cause_infra",
    "Prct retard pour cause gestion trafic": "pct_cause_traffic",
    "Prct retard pour cause matériel roulant": "pct_cause_rollingstock",
    "Prct retard pour cause gestion en gare et réutilisation de matériel": "pct_cause_station_reuse",
    "Prct retard pour cause prise en compte voyageurs (affluence, gestions PSH, correspondances)": "pct_cause_passengers",
}

NUMERIC_INT = [
    "avg_duration_min", "planned", "canceled",
    "late_depart_count", "late_arr_count",
    "late_over_15_count", "late_over_30_count", "late_over_60_count",
]

NUMERIC_FLOAT = [
    "avg_delay_dep_delayed_min", "avg_delay_dep_all_min",
    "avg_delay_arr_delayed_min", "avg_delay_arr_all_min",
    "avg_delay_over15_min",
    "pct_cause_external", "pct_cause_infra", "pct_cause_traffic",
    "pct_cause_rollingstock", "pct_cause_station_reuse", "pct_cause_passengers",
]

def _coerce_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")

def _coerce_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype(float)

def _duration_class(mins: float | int) -> str:
    if pd.isna(mins):
        return "unknown"
    if mins < 90:
        return "< 1h30"
    if mins <= 180:
        return "1h30–3h"
    return "> 3h"

def clean(df_raw: pd.DataFrame) -> pd.DataFrame:
    # Rename columns
    df = df_raw.rename(columns=FR_TO_EN).copy()

    # Parse date as first day of month
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m")

    # Coerce numeric columns
    for col in NUMERIC_INT:
        if col in df.columns:
            df[col] = _coerce_int(df[col])
    for col in NUMERIC_FLOAT:
        if col in df.columns:
            df[col] = _coerce_float(df[col])

    # Derived fields
    df["liaison"] = df["departure"].astype(str) + " → " + df["arrival"].astype(str)
    df["duration_class"] = df["avg_duration_min"].apply(_duration_class)

    # Circulated = planned - canceled (>= 0)
    df["circulated"] = (df["planned"].fillna(0) - df["canceled"].fillna(0)).clip(lower=0).astype("Int64")

    # Cancel rate (% of planned)
    with np.errstate(divide="ignore", invalid="ignore"):
        df["cancel_rate_pct"] = np.where(
            df["planned"] > 0,
            100 * df["canceled"].fillna(0) / df["planned"],
            np.nan
        )

    # Sanity checks flags
    df["check_late_chain_ok"] = (
        (df["late_over_60_count"].fillna(0) <= df["late_over_30_count"].fillna(0)) &
        (df["late_over_30_count"].fillna(0) <= df["late_over_15_count"].fillna(0)) &
        (df["late_over_15_count"].fillna(0) <= df["circulated"].fillna(0))
    )

    # Bounds for cause percentages
    cause_cols = [
        "pct_cause_external", "pct_cause_infra", "pct_cause_traffic",
        "pct_cause_rollingstock", "pct_cause_station_reuse", "pct_cause_passengers"
    ]
    for c in cause_cols:
        if c in df.columns:
            df[f"check_bounds_{c}"] = df[c].between(0, 100) | df[c].isna()

    return df

def filter_values(df: pd.DataFrame) -> dict:
    dates = pd.to_datetime(df["date"].dropna().unique())
    dates_sorted = sorted(dates)
    services = sorted([s for s in df["service"].dropna().unique()])
    departures = sorted([s for s in df["departure"].dropna().unique()])
    arrivals = sorted([s for s in df["arrival"].dropna().unique()])
    duration_classes = ["< 1h30", "1h30–3h", "> 3h"]  # stable definition

    return {
        "date_min": dates_sorted[0] if dates_sorted else None,
        "date_max": dates_sorted[-1] if dates_sorted else None,
        "date_options": [d.strftime("%Y-%m") for d in dates_sorted],
        "services": services,
        "departures": departures,
        "arrivals": arrivals,
        "duration_classes": duration_classes,
    }