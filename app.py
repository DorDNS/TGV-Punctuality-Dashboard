import streamlit as st
from pathlib import Path
import os
import pandas as pd

# Import project modules
from utils.state import init_state
from utils.io import load_csv_semicolon, maybe_read_parquet, write_parquet
from utils.prep import clean, filter_values
import constants

# Attempt to import download function
try:
    from download_data import download_and_save, DATA_URL
    DOWNLOAD_ENABLED = True
except ImportError:
    st.error("Could not import download function. Manual data download might be required.")
    DOWNLOAD_ENABLED = False
    def download_and_save(url, path): pass
    DATA_URL = ""

# Page config
st.set_page_config(
    page_title="TGV Punctuality Dashboard",
    page_icon=":material/train:",
    layout="wide",
)

# Sidebar Logo
with st.sidebar:
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        st.logo(str(logo_path), icon_image=str(logo_path))
    else:
        st.sidebar.warning("Logo file not found at assets/logo.png")

# Initialize Session State
init_state()

# Load data once per session
if "df_clean" not in st.session_state:
    # File paths
    DATA_CSV_PATH = Path(f"data/{constants.DATA_FILENAME}")
    PARQUET_PATH = Path(f"data/{constants.CLEANED_PARQUET_FILENAME}")

    dfp = None
    # Check if Parquet cache exists
    if PARQUET_PATH.exists():
        try:
            dfp = maybe_read_parquet(PARQUET_PATH)
        except Exception as e_pq:
            st.warning(f"Could not load Parquet cache ({PARQUET_PATH.name}): {e_pq}. Processing raw data.")
            dfp = None

    # If Parquet wasn't loaded
    if dfp is None:
        # Check if the raw CSV exists, download if missing
        if not DATA_CSV_PATH.exists():
            if DOWNLOAD_ENABLED:
                try:
                    DATA_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with st.spinner(f"Downloading required data file: {DATA_CSV_PATH.name}..."):
                        download_and_save(DATA_URL, DATA_CSV_PATH)
                    if not DATA_CSV_PATH.exists():
                        st.error(f"Download failed: {DATA_CSV_PATH}. Place file manually or check connection.")
                        st.stop()
                except Exception as download_error:
                    st.error(f"Download error: {download_error}")
                    st.stop()
            else:
                st.error(f"Raw data file missing at `{DATA_CSV_PATH}` and download unavailable.")
                st.stop()

        # Load the CSV
        try:
            df_raw = load_csv_semicolon(DATA_CSV_PATH)
        except Exception as load_error:
            st.error(f"Failed to load CSV file: {load_error}")
            st.stop()

        # Clean the data
        with st.spinner("Cleaning and preparing data..."):
            df_clean = clean(df_raw)

        # Attempt to save cleaned data to Parquet
        try:
            write_parquet(df_clean, PARQUET_PATH)
        except Exception as write_error:
            st.warning(f"Could not save Parquet cache ({PARQUET_PATH.name}): {write_error}")

    else: 
        df_clean = dfp

    # Store and prepare filters
    st.session_state.df_clean = df_clean
    st.session_state.filters_catalog = filter_values(df_clean)

    # Initialize date range filters
    if "date_start" not in st.session_state or "date_end" not in st.session_state:
        opts = st.session_state.filters_catalog.get("date_options", [])
        if opts:
            st.session_state["date_start"] = opts[0]
            st.session_state["date_end"] = opts[-1]

# Pages navigation
pg = st.navigation([
    st.Page("pages/01_Intro.py",               title="Intro & Context",    icon=":material/train:", default=True),
    st.Page("pages/02_Overview.py",            title="Overview",           icon=":material/analytics:"),
    st.Page("pages/03_Routes_Compare.py",      title="Routes Compare",     icon=":material/route:"),
    st.Page("pages/04_Causes_and_Severity.py", title="Causes & Severity",  icon=":material/stacked_bar_chart:"),
    st.Page("pages/05_Geo_View.py",            title="Geo View",           icon=":material/public:"),
    st.Page("pages/06_Data_Quality.py",        title="Data Quality",       icon=":material/award_star:"),
    st.Page("pages/07_Conclusions.py",         title="Conclusions",        icon=":material/check_circle:"),
])

# Run the selected page
pg.run()