import streamlit as st
import subprocess
import threading
import time
import re
import pandas as pd
import psutil
import os
from collections import defaultdict

# ----- Streamlit Setup -----
st.set_page_config(page_title="🧠 Full System Monitor", layout="wide")
st.title("📊 Full Real-Time System Monitoring Dashboard")

# ----- Global Data Structures -----
log_lines = []
global_stats = {
    'switches_per_second': [],
    'last_second': int(time.time()),
    'switch_count': 0
}

process_stats = defaultdict(lambda: {
    'total_time_in_cpu': 0.0,
    'last_switch_in': None,
    'context_switches': 0
})


# ----- BPFTRACE Setup -----
def write_bpftrace_script():
    with open("full_stats.bt", "w") as f:
        f.write("""
tracepoint:sched:sched_switch
{
  printf("SWITCH: CPU %d | FROM %s (%d) → TO %s (%d)\\n",
         cpu, args->prev_comm, args->prev_pid, args->next_comm, args->next_pid);
}
tracepoint:sched:sched_wakeup
{
  printf("WAKEUP: CPU %d | %s (%d)\\n",
         cpu, args->comm, args->pid);
}
""")


def parse_bpftrace_output(line):
    now = time.time()
    if "SWITCH" in line:
        match = re.search(r'FROM (.*?) \((\d+)\) → TO (.*?) \((\d+)\)', line)
        if match:
            prev_comm, prev_pid, next_comm, next_pid = match.groups()
            prev_pid, next_pid = int(prev_pid), int(next_pid)

            if process_stats[prev_pid]['last_switch_in']:
                delta = now - process_stats[prev_pid]['last_switch_in']
                process_stats[prev_pid]['total_time_in_cpu'] += delta
                process_stats[prev_pid]['last_switch_in'] = None

            process_stats[next_pid]['last_switch_in'] = now
            process_stats[next_pid]['context_switches'] += 1

            global_stats['switch_count'] += 1
            current_sec = int(now)
            if current_sec != global_stats['last_second']:
                elapsed = now - global_stats['last_second']
                rate = global_stats['switch_count'] / elapsed
                global_stats['switches_per_second'].append(rate)
                global_stats['last_second'] = current_sec
                global_stats['switch_count'] = 0

            log_lines.append(f"SWITCH: {prev_comm}({prev_pid}) → {next_comm}({next_pid})")

    elif "WAKEUP" in line:
        match = re.search(r'WAKEUP: CPU \d+ \| (.*?) \((\d+)\)', line)
        if match:
            comm, pid = match.groups()
            log_lines.append(f"WAKEUP: {comm}({pid})")


def run_bpftrace():
    write_bpftrace_script()
    proc = subprocess.Popen(["sudo", "bpftrace", "full_stats.bt"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True)
    for line in proc.stdout:
        parse_bpftrace_output(line)


threading.Thread(target=run_bpftrace, daemon=True).start()


# ----- System Stats -----
def get_schedstat():
    schedstat_path = "/proc/schedstat"
    if not os.path.exists(schedstat_path):
        return pd.DataFrame()

    data = []
    with open(schedstat_path) as f:
        for i, line in enumerate(f):
            parts = line.strip().split()
            if len(parts) >= 5:
                cpu = f"Core {i}"
                run_time = int(parts[0])
                queue_time = int(parts[1])
                switches = int(parts[2])
                data.append({
                    "CPU": cpu,
                    "RunQueueTime": queue_time,
                    "Switches": switches
                })
    return pd.DataFrame(data)


def cpu_heatmap(cpu_usage):
    n = len(cpu_usage)
    rows = int(n**0.5)
    cols = (n + rows - 1) // rows
    padded = cpu_usage + [0] * (rows * cols - n)
    return pd.DataFrame([padded[i * cols:(i + 1) * cols] for i in range(rows)])


# ----- Dashboard -----
while True:
    time.sleep(1)

    st.empty()
    col1, col2 = st.columns(2)

    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    cpu_percents = psutil.cpu_percent(percpu=True)

    with col1:
        st.subheader("🧠 Memory Usage")
        st.metric("Memory % Used", f"{mem_percent:.2f} %")
        st.progress(mem_percent / 100)

    with col2:
        st.subheader("🧮 Per-Core CPU Usage")
        df = pd.DataFrame({
            "Core": [f"Core {i}" for i in range(len(cpu_percents))],
            "Usage": cpu_percents
        }).set_index("Core")
        st.bar_chart(df)

    # Heatmap
    st.subheader("🌡️ CPU Heatmap")
    st.dataframe(cpu_heatmap(cpu_percents), use_container_width=True)

    # Alerts
    st.subheader("🚨 Alerts")
    if mem_percent > 85:
        st.error("High memory usage detected!")
    if any(p > 90 for p in cpu_percents):
        st.warning("Some cores have high CPU usage!")

    # Context Switches
    st.subheader("🔁 Context Switch Statistics")
    stats = global_stats['switches_per_second']
    min_sw = min(stats) if stats else 0
    max_sw = max(stats) if stats else 0
    avg_sw = sum(stats) / len(stats) if stats else 0
    st.write(f"Min: `{min_sw:.2f}`/s, Max: `{max_sw:.2f}`/s, Avg: `{avg_sw:.2f}`/s")

    # Live Logs
    st.subheader("📋 Live BPF Logs")
    st.code("\n".join(log_lines[-15:]))

    # BPF Per-Process Stats
    st.subheader("⚙️ Process Stats (BPFTrace Tracked)")
    rows = []
    for pid, stats in process_stats.items():
        time_in = stats['total_time_in_cpu']
        switches = stats['context_switches']
        efficiency = time_in / switches if switches else 0
        rows.append({
            "PID": pid,
            "Switches": switches,
            "CPU Time (s)": round(time_in, 3),
            "Efficiency (s/switch)": round(efficiency, 4)
        })
    bpf_df = pd.DataFrame(rows).sort_values("CPU Time (s)", ascending=False)
    st.dataframe(bpf_df, use_container_width=True)

    # Live psutil Process Table
    st.subheader("📊 Live Process Table")
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_percent']):
        try:
            procs.append(p.info)
        except psutil.NoSuchProcess:
            pass
    proc_df = pd.DataFrame(procs).sort_values("cpu_percent", ascending=False)
    st.dataframe(proc_df.head(30), use_container_width=True)

    # /proc/schedstat Stats
    st.subheader("🧬 Kernel SchedStat (/proc/schedstat)")
    sched_df = get_schedstat()
    if not sched_df.empty:
        st.dataframe(sched_df, use_container_width=True)

    # Export Logs
    st.subheader("📥 Export BPF Stats")
    st.download_button("Download Process Stats CSV", bpf_df.to_csv(index=False), "bpf_stats.csv", "text/csv")

    st.stop()