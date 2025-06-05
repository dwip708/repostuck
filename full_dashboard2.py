# full_dashboard.py

import streamlit as st
import sqlite3
import pandas as pd
import psutil
import plotly.express as px
from datetime import datetime
import time

DB_FILE = "monitoring.db"

st.set_page_config(page_title="🖥️ Linux Scheduler Monitor Dashboard", layout="wide")
st.title(":desktop_computer: Linux Scheduler Monitor Dashboard")

# Auto-refresh every 10s
st_autorefresh = st.experimental_rerun if 'last_refresh' in st.session_state and (time.time() - st.session_state['last_refresh']) >= 10 else None
st.session_state['last_refresh'] = time.time()

# Load DB data
def load_all_data():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            df_sys = pd.read_sql_query("SELECT * FROM system_metrics ORDER BY timestamp DESC LIMIT 500", conn)
            df_proc = pd.read_sql_query("SELECT * FROM process_metrics ORDER BY timestamp DESC LIMIT 1000", conn)
            df_core = pd.read_sql_query("SELECT * FROM cpu_core_stats ORDER BY timestamp DESC LIMIT 500", conn)
            df_events = pd.read_sql_query("SELECT * FROM system_events ORDER BY timestamp DESC LIMIT 100", conn)
            df_sched = pd.read_sql_query("SELECT * FROM scheduler_metrics ORDER BY timestamp DESC LIMIT 500", conn)
            return df_sys, df_proc, df_core, df_events, df_sched
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

st.markdown(f"**Last updated:** {datetime.now().strftime('%I:%M:%S %p')}")
df_sys, df_proc, df_core, df_events, df_sched = load_all_data()

if df_sys.empty:
    st.warning("No system metrics available.")
    st.stop()

latest = df_sys.iloc[0]

# Threshold Alerts
if latest['cpu_percent'] > 90:
    st.error("🚨 High CPU usage detected!")
if latest['memory_percent'] > 90:
    st.warning("⚠️ High memory usage!")

# Overview
st.header(":bar_chart: System Overview")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Processes", f"{int(latest['processes_running'] + latest['processes_sleeping'])}")
col2.metric("Running", f"{int(latest['processes_running'])}")
col3.metric("Blocked", f"{int(latest['processes_sleeping'])}")
col4.metric("Zombie", str(int(latest.get('processes_zombie', 0))))

st.header(":zap: CPU Statistics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Avg CPU Usage", f"{df_sys['cpu_percent'].mean():.1f}%")
col2.metric("Max CPU Usage", f"{df_sys['cpu_percent'].max():.1f}%")
col3.metric("CPU Cores", f"{psutil.cpu_count(logical=True)}")
col4.metric("Load Average", f"{latest['load_avg_1']:.2f}")

# CPU usage over time
st.subheader("CPU Usage Over Time")
fig = px.line(df_sys.sort_values("timestamp"), x="timestamp", y="cpu_percent", title="CPU Usage (%)")
st.plotly_chart(fig, use_container_width=True)

# Context Switch Graph
st.subheader("Context Switches Over Time")
df_sys["context_diff"] = df_sys["context_switches"].diff().fillna(0)
fig2 = px.line(df_sys.sort_values("timestamp"), x="timestamp", y="context_diff", title="Context Switches/sec")
st.plotly_chart(fig2, use_container_width=True)

st.header(":repeat: Context Switches")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Avg/sec", f"{df_sys['context_diff'].mean():.0f}")
col2.metric("Max/sec", f"{df_sys['context_diff'].max():.0f}")
col3.metric("Voluntary", str(int(latest.get('voluntary_ctx_switches', 0))))
col4.metric("Involuntary", str(int(latest.get('involuntary_ctx_switches', 0))))

# Top Processes
st.header(":runner: Top Processes by CPU")
if not df_proc.empty:
    df_now = df_proc[df_proc['timestamp'] == latest['timestamp']]
    df_now = df_now.sort_values(by='cpu_time', ascending=False).head(10)
    df_now['CPU%'] = df_now['cpu_time'] / df_now['cpu_time'].sum() * 100
    df_now['Memory'] = ["{:.1f}MB".format(v) for v in (df_now['cpu_time'] * 10)]
    df_now['Threads'] = df_now.get('threads', 1)
    df_now['Priority'] = df_now.get('priority', 0)
    df_now['Status'] = df_now['status'].str[0].str.upper()
    df_now['Scheduler'] = df_now.get('scheduler', 'CFS')

    st.dataframe(df_now[['Status', 'pid', 'name', 'CPU%', 'Memory', 'Threads', 'Priority', 'Scheduler']].rename(columns={
        'pid': 'PID', 'name': 'Command'
    }), use_container_width=True)
else:
    st.info("No per-process data.")

# Memory
st.header(":floppy_disk: Memory Statistics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Memory", f"{psutil.virtual_memory().total / (1024**3):.1f}GB")
col2.metric("Used Memory", f"{psutil.virtual_memory().used / (1024**3):.1f}GB")
col3.metric("Free Memory", f"{psutil.virtual_memory().available / (1024**3):.1f}GB")
col4.metric("Usage %", f"{latest['memory_percent']:.1f}%")

# Queues
st.header(":clipboard: Scheduler Queues")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Runqueue Size", str(int(latest.get('runqueue_size', 1))))
col2.metric("Load 1min", f"{latest['load_avg_1']:.2f}")
col3.metric("Load 5min", f"{latest['load_avg_5']:.2f}")
col4.metric("Load 15min", f"{latest['load_avg_15']:.2f}")

# Per-core stats
st.header(":dna: Per-Core CPU Stats")
if not df_core.empty:
    df_recent = df_core[df_core['timestamp'] == df_core['timestamp'].max()]
    st.dataframe(df_recent[['core_id', 'usage_percent', 'idle_time', 'irq_time', 'user_time', 'system_time']].rename(columns={
        'core_id': 'Core', 'usage_percent': 'Usage %', 'idle_time': 'Idle', 'irq_time': 'IRQ', 'user_time': 'User', 'system_time': 'System'
    }), use_container_width=True)

# Event logs
st.header(":memo: System Events Log")
if not df_events.empty:
    for _, row in df_events.iterrows():
        st.text(f"{row['timestamp']} - {row['event_type']} PID:{row['pid']} {row['process_name']} - {row['details']}")
else:
    st.info("No event logs available.")

# Efficiency
st.header(":gear: Scheduler Efficiency")
if not df_sched.empty:
    latest_sched = df_sched.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Response Time", f"{latest_sched['avg_response_time']:.2f} ms")
    col2.metric("Throughput", f"{latest_sched['throughput']:.2f} /s")
    col3.metric("Fairness Index", f"{latest_sched['fairness_index']:.3f}")
    col4.metric("Migration Rate", f"{latest_sched['migration_rate']:.2f} /s")
else:
    st.info("Scheduler efficiency data not available.")

st.markdown("---")
st.caption("Made with :heart: using Streamlit")
