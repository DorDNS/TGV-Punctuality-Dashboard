import pandas as pd
import numpy as np

CORE_KEYS = ["date", "service", "departure", "arrival"]

def missingness_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["column", "missing_count", "missing_pct"])
    miss_ct = df.isna().sum().rename("missing_count")
    miss_pct = (df.isna().mean() * 100).round(2).rename("missing_pct")
    out = pd.concat([miss_ct, miss_pct], axis=1).reset_index().rename(columns={"index": "column"})
    return out.sort_values("missing_pct", ascending=False)

def duplicate_keys(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not set(CORE_KEYS).issubset(df.columns):
        return pd.DataFrame(columns=CORE_KEYS + ["count"])
    g = df.groupby(CORE_KEYS, dropna=False).size().reset_index(name="count")
    return g[g["count"] > 1].sort_values("count", ascending=False)

def bounds_issues(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["row_id", "issue", "value"])

    checks = []
    def add_issue(idx, issue, value):
        checks.append({"row_id": int(idx), "issue": issue, "value": value})

    pct_cols = [c for c in df.columns if c.startswith("pct_")]
    count_cols = [c for c in df.columns if c.endswith("_count")] + ["planned", "canceled", "circulated", "late_arr_count"]
    duration_col = "duration_min" if "duration_min" in df.columns else "duration"

    for idx, row in df.iterrows():
        # percentages in [0,100]
        for c in pct_cols:
            v = row[c]
            if pd.notna(v) and (v < 0 or v > 100):
                add_issue(idx, f"{c} outside [0,100]", v)

        # counts >= 0
        for c in count_cols:
            if c in df.columns:
                v = row[c]
                if pd.notna(v) and v < 0:
                    add_issue(idx, f"{c} negative", v)

        # duration > 0
        if duration_col in df.columns:
            v = row[duration_col]
            if pd.notna(v) and v <= 0:
                add_issue(idx, f"{duration_col} non-positive", v)

    return pd.DataFrame(checks)

def logical_consistency(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["row_id", "rule", "details"])

    rules = []
    def add(idx, rule, details):
        rules.append({"row_id": int(idx), "rule": rule, "details": details})

    c15 = "late_over_15_count" if "late_over_15_count" in df.columns else None
    c30 = "late_over_30_count" if "late_over_30_count" in df.columns else None
    c60 = "late_over_60_count" if "late_over_60_count" in df.columns else None

    for idx, r in df.iterrows():
        circ = r["circulated"] if "circulated" in df.columns else np.nan
        late = r["late_arr_count"] if "late_arr_count" in df.columns else np.nan

        if pd.notna(late) and pd.notna(circ) and late > circ:
            add(idx, "late_arr_count ≤ circulated violated", f"{late} > {circ}")

        if c15 and c15 in df.columns and pd.notna(r.get(c15)) and pd.notna(circ) and r[c15] > circ:
            add(idx, "≥15 ≤ circulated violated", f"{r[c15]} > {circ}")

        if c30 and c15 and pd.notna(r.get(c30)) and pd.notna(r.get(c15)) and r[c30] > r[c15]:
            add(idx, "≥30 ≤ ≥15 violated", f"{r[c30]} > {r[c15]}")

        if c60 and c30 and pd.notna(r.get(c60)) and pd.notna(r.get(c30)) and r[c60] > r[c30]:
            add(idx, "≥60 ≤ ≥30 violated", f"{r[c60]} > {r[c30]}")

        # mean(all trains) ≤ mean(delayed only)
        a_all = r.get("avg_delay_arr_all_min", np.nan)
        a_del = r.get("avg_delay_arr_delayed_min", np.nan)
        if pd.notna(a_all) and pd.notna(a_del) and a_all > a_del:
            add(idx, "avg(all) ≤ avg(delayed) violated", f"{a_all} > {a_del}")

    return pd.DataFrame(rules)

def outlier_months(df: pd.DataFrame, method: str = "iqr", threshold: float = 1.5) -> pd.DataFrame:
    if df.empty or "liaison" not in df.columns or "date" not in df.columns:
        return pd.DataFrame(columns=["date", "liaison", "on_time_pct", "flag"])

    d = df.copy()
    if "on_time_pct_row" not in d.columns:
        if {"circulated", "late_arr_count"}.issubset(d.columns):
            d["on_time_pct_row"] = np.where(
                d["circulated"] > 0,
                (d["circulated"] - d["late_arr_count"]) / d["circulated"] * 100.0,
                np.nan,
            )
        else:
            d["on_time_pct_row"] = np.nan

    d["month"] = d["date"].dt.to_period("M").dt.to_timestamp()
    grp = d.dropna(subset=["on_time_pct_row"]).groupby(["liaison", "month"])["on_time_pct_row"].mean().reset_index()

    if grp.empty:
        return pd.DataFrame(columns=["date", "liaison", "on_time_pct", "flag"])

    def flag_group(g):
        if g["on_time_pct_row"].nunique() <= 1:
            g["flag"] = False
            return g
        x = g["on_time_pct_row"]
        if method == "z":
            z = (x - x.mean()) / (x.std(ddof=0) + 1e-9)
            g["flag"] = z < -threshold
        else:
            q1, q3 = x.quantile(0.25), x.quantile(0.75)
            iqr = (q3 - q1) + 1e-9
            lower = q1 - threshold * iqr
            g["flag"] = x < lower
        return g

    flagged = grp.groupby("liaison", group_keys=False).apply(flag_group)
    flagged = flagged[flagged["flag"]].rename(columns={"month": "date", "on_time_pct_row": "on_time_pct"})
    return flagged[["date", "liaison", "on_time_pct", "flag"]].sort_values(["date", "liaison"])