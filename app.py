import streamlit as st
from pathlib import Path
import os

from utils.state import init_state
from utils.io import load_csv_semicolon, maybe_read_parquet, write_parquet
from utils.prep import clean, filter_values
import constants

try:
    from download_data import download_and_save, DATA_URL
    DOWNLOAD_ENABLED = True
except ImportError:
    st.error("Could not import download function. Manual data download might be required.")
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
        st.sidebar.warning("Logo file not found at assets/logo.png")

init_state()

# --- Load data once (silent version) ---
if "df_clean" not in st.session_state:
    DATA_CSV_PATH = Path(f"data/{constants.DATA_FILENAME}")
    PARQUET_PATH = Path(f"data/{constants.CLEANED_PARQUET_FILENAME}")

    dfp = maybe_read_parquet(PARQUET_PATH)

    if dfp is None:
        # st.info(...) # Removed message
        if not DATA_CSV_PATH.exists():
            if DOWNLOAD_ENABLED:
                # Keep warning for download attempt only if necessary, or remove too
                # st.warning(f"Raw data file ({DATA_CSV_PATH.name}) not found. Attempting download...")
                try:
                    DATA_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
                    # Use a spinner for user feedback during download
                    with st.spinner(f"Downloading required data file: {DATA_CSV_PATH.name}..."):
                        download_and_save(DATA_URL, DATA_CSV_PATH)

                    if not DATA_CSV_PATH.exists():
                        st.error(f"Download failed. Could not retrieve data to {DATA_CSV_PATH}.")
                        st.stop()
                    # else: st.success(...) # Removed message
                except Exception as download_error:
                    st.error(f"An error occurred during download: {download_error}")
                    st.info("Please ensure you have an internet connection or manually place the required CSV file.")
                    st.stop()
            else:
                st.error(f"Raw data file missing at `{DATA_CSV_PATH}` and download function is unavailable.")
                st.stop()

        try:
            df_raw = load_csv_semicolon(DATA_CSV_PATH)
            # st.success(...) # Removed message
        except FileNotFoundError:
            st.error(f"Data file still missing at `{DATA_CSV_PATH}` despite checks.")
            st.stop()
        except Exception as load_error:
            st.error(f"Failed to load or read the CSV file: {load_error}")
            st.stop()

        # Use spinner for cleaning process feedback
        with st.spinner("Cleaning and preparing data..."):
            df_clean = clean(df_raw)
        # st.success(...) # Removed message

        try:
            write_parquet(df_clean, PARQUET_PATH)
            # st.info(...) # Removed message
        except Exception as write_error:
            # Keep warning for write failure, as it impacts performance
            st.warning(f"Could not save cleaned data cache: {write_error}")

    else:
        df_clean = dfp
        # st.success(...) # Removed message

    st.session_state.df_clean = df_clean
    st.session_state.filters_catalog = filter_values(df_clean)

    if "date_start" not in st.session_state or "date_end" not in st.session_state:
        opts = st.session_state.filters_catalog.get("date_options", [])
        if opts:
            st.session_state["date_start"] = opts[0]
            st.session_state["date_end"] = opts[-1]
            # st.info(...) # Removed message

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