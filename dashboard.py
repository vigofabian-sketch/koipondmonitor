"""
Streamlit dashboard for the koi pond monitor (SYNTHETIC data).

Run from repo root, after build_features.py and anomaly_detection.py:
    streamlit run dashboard.py
"""
from pathlib import Path
import pandas as pd
import altair as alt
import streamlit as st

ROOT = Path(__file__).parent
PRED = ROOT / "Data" / "predictions.csv"

st.set_page_config(page_title="Koi Pond Monitor", layout="wide")
st.title("Koi Pond Monitor")
st.warning("Hardware simulated, data synthetic, not deployed. "
           "This dashboard demonstrates the pipeline only.")

if not PRED.exists():
    st.error("Data/predictions.csv not found. Run `python build_features.py` "
             "then `python anomaly_detection.py` first.")
    st.stop()

df = pd.read_csv(PRED, parse_dates=["ts"])

# --- sidebar controls ---
st.sidebar.header("Controls")
sensor = st.sidebar.selectbox("Sensor", ["temp_c", "ph", "turbidity"])
start, end = st.sidebar.slider(
    "Date range",
    min_value=df["ts"].min().to_pydatetime(),
    max_value=df["ts"].max().to_pydatetime(),
    value=(df["ts"].min().to_pydatetime(), df["ts"].max().to_pydatetime()),
)
show_events = st.sidebar.checkbox("Show injected events (ground truth)", True)
view = df[(df["ts"] >= start) & (df["ts"] <= end)]

# --- summary cards ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Readings", f"{len(view):,}")
c2.metric("Isolation Forest flags", int(view["iforest_flag"].sum()))
c3.metric("Threshold flags", int(view["baseline_flag"].sum()))
c4.metric(f"Latest {sensor}", f"{view[sensor].iloc[-1]:.2f}")

# --- main chart ---
line = alt.Chart(view).mark_line(color="steelblue", strokeWidth=1).encode(
    x=alt.X("ts:T", title="Time"), y=alt.Y(f"{sensor}:Q", scale=alt.Scale(zero=False)))
flags = alt.Chart(view[view["iforest_flag"] == 1]).mark_circle(
    color="red", size=22).encode(x="ts:T", y=f"{sensor}:Q",
    tooltip=["ts:T", alt.Tooltip(f"{sensor}:Q")])
chart = line + flags

if show_events:
    ev = (view[view["event_label"] != "none"]
          .groupby("event_id")
          .agg(start=("ts", "min"), end=("ts", "max"), kind=("event_label", "first"))
          .reset_index())
    if len(ev):
        bands = alt.Chart(ev).mark_rect(opacity=0.2, color="orange").encode(
            x="start:T", x2="end:T", tooltip=["kind", "start:T", "end:T"])
        chart = bands + chart

st.altair_chart(chart.properties(height=380).interactive(), width="stretch")
st.caption("Red dots: Isolation Forest flags. Orange bands: injected events (used only for scoring).")

# --- flags by event type ---
st.subheader("Flag rate by event type")
by_type = (view.groupby("event_label")[["iforest_flag", "baseline_flag"]]
           .mean().round(3).rename(columns={
               "iforest_flag": "Isolation Forest", "baseline_flag": "Threshold baseline"}))
st.dataframe(by_type)
st.caption("Share of readings flagged inside each event type. "
           "'none' = false-positive rate on normal readings.")
