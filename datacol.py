import sqlite3
import time
import psutil
from datetime import datetime
import os
import traceback

DB_FILE = "system_monitor.db"
MAX_RECORDS = 500
SLEEP_INTERVAL = 10  # seconds

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        # Create system metrics table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_metrics (
            timestamp TEXT, cpu_percent REAL, memory_percent REAL,
            context_switches INTEGER, processes_running INTEGER,
            processes_sleeping INTEGER, load_avg_1 REAL,
            load_avg_5 REAL, load_avg_15 REAL
        )
        """)

        # Create per-process stats table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS process_metrics (
            timestamp TEXT, pid INTEGER, name TEXT, user TEXT,
            cpu_time REAL, create_time REAL, ctx_switches INTEGER,
            status TEXT
        )
        """)

        # Create per-core stats table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cpu_core_stats (
            timestamp TEXT, core INTEGER, cpu_percent REAL
        )
        """)

        conn.commit()

def limit_table_rows(conn, table_name, max_rows=MAX_RECORDS):
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    if count > max_rows:
        to_delete = count - max_rows
        cursor.execute(f"""
            DELETE FROM {table_name}
            WHERE rowid IN (
                SELECT rowid FROM {table_name}
                ORDER BY timestamp ASC LIMIT ?
            )
        """, (to_delete,))
        conn.commit()

def collect_metrics():
    init_db()

    while True:
        timestamp = datetime.utcnow().isoformat()
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            ctx_switches = psutil.cpu_stats().ctx_switches

            load_avg = os.getloadavg()
            processes = list(psutil.process_iter(['pid', 'name', 'username', 'cpu_times', 'create_time', 'status', 'num_ctx_switches']))
            processes_running = sum(1 for p in processes if p.info['status'] == psutil.STATUS_RUNNING)
            processes_sleeping = sum(1 for p in processes if p.info['status'] == psutil.STATUS_SLEEPING)

            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()

                # Insert system metrics
                cursor.execute("""
                INSERT INTO system_metrics
                (timestamp, cpu_percent, memory_percent, context_switches,
                processes_running, processes_sleeping,
                load_avg_1, load_avg_5, load_avg_15)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, cpu_percent, memory_percent, ctx_switches,
                    processes_running, processes_sleeping,
                    load_avg[0], load_avg[1], load_avg[2]
                ))

                # Insert process metrics
                for proc in processes:
                    try:
                        cpu_time = sum(proc.info['cpu_times']) if proc.info['cpu_times'] else 0.0
                        cursor.execute("""
                        INSERT INTO process_metrics
                        (timestamp, pid, name, user, cpu_time,
                        create_time, ctx_switches, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            timestamp,
                            proc.info['pid'],
                            proc.info['name'],
                            proc.info['username'],
                            cpu_time,
                            proc.info['create_time'],
                            proc.info['num_ctx_switches'].voluntary + proc.info['num_ctx_switches'].involuntary if proc.info['num_ctx_switches'] else 0,
                            proc.info['status']
                        ))
                    except Exception:
                        # Skip any process we can't access
                        continue

                # Insert CPU core stats
                per_core_usage = psutil.cpu_percent(interval=None, percpu=True)
                for core, usage in enumerate(per_core_usage):
                    cursor.execute("""
                    INSERT INTO cpu_core_stats (timestamp, core, cpu_percent)
                    VALUES (?, ?, ?)
                    """, (timestamp, core, usage))

                conn.commit()

                # Trim tables
                limit_table_rows(conn, "system_metrics")
                limit_table_rows(conn, "process_metrics")
                limit_table_rows(conn, "cpu_core_stats")

        except Exception as e:
            print(f"[{timestamp}] Error occurred: {e}")
            traceback.print_exc()

        time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    collect_metrics()