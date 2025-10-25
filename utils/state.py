import streamlit as st

def init_state():
    defaults = {
        # Date range filter
        "service": ["National", "International"],
        "treat_bidirectional": True,
        "duration_class": ["< 1h30", "1h30–3h", "> 3h"],

        # Station filters
        "departures_query": "",
        "arrivals_query": "",

        # Metric selector
        "metric": "On-time arrival %",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)