import streamlit as st
import pandas as pd
from pathlib import Path

@st.cache_data(show_spinner=False)
def load_csv_semicolon(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path.resolve()}")
    df = pd.read_csv(path, sep=";", encoding="utf-8", low_memory=False)
    return df

@st.cache_data(show_spinner=False)
def maybe_read_parquet(path: str | Path) -> pd.DataFrame | None:
    p = Path(path)
    if p.exists():
        return pd.read_parquet(p)
    return None

@st.cache_data(show_spinner=False)
def write_parquet(df: pd.DataFrame, path: str | Path) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    return str(p.resolve())