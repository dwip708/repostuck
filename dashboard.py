# dashboard.py

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

DB_FILE = "monitoring.db"

# Page config
st.set_page_config(page_title="Advanced System Monitor", layout="wide")
st.title("🖥️ Advanced System Monitoring Dashboard")

def load_data():
    try:
        conn = sqlite3.connect(DB_FILE)
        df_sys = pd.read_sql_query("SELECT * FROM system_metrics ORDER BY timestamp DESC", conn)
        df_proc = pd.read_sql_query("SELECT * FROM process_metrics ORDER BY timestamp DESC", conn)
        df_core = pd.read_sql_query("SELECT * FROM cpu_core_stats ORDER BY timestamp DESC", conn)
        conn.close()
        return df_sys, df_proc, df_core
    except Exception as e:
        st.error(f"Database read failed: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_sys, df_proc, df_core = load_data()

if df_sys.empty:
    st.warning("No system data available yet.")
    st.stop()

latest_sys = df_sys.iloc[0]

# Display overall system stats
st.header("📊 System Summary")

col1, col2, col3 = st.columns(3)
col1.metric("CPU Usage (%)", f"{latest_sys['cpu_percent']:.2f}")
col2.metric("Memory Usage (%)", f"{latest_sys['memory_percent']:.2f}")
col3.metric("Context Switches", f"{int(latest_sys['context_switches'])}")

col4, col5, col6 = st.columns(3)
col4.metric("Running Processes", f"{int(latest_sys['processes_running'])}")
col5.metric("Sleeping Processes", f"{int(latest_sys['processes_sleeping'])}")
col6.metric("Load Avg (1 min)", f"{latest_sys['load_avg_1']:.2f}")

st.markdown("---")

# Per-core CPU usage
st.header("⚙️ Per-CPU Core Usage")
if not df_core.empty:
    df_latest_core = df_core[df_core['timestamp'] == latest_sys['timestamp']]
    df_latest_core = df_latest_core.sort_values('core')
    st.bar_chart(data=df_latest_core.set_index('core')['cpu_percent'], width=700, height=200)
else:
    st.info("No CPU core data available.")

st.markdown("---")

# Process Stats Table
st.header("🧩 Per-Process Statistics (Live Processes)")

if df_proc.empty:
    st.info("No process data available yet.")
else:
    # Filter latest timestamp
    df_proc_latest = df_proc[df_proc['timestamp'] == latest_sys['timestamp']].copy()

    # Calculate extra stats:
    # Turnaround time = current_time - create_time
    now_ts = datetime.fromisoformat(latest_sys['timestamp'])
    df_proc_latest['turnaround_sec'] = df_proc_latest['create_time'].apply(lambda ct: (now_ts.timestamp() - ct) if ct else 0)

    # Efficiency = cpu_time / turnaround_time (bounded 0..1)
    df_proc_latest['efficiency'] = df_proc_latest.apply(
        lambda r: (r['cpu_time'] / r['turnaround_sec']) if r['turnaround_sec'] > 0 else 0, axis=1)

    # Idle time approx = turnaround_sec - cpu_time
    df_proc_latest['idle_time_sec'] = df_proc_latest['turnaround_sec'] - df_proc_latest['cpu_time']

    # Sort by cpu_time desc
    df_proc_latest = df_proc_latest.sort_values('cpu_time', ascending=False)

    # Select columns and format nicely
    df_display = df_proc_latest[[
        'pid', 'name', 'user', 'status', 'cpu_time', 'ctx_switches',
        'turnaround_sec', 'idle_time_sec', 'efficiency'
    ]].copy()

    df_display.columns = [
        "PID", "Name", "User", "Status", "CPU Time (s)", "Context Switches",
        "Turnaround Time (s)", "Idle Time (s)", "Efficiency (CPU/Turnaround)"
    ]

    st.dataframe(df_display.style.format({
        "CPU Time (s)": "{:.2f}",
        "Turnaround Time (s)": "{:.1f}",
        "Idle Time (s)": "{:.1f}",
        "Efficiency (CPU/Turnaround)": "{:.2%}"
    }), height=400)

st.markdown("---")

# System metrics trends charts
st.header("📈 System Metrics Over Time (Last 500 samples)")

# Prepare time index
df_sys['timestamp'] = pd.to_datetime(df_sys['timestamp'])
df_sys.set_index('timestamp', inplace=True)

cols_to_plot = ['cpu_percent', 'memory_percent', 'context_switches', 'processes_running', 'processes_sleeping']

st.line_chart(df_sys[cols_to_plot])

st.markdown("---")

# Advanced stats summary for system metrics
st.header("📊 Advanced System Statistics")

def stat_summary(col):
    return {
        "Min": df_sys[col].min(),
        "Max": df_sys[col].max(),
        "Average": df_sys[col].mean()
    }

stats = {col: stat_summary(col) for col in cols_to_plot}
stats_df = pd.DataFrame(stats).T
st.table(stats