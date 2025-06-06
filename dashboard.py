import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import time

DB_FILE = "system_monitor.db"
REFRESH_INTERVAL = 10  # seconds

def load_data():
    conn = sqlite3.connect(DB_FILE)
    try:
        system_df = pd.read_sql_query("SELECT * FROM system_metrics ORDER BY timestamp DESC LIMIT 100", conn)
        process_df = pd.read_sql_query("SELECT * FROM process_metrics ORDER BY timestamp DESC LIMIT 500", conn)
        core_df = pd.read_sql_query("SELECT * FROM cpu_core_stats ORDER BY timestamp DESC LIMIT 500", conn)
        sched_df = pd.read_sql_query("SELECT * FROM scheduler_stats ORDER BY timestamp DESC LIMIT 500", conn)
    except Exception as e:
        st.error(f"Error reading DB: {e}")
        return None, None, None, None
    finally:
        conn.close()
    return system_df, core_df, process_df, sched_df

def compute_statistics(system_df, process_df, sched_df):
    stats = {}

    # System-level
    stats["Avg CPU %"] = round(system_df["cpu_percent"].mean(), 2)
    stats["Max CPU %"] = round(system_df["cpu_percent"].max(), 2)
    stats["Avg Mem %"] = round(system_df["memory_percent"].mean(), 2)
    stats["Total Context Switches"] = int(system_df["context_switches"].sum())

    # Process-level
    if process_df is not None and not process_df.empty:
        # Use create_time or fallback to zero
        process_df["create_time"] = process_df.get("create_time", 0)
        uptime = (time.time() - process_df["create_time"]).clip(lower=1)
        process_df["efficiency"] = process_df["cpu_time"] / uptime
        stats["Avg Process Efficiency"] = round(process_df["efficiency"].mean(), 3)
        stats["Avg CPU Time (s)"] = round(process_df["cpu_time"].mean(), 2)
        stats["Max CPU Time (s)"] = round(process_df["cpu_time"].max(), 2)
        stats["Total Context Switches (Processes)"] = int(process_df["ctx_switches"].sum())
    else:
        stats["Avg Process Efficiency"] = "N/A"
        stats["Avg CPU Time (s)"] = "N/A"
        stats["Max CPU Time (s)"] = "N/A"
        stats["Total Context Switches (Processes)"] = "N/A"

    # Scheduler-level
    if sched_df is not None and not sched_df.empty:
        stats["Avg Run Queue Length"] = round(sched_df["run_queue_length"].mean(), 2)
        stats["Max Run Queue Length"] = int(sched_df["run_queue_length"].max())
        stats["Avg Run Time (ms)"] = round(sched_df["run_time_ns"].mean() / 1e6, 2)
    else:
        stats["Avg Run Queue Length"] = "N/A"
        stats["Max Run Queue Length"] = "N/A"
        stats["Avg Run Time (ms)"] = "N/A"

    return stats

def draw_dashboard():
    st.title("📊 Real-time System Monitoring Dashboard")

    try:
        system_df, core_df, process_df, sched_df = load_data()
        if system_df is None:
            st.warning("Waiting for system metrics data...")
            return

        stats = compute_statistics(system_df, process_df, sched_df)

        st.subheader("📌 System Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Avg CPU %", stats["Avg CPU %"])
        col1.metric("Max CPU %", stats["Max CPU %"])
        col2.metric("Avg Mem %", stats["Avg Mem %"])
        col2.metric("Total Context Switches", stats["Total Context Switches"])
        col3.metric("Avg Run Queue Length", stats.get("Avg Run Queue Length", "N/A"))
        col3.metric("Max Run Queue Length", stats.get("Max Run Queue Length", "N/A"))

        st.subheader("🧠 CPU Core Usage")
        if core_df is not None and not core_df.empty:
            # Show latest per-core CPU %
            latest_core = core_df.groupby("core").first().reset_index()
            st.bar_chart(latest_core.set_index("core")["cpu_percent"])
        else:
            st.info("No CPU core data available.")

        st.subheader("⚙️ Per-Process Statistics (Active)")
        if process_df is not None and not process_df.empty:
            # Filter active processes (status not zombie)
            active_procs = process_df[process_df["status"] != "zombie"].copy()
            st.dataframe(
                active_procs[["pid", "name", "user", "status", "cpu_time", "ctx_switches"]]
                .sort_values(by="cpu_time", ascending=False),
                use_container_width=True
            )
        else:
            st.info("No process data available.")

        st.subheader("🧮 Scheduler Stats (Recent)")
        if sched_df is not None and not sched_df.empty:
            sched_display = sched_df[["timestamp", "cpu", "run_queue_length", "context_switches", "run_time_ns"]].copy()
            sched_display["run_time_ms"] = sched_display["run_time_ns"] / 1e6
            st.dataframe(sched_display, use_container_width=True)
        else:
            st.info("No scheduler stats available.")

        st.subheader("📈 Historical CPU/Memory Usage")
        system_df_sorted = system_df.sort_values("timestamp")
        st.line_chart(system_df_sorted[["cpu_percent", "memory_percent"]].reset_index(drop=True))

        st.subheader("📋 Detailed Metrics Summary")
        for k, v in stats.items():
            st.markdown(f"**{k}**: `{v}`")

        st.info(f"Dashboard updates every {REFRESH_INTERVAL} seconds. Scroll down for more tables.")

    except Exception as e:
        st.error(f"Dashboard error: {e}")

    # Auto refresh
    time.sleep(REFRESH_INTERVAL)
    st.experimental_rerun()

if __name__ == "__main__":
    draw_dashboard()