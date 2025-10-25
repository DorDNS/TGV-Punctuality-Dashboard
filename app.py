import streamlit as st
from pathlib import Path
import os
import pandas as pd # Ajouter l'import pandas

from utils.state import init_state
from utils.io import load_csv_semicolon, maybe_read_parquet, write_parquet
from utils.prep import clean, filter_values
import constants

try:
    from download_data import download_and_save, DATA_URL
    DOWNLOAD_ENABLED = True
except ImportError:
    st.error("Could not import download function.")
    DOWNLOAD_ENABLED = False
    def download_and_save(url, path): pass
    DATA_URL = ""


st.set_page_config(
    page_title="TGV Punctuality Dashboard",
    page_icon=":material/train:",
    layout="wide",
)

with st.sidebar:
    logo_path = Path("assets/logo.png")
    if logo_path.exists():
        st.logo(str(logo_path), icon_image=str(logo_path))
    else:
        st.sidebar.warning("Logo file not found.")

init_state()

# --- Load data once with DEBUG messages ---
st.write("--- Debug: Checking data load ---") # DEBUG
if "df_clean" not in st.session_state:
    DATA_CSV_PATH = Path(f"data/{constants.DATA_FILENAME}")
    PARQUET_PATH = Path(f"data/{constants.CLEANED_PARQUET_FILENAME}")
    st.write(f"Debug: Parquet path = {PARQUET_PATH}") # DEBUG
    st.write(f"Debug: CSV path = {DATA_CSV_PATH}") # DEBUG

    dfp = None
    if PARQUET_PATH.exists(): # Vérifier explicitement l'existence
        st.write(f"Debug: Parquet file FOUND at {PARQUET_PATH}.") # DEBUG
        try:
            dfp = maybe_read_parquet(PARQUET_PATH)
            st.write(f"Debug: Successfully loaded Parquet. Shape: {dfp.shape if dfp is not None else 'None'}") # DEBUG
            # Vérifier les dates DANS le parquet chargé
            if dfp is not None and 'date' in dfp.columns:
                 min_date_pq = pd.to_datetime(dfp['date']).min().strftime('%Y-%m')
                 max_date_pq = pd.to_datetime(dfp['date']).max().strftime('%Y-%m')
                 st.write(f"Debug: Parquet data range: {min_date_pq} to {max_date_pq}") # DEBUG

        except Exception as e_pq:
            st.write(f"Debug: Error loading existing Parquet file: {e_pq}. Will try CSV.") # DEBUG
            dfp = None # Forcer le passage au CSV si erreur
    else:
        st.write(f"Debug: Parquet file NOT FOUND at {PARQUET_PATH}.") # DEBUG


    if dfp is None:
        st.write("Debug: Parquet not loaded or not found. Attempting CSV path.") # DEBUG
        if not DATA_CSV_PATH.exists():
            st.write(f"Debug: CSV file NOT FOUND at {DATA_CSV_PATH}.") # DEBUG
            if DOWNLOAD_ENABLED:
                st.write("Debug: Download function is enabled. Attempting download...") # DEBUG
                try:
                    DATA_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with st.spinner(f"Downloading required data file: {DATA_CSV_PATH.name}..."):
                        download_and_save(DATA_URL, DATA_CSV_PATH)

                    if not DATA_CSV_PATH.exists():
                        st.error(f"Download failed. File still missing: {DATA_CSV_PATH}.")
                        st.stop()
                    else:
                        st.write(f"Debug: Download successful. File exists at {DATA_CSV_PATH}.") # DEBUG
                except Exception as download_error:
                    st.error(f"Download error: {download_error}")
                    st.stop()
            else:
                st.error(f"CSV missing at `{DATA_CSV_PATH}` and download unavailable.")
                st.stop()
        else:
             st.write(f"Debug: CSV file FOUND at {DATA_CSV_PATH}.") # DEBUG

        try:
            st.write("Debug: Loading CSV...") # DEBUG
            df_raw = load_csv_semicolon(DATA_CSV_PATH)
            st.write(f"Debug: Loaded CSV. Shape: {df_raw.shape}") # DEBUG
            # Vérifier les dates DANS le CSV chargé
            if 'date' in df_raw.columns:
                 min_date_csv = pd.to_datetime(df_raw['date']).min().strftime('%Y-%m')
                 max_date_csv = pd.to_datetime(df_raw['date']).max().strftime('%Y-%m')
                 st.write(f"Debug: CSV data range: {min_date_csv} to {max_date_csv}") # DEBUG

        except Exception as load_error:
            st.error(f"Failed to load CSV: {load_error}")
            st.stop()

        with st.spinner("Cleaning data..."):
            st.write("Debug: Cleaning data...") # DEBUG
            df_clean = clean(df_raw)
            st.write(f"Debug: Cleaned data. Shape: {df_clean.shape}") # DEBUG
            if 'date' in df_clean.columns:
                 min_date_clean = pd.to_datetime(df_clean['date']).min().strftime('%Y-%m')
                 max_date_clean = pd.to_datetime(df_clean['date']).max().strftime('%Y-%m')
                 st.write(f"Debug: Cleaned data range: {min_date_clean} to {max_date_clean}") # DEBUG


        try:
            st.write(f"Debug: Writing Parquet to {PARQUET_PATH}...") # DEBUG
            write_parquet(df_clean, PARQUET_PATH)
            st.write("Debug: Parquet write successful.") # DEBUG
        except Exception as write_error:
            st.warning(f"Could not save Parquet cache: {write_error}")

    else: # dfp n'est PAS None
        st.write("Debug: Using loaded Parquet data.") # DEBUG
        df_clean = dfp

    st.session_state.df_clean = df_clean
    st.session_state.filters_catalog = filter_values(df_clean)
    st.write("Debug: Data loaded into session state.") # DEBUG

    if "date_start" not in st.session_state or "date_end" not in st.session_state:
        opts = st.session_state.filters_catalog.get("date_options", [])
        if opts:
            st.session_state["date_start"] = opts[0]
            st.session_state["date_end"] = opts[-1]
            st.write(f"Debug: Date range set: {opts[0]} – {opts[-1]}.") # DEBUG
else:
    st.write("Debug: Data already in session state.") # DEBUG

st.write("--- Debug: Data load check complete ---") # DEBUG

# --- Navigation Setup ---
pg = st.navigation([
    st.Page("pages/01_Intro.py",               title="Intro & Context",    icon=":material/train:", default=True),
    st.Page("pages/02_Overview.py",            title="Overview",           icon=":material/analytics:"),
    st.Page("pages/03_Routes_Compare.py",      title="Routes Compare",     icon=":material/route:"),
    st.Page("pages/04_Causes_and_Severity.py", title="Causes & Severity",  icon=":material/stacked_bar_chart:"),
    st.Page("pages/05_Geo_View.py",            title="Geo View",           icon=":material/public:"),
    st.Page("pages/06_Data_Quality.py",        title="Data Quality",       icon=":material/award_star:"),
    st.Page("pages/07_Conclusions.py",         title="Conclusions",        icon=":material/check_circle:"),
])

# --- Run App ---
pg.run()