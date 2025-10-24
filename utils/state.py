import streamlit as st

def init_state():
    """Initialize shared state; page-specific sidebars will write into these keys later."""
    defaults = {
        # Do NOT set date_start / date_end here → sidebar will init from data range
        "service": ["National", "International"],
        "treat_bidirectional": True,
        "duration_class": ["< 1h30", "1h30–3h", "> 3h"],

        # Station filters (used by Overview/Routes/Geo)
        "departures_query": "",
        "arrivals_query": "",

        # Metric selector (Overview/Routes)
        "metric": "On-time arrival %",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)