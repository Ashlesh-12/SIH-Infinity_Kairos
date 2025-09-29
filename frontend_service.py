# frontend_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from typing import Any, Dict, List, Optional, Tuple

# ------------- CONFIG -------------
DEFAULT_BACKEND_URL = "http://127.0.0.1:5000/api/query"
TEST_BACKEND_URL = "http://127.0.0.1:5000/api/test"
REQUEST_TIMEOUT = 30  # seconds

# ------------- HELPERS -------------
def to_numeric_df(df: pd.DataFrame) -> pd.DataFrame:
    """Try to convert object columns that look numeric to numeric dtype."""
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = pd.to_numeric(df[c], errors="ignore")
    return df

def detect_date_column(df: pd.DataFrame) -> Optional[str]:
    """Return column name if a date-like column exists."""
    for c in df.columns:
        if "date" in c.lower():
            # try strict parse
            try:
                pd.to_datetime(df[c], errors="raise")
                return c
            except Exception:
                parsed = pd.to_datetime(df[c], errors="coerce")
                if parsed.notna().sum() >= max(1, len(parsed) // 4):
                    return c
    return None

def choose_axes(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], str]:
    """
    Heuristics to choose default x and y axes and recommended chart type.
    Returns (x_col, y_col, chart_type) where chart_type in {'line','scatter','bar','table'}.
    """
    df = to_numeric_df(df)
    cols = list(df.columns)
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    # Aggregated single-row -> bar chart of numeric columns
    if len(df) == 1 and numeric_cols:
        return (None, None, "bar")

    # Date-like column -> time series
    date_col = detect_date_column(df)
    if date_col:
        # prefer temperature/salinity/pressure as y
        for pref in ["temperature", "temp", "salinity", "pressure"]:
            for c in cols:
                if pref in c.lower() and c in numeric_cols:
                    return (date_col, c, "line")
        if numeric_cols:
            return (date_col, numeric_cols[0], "line")

    # Pressure-based profile: pressure on y (reversed)
    pressure_col = None
    for c in cols:
        if "pressure" == c.lower() or "pressure" in c.lower():
            pressure_col = c
            break
    if pressure_col:
        for pref in ["temperature", "salinity", "temp"]:
            for c in cols:
                if pref in c.lower() and c in numeric_cols:
                    return (c, pressure_col, "line")
        others = [c for c in numeric_cols if c != pressure_col]
        if others:
            return (others[0], pressure_col, "line")

    # Two numeric columns -> scatter
    if len(numeric_cols) >= 2:
        return (numeric_cols[0], numeric_cols[1], "scatter")

    # No suitable numeric columns -> table
    return (None, None, "table")

def plot_dataframe(df: pd.DataFrame, x: Optional[str], y: Optional[str], chart_type: str):
    """Plot using plotly.express based on chosen chart_type."""
    if chart_type == "bar":
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if not numeric_cols:
            st.dataframe(df)
            return
        bar_df = pd.DataFrame({
            "metric": numeric_cols,
            "value": [float(df.iloc[0][c]) if pd.notna(df.iloc[0][c]) else None for c in numeric_cols]
        })
        fig = px.bar(bar_df, x="metric", y="value", title="Aggregated values")
        st.plotly_chart(fig, use_container_width=True)
        return

    if chart_type in ("line", "scatter"):
        if x is None or y is None:
            st.dataframe(df)
            return

        # Try parse date column if used as x
        if "date" in x.lower():
            try:
                df[x] = pd.to_datetime(df[x], errors="coerce")
            except Exception:
                pass

        if chart_type == "line":
            try:
                df_plot = df.sort_values(by=x)
            except Exception:
                df_plot = df
            fig = px.line(df_plot, x=x, y=y, title=f"{y} vs {x}")
        else:
            fig = px.scatter(df, x=x, y=y, title=f"{y} vs {x}")

        # If pressure on y axis, reverse axis for profile view
        if y and "pressure" in y.lower():
            fig.update_yaxes(autorange="reversed")

        st.plotly_chart(fig, use_container_width=True)
        return

    # fallback to table
    st.dataframe(df)

# ------------- STREAMLIT UI -------------
st.set_page_config(page_title="FloatChat", layout="wide")
st.title("FloatChat: Ocean Data Discovery")
st.markdown("Ask questions about ARGO float data. Frontend auto-generates visualizations when possible.")

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    use_test_endpoint = st.checkbox("Use /api/test endpoint (debug)", value=False)
    backend_url = TEST_BACKEND_URL if use_test_endpoint else DEFAULT_BACKEND_URL
    st.write("Backend URL:")
    st.code(backend_url)
    st.markdown("---")
    st.markdown("Quick example queries")
    if st.button("Show temperature & pressure for float 123"):
        st.session_state._example = "Show temperature and pressure for float 123"
        st.session_state._auto_submit = True
    if st.button("Salinity & pressure near equator"):
        st.session_state._example = "Show salinity and pressure for floats near the equator"
        st.session_state._auto_submit = True
    if st.button("Avg temperature Mar 2002"):
        st.session_state._example = "Average temperature between 2002-03-01 and 2002-03-31"
        st.session_state._auto_submit = True
    st.markdown("---")
    show_raw = st.checkbox("Show raw JSON response", value=False)

# Chat history initialization
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! What ocean data are you curious about?", "data": []}]

# Display chat history
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        data_preview = m.get("data", [])
        if isinstance(data_preview, list) and data_preview:
            try:
                df_preview = pd.DataFrame(data_preview)
                st.dataframe(df_preview.head(5))
            except Exception:
                st.write("Could not preview historical data.")

# Prefill example and auto_submit flag
prefill = st.session_state.pop("_example", "")
auto_submit = st.session_state.pop("_auto_submit", False)

# Input form
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask a question about ARGO data...", value=prefill, key="user_input")
    submit = st.form_submit_button("Send")

do_submit = submit or auto_submit

if do_submit and user_input:
    prompt = user_input.strip()
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Fetching results..."):
        try:
            resp = requests.post(backend_url, json={"query": prompt}, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            response_json: Dict[str, Any] = resp.json()
        except Exception as e:
            response_json = {"summary": f"Error contacting backend: {e}", "data": []}

    # Normalize response
    if isinstance(response_json, str):
        response_json = {"summary": response_json, "data": []}
    if not isinstance(response_json, dict):
        response_json = {"summary": "Invalid response format", "data": []}

    summary = response_json.get("summary") or "No summary returned."
    data = response_json.get("data") or []

    # Show assistant response and visualize data if present
    with st.chat_message("assistant"):
        st.markdown(summary)
        if show_raw:
            st.expander("Raw JSON").write(response_json)

        if isinstance(data, list) and len(data) > 0:
            try:
                df = pd.DataFrame(data)
                df = to_numeric_df(df)

                x_col, y_col, chart_type = choose_axes(df)

                # Provide UI to override axes and chart type when appropriate
                cols_for_select = list(df.columns)
                if chart_type != "bar" and len(cols_for_select) > 1:
                    st.markdown("### Plot controls")
                    date_col = detect_date_column(df)
                    # set sensible defaults
                    default_x = x_col if (x_col in cols_for_select) else cols_for_select[0]
                    default_y = y_col if (y_col in cols_for_select) else (cols_for_select[1] if len(cols_for_select) > 1 else cols_for_select[0])
                    col1, col2 = st.columns(2)
                    with col1:
                        chosen_x = st.selectbox("X axis", options=cols_for_select, index=cols_for_select.index(default_x) if default_x in cols_for_select else 0)
                    with col2:
                        chosen_y = st.selectbox("Y axis", options=cols_for_select, index=cols_for_select.index(default_y) if default_y in cols_for_select else (1 if len(cols_for_select) > 1 else 0))
                    chart_type = st.selectbox("Chart type", options=["line", "scatter", "bar", "table"], index=["line", "scatter", "bar", "table"].index(chart_type) if chart_type in ["line","scatter","bar"] else 0)
                    x_col, y_col = chosen_x, chosen_y

                plot_dataframe(df, x_col, y_col, chart_type)
            except Exception as e:
                st.write(f"Could not visualize returned data: {e}")
        else:
            st.info("The SQL query returned no tabular data to plot.")

    # Save assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": summary, "data": data})
