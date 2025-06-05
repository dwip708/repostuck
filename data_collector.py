# data_collector.py

import sqlite3
import psutil
import time
from datetime import datetime

DB_FILE = "monitoring.db"
MAX_ROWS = 500
MAX_PROC_ROWS = 1000  # limit per-process stats rows

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # system metrics table (overall system info)
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_metrics (
            timestamp TEXT PRIMARY KEY,
            cpu_percent REAL,
            memory_percent REAL,
            context_switches INTEGER,
            processes_running INTEGER,
            processes_sleeping INTEGER,
            load_avg_1 REAL,
            load_avg_5 REAL,
            load_avg_15 REAL
        )
    ''')

    # per process stats
    c.execute('''
        CREATE TABLE IF NOT EXISTS process_metrics (
            timestamp TEXT,
            pid INTEGER,
            name TEXT,
            user TEXT,
            cpu_time REAL,
            create_time REAL,
            ctx_switches INTEGER,
            status TEXT,
            PRIMARY KEY(timestamp, pid)
        )
    ''')

    # per-core cpu usage
    c.execute('''
        CREATE TABLE IF NOT EXISTS cpu_core_stats (
            timestamp TEXT,
            core INTEGER,
            cpu_percent REAL,
            PRIMARY KEY(timestamp, core)
        )
    ''')

    conn.commit()
    conn.close()

def collect_system_metrics():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory_percent = psutil.virtual_memory().percent
    ctx_switches = sum(p.num_ctx_switches().voluntary + p.num_ctx_switches().involuntary for p in psutil.process_iter())
    procs = [p.info for p in psutil.process_iter(['status'])]
    running = sum(1 for p in procs if p['status'] == psutil.STATUS_RUNNING)
    sleeping = sum(1 for p in procs if p['status'] == psutil.STATUS_SLEEPING)
    load1, load5, load15 = psutil.getloadavg()

    return {
        'timestamp': datetime.now().isoformat(),
        'cpu_percent': cpu_percent,
        'memory_percent': memory_percent,
        'context_switches': ctx_switches,
        'processes_running': running,
        'processes_sleeping': sleeping,
        'load_avg_1': load1,
        'load_avg_5': load5,
        'load_avg_15': load15,
    }

def collect_process_metrics():
    procs = []
    now_ts = datetime.now().isoformat()
    for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_times', 'create_time', 'num_ctx_switches', 'status']):
        try:
            cpu_time = sum(p.info['cpu_times'][:2])  # user + system time
            ctx_switches = p.info['num_ctx_switches'].voluntary + p.info['num_ctx_switches'].involuntary
            procs.append((
                now_ts,
                p.info['pid'],
                p.info['name'],
                p.info['username'],
                cpu_time,
                p.info['create_time'],
                ctx_switches,
                p.info['status']
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs

def collect_cpu_core_stats():
    now_ts = datetime.now().isoformat()
    per_core = psutil.cpu_percent(interval=0, percpu=True)
    return [(now_ts, idx, val) for idx, val in enumerate(per_core)]

def insert_system_metrics(metrics):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO system_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', tuple(metrics.values()))

    # Keep last MAX_ROWS entries
    c.execute(f'''
        DELETE FROM system_metrics
        WHERE timestamp NOT IN (
            SELECT timestamp FROM system_metrics ORDER BY timestamp DESC LIMIT {MAX_ROWS}
        )
    ''')
    conn.commit()
    conn.close()

def insert_process_metrics(procs):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.executemany('''
        INSERT OR REPLACE INTO process_metrics VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', procs)

    # Keep last MAX_PROC_ROWS timestamps * pids approximately (may not be perfect)
    c.execute(f'''
        DELETE FROM process_metrics
        WHERE timestamp NOT IN (
            SELECT timestamp FROM process_metrics ORDER BY timestamp DESC LIMIT {MAX_ROWS}
        )
    ''')
    conn.commit()
    conn.close()

def insert_cpu_core_stats(core_stats):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.executemany('''
        INSERT OR REPLACE INTO cpu_core_stats VALUES (?, ?, ?)
    ''', core_stats)

    # Keep last MAX_ROWS timestamps * cores approx
    c.execute(f'''
        DELETE FROM cpu_core_stats
        WHERE timestamp NOT IN (
            SELECT timestamp FROM cpu_core_stats ORDER BY timestamp DESC LIMIT {MAX_ROWS}
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    while True:
        try:
            system_metrics = collect_system_metrics()
            insert_system_metrics(system_metrics)

            process_metrics = collect_process_metrics()
            insert_process_metrics(process_metrics)

            core_stats = collect_cpu_core_stats()
            insert_cpu_core_stats(core_stats)

            print(f"Inserted metrics at {system_metrics['timestamp']}")

        except Exception as e:
            print(f"[ERROR] {e}")

        time.sleep(10)