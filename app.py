import streamlit as st
from utils.state import init_state
from utils.io import load_csv_semicolon, maybe_read_parquet, write_parquet
from utils.prep import clean, filter_values
from pathlib import Path
import constants

st.set_page_config(
    page_title="TGV Punctuality Dashboard",
    page_icon=":material/train:",
    layout="wide",
)

# Logo in sidebar
with st.sidebar:
    st.logo("assets/logo.png", icon_image="assets/logo.png")

# Initialize session state
init_state()

# Load data
if "df_clean" not in st.session_state:
    DATA_CSV = f"data/{constants.DATA_FILENAME}"
    PARQUET = f"data/{constants.CLEANED_PARQUET_FILENAME}"

    dfp = maybe_read_parquet(PARQUET)
    if dfp is None:
        try:
            df_raw = load_csv_semicolon(DATA_CSV)
        except FileNotFoundError as e:
            st.error(f"Data file missing. Put your CSV at `{DATA_CSV}` or set secrets.DATA_CSV. {e}")
            st.stop()
        df_clean = clean(df_raw)
        write_parquet(df_clean, PARQUET)
    else:
        df_clean = dfp

    st.session_state.df_clean = df_clean
    st.session_state.filters_catalog = filter_values(df_clean)
    if "date_start" not in st.session_state or "date_end" not in st.session_state:
        opts = st.session_state.filters_catalog.get("date_options", [])
        if opts:
            st.session_state["date_start"] = opts[0]
            st.session_state["date_end"] = opts[-1]


# Pages
pg = st.navigation([
    st.Page("pages/01_Intro.py",               title="Intro & Context",    icon=":material/train:", default=True),
    st.Page("pages/02_Overview.py",            title="Overview",           icon=":material/analytics:"),
    st.Page("pages/03_Routes_Compare.py",      title="Routes Compare",     icon=":material/route:"),
    st.Page("pages/04_Causes_and_Severity.py", title="Causes & Severity",  icon=":material/stacked_bar_chart:"),
    st.Page("pages/05_Geo_View.py",            title="Geo View",           icon=":material/public:"),
    st.Page("pages/06_Data_Quality.py",        title="Data Quality",       icon=":material/award_star:"),
    st.Page("pages/07_Conclusions.py",         title="Conclusions",        icon=":material/check_circle:"),
])

pg.run()