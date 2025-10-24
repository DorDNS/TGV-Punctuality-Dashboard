import streamlit as st
from utils.filters import conclusions_sidebar

st.set_page_config(page_title="Conclusions", page_icon=":material/check_circle:", layout="wide")

# Page-specific sidebar (empty/minimal)
conclusions_sidebar()

st.markdown("# Conclusions")
st.markdown(
    """
    We will synthesize the main findings from other sections here,
    and propose actionable next steps for operations and traveler communication.
    """
)
