import streamlit as st
import pandas as pd
from datetime import date
import bisect

def _date_opts():
    cat = st.session_state.get("filters_catalog", {})
    return cat.get("date_options", [])

def _services():
    return st.session_state.get("filters_catalog", {}).get("services", ["National", "International"])

def _departures():
    return st.session_state.get("filters_catalog", {}).get("departures", [])

def _arrivals():
    return st.session_state.get("filters_catalog", {}).get("arrivals", [])

def _duration_classes():
    return st.session_state.get("filters_catalog", {}).get("duration_classes", ["< 1h30", "1h30–3h", "> 3h"])

def _date_range_slider(label: str):
    """
    Date range slider using st.slider (dates).
    - Internally uses datetime.date for the widget.
    - Snaps the selection to the list of available months (YYYY-MM) from filters_catalog.
    - Stores only 'date_start' and 'date_end' (YYYY-MM) for downstream code.
    - NEVER writes to the widget's key after instantiation.
    """
    # Allowed months as strings, e.g. ["2018-01", ..., "2020-12"]
    months_str = _date_opts()

    if months_str:
        # Convert to list of datetime.date (first day of month)
        months_dt = [pd.to_datetime(m, format="%Y-%m").date() for m in months_str]

        # Helper: snap any date to the nearest available month in months_dt
        def snap_to_month(d: date) -> date:
            i = bisect.bisect_left(months_dt, d)
            if i <= 0:
                return months_dt[0]
            if i >= len(months_dt):
                return months_dt[-1]
            before = months_dt[i - 1]
            after = months_dt[i]
            # pick the closer one
            return before if abs(d - before) <= abs(after - d) else after

        # INITIAL VALUE (first render only)
        if "date_range_dt" not in st.session_state:
            # derive from existing string keys if present, else full range
            start_s = st.session_state.get("date_start", months_str[0])
            end_s = st.session_state.get("date_end", months_str[-1])
            # sanitize
            if start_s not in months_str:
                start_s = months_str[0]
            if end_s not in months_str:
                end_s = months_str[-1]

            init_val = (pd.to_datetime(start_s, format="%Y-%m").date(),
                        pd.to_datetime(end_s,   format="%Y-%m").date())

            st.sidebar.slider(
                label,
                min_value=months_dt[0],
                max_value=months_dt[-1],
                value=init_val,                 # tuple → range slider
                format="YYYY-MM",               # month display
                key="date_range_dt",
            )
        else:
            # Subsequent reruns: do NOT pass value= to avoid conflicts
            st.sidebar.slider(
                label,
                min_value=months_dt[0],
                max_value=months_dt[-1],
                format="YYYY-MM",
                key="date_range_dt",
            )

        # Read widget value (tuple of dates), snap to nearest allowed months, and expose canonical YYYY-MM
        sel = st.session_state.get("date_range_dt", (months_dt[0], months_dt[-1]))
        if not (isinstance(sel, (list, tuple)) and len(sel) == 2):
            sel = (months_dt[0], months_dt[-1])

        start_dt = snap_to_month(sel[0])
        end_dt = snap_to_month(sel[1])

        # Update only the downstream string keys used by the rest of the app
        st.session_state["date_start"] = pd.to_datetime(start_dt).strftime("%Y-%m")
        st.session_state["date_end"]   = pd.to_datetime(end_dt).strftime("%Y-%m")

    else:
        # Fallback text inputs if no catalog yet
        st.sidebar.text_input("Start month (YYYY-MM)", key="date_start")
        st.sidebar.text_input("End month (YYYY-MM)", key="date_end")

def _stateful_multiselect_service(label: str):
    """
    State-safe multiselect for 'service'.
    - Initializes/clamps selection BEFORE widget creation.
    - Creates the widget WITHOUT `default=`, using only `key="service"`.
    - Does not modify st.session_state['service'] after the widget exists.
    """
    options = _services()

    # Initialize or clamp current selection BEFORE widget creation.
    if "service" in st.session_state:
        current = [v for v in st.session_state["service"] if v in options]
        if not current:
            current = list(options)  # sensible default: all options selected
        st.session_state["service"] = current
    else:
        # First run: select all options by default
        st.session_state["service"] = list(options)

    # Create the widget WITHOUT default=
    st.sidebar.multiselect(
        label,
        options=options,
        key="service",
        placeholder="Choose services",
    )
    # Do not write to st.session_state["service"] after this point.

def _stateful_multiselect_duration(label: str):
    """
    State-safe multiselect for 'duration_class'.
    - Initializes/clamps selection BEFORE widget creation.
    - Creates the widget WITHOUT `default=`, using only `key="duration_class"`.
    - No writes to st.session_state['duration_class'] after the widget exists.
    """
    options = _duration_classes()

    # Initialize or clamp current selection BEFORE widget creation.
    if "duration_class" in st.session_state:
        current = [v for v in st.session_state["duration_class"] if v in options]
        if not current:
            current = list(options)  # sensible default: all selected
        st.session_state["duration_class"] = current
    else:
        st.session_state["duration_class"] = list(options)

    # Create the widget WITHOUT default=
    st.sidebar.multiselect(
        label,
        options=options,
        key="duration_class",
        placeholder="Choose duration classes",
    )
    # Do not write to st.session_state["duration_class"] after this point.

def _stateful_select_metric(label: str):
    """
    State-safe selectbox for 'metric' (Primary metric on Overview).
    - Initializes/clamps selection BEFORE widget creation.
    - Creates the widget WITHOUT `index=` or `default=`, using only `key="metric"`.
    """
    options = [
        "On-time arrival %",
        "Avg arrival delay (delayed trains)",
        "Cancel rate %",
    ]

    # Init/clamp BEFORE widget creation (handles old sessions that had "Severe delays...")
    current = st.session_state.get("metric")
    if current not in options:
        st.session_state["metric"] = options[0]

    st.sidebar.selectbox(
        label,
        options=options,
        key="metric",
        placeholder="Choose a primary metric",
    )

def _stateful_select_color_by(label: str):
    """
    State-safe selectbox for 'color_by' used by the Routes Compare scatter.
    UI shows nice labels; we store the normalized column name in session:
      - "Service"         -> "service"
      - "Duration class"  -> "duration_class"
    """
    ui_options = ["Service", "Duration class"]
    map_to_col = {"Service": "service", "Duration class": "duration_class"}

    # Initialize/clamp BEFORE widget creation
    current = st.session_state.get("color_by_choice")
    if current not in ui_options:
        # default = Service
        st.session_state["color_by_choice"] = "Service"
        st.session_state["color_by"] = "service"
    else:
        # keep normalized mirror in sync (in case of old sessions)
        st.session_state["color_by"] = map_to_col[current]

    # Create widget (no index=)
    st.sidebar.selectbox(
        label,
        options=ui_options,
        key="color_by_choice",
        help="Used to color the performance scatter by service or by duration class.",
    )

    # Mirror to normalized value after widget exists (read-only downstream)
    st.session_state["color_by"] = map_to_col[st.session_state["color_by_choice"]]

def overview_sidebar():
    st.sidebar.header("Overview Filters")
    _date_range_slider("Date range")
    _stateful_multiselect_service("Service")
    _stateful_multiselect_duration("Duration class")
    _stateful_select_metric("Primary metric")

def routes_sidebar():
    st.sidebar.header("Routes Filters")
    _date_range_slider("Date range")
    _stateful_multiselect_service("Service")
    st.sidebar.checkbox("Treat A→B and B→A as the same liaison", key="treat_bidirectional")
    st.sidebar.multiselect("Departure station", options=_departures(), key="departures")
    st.sidebar.multiselect("Arrival station", options=_arrivals(), key="arrivals")
    st.sidebar.selectbox(
        "Ranking metric",
        options=["On-time arrival %", "Avg arrival delay (delayed trains)", "Cancel rate %"],
        key="metric",
    )
    _stateful_select_color_by("Color by")

def causes_sidebar():
    """Sidebar controls for Causes & Severity page."""
    st.sidebar.header("Causes & Severity Filters")
    _date_range_slider("Date range")
    _stateful_multiselect_service("Service")
    _stateful_multiselect_duration("Duration class")  

    st.sidebar.selectbox("Breakdown", options=["Month", "Liaison"], key="causes_breakdown")

    if st.session_state.get("causes_breakdown") == "Liaison":
        st.sidebar.number_input("Top N liaisons", min_value=5, max_value=30, value=10, step=1, key="causes_top_n")

    st.sidebar.selectbox("Severity bucket", options=["≥15", "≥30", "≥60"], index=0, key="severity_bucket")

def geo_sidebar():
    st.sidebar.header("Geo View Filters")
    _date_range_slider("Date range")
    _stateful_multiselect_service("Service")  # <-- use helper
    st.sidebar.checkbox("Treat A→B and B→A as the same liaison", key="treat_bidirectional")
    st.sidebar.multiselect("Departure station", options=_departures(), key="departures")
    st.sidebar.multiselect("Arrival station", options=_arrivals(), key="arrivals")

def dq_sidebar():
    st.sidebar.header("Data Quality Tools")
    _date_range_slider("Date range")

def conclusions_sidebar():
    pass

def intro_sidebar():
    st.sidebar.header("How to use this app")
    st.sidebar.info("Use the page selector above. Each page only shows the filters it needs.")
