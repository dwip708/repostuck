import subprocess
import time
import csv
import os
from threading import Thread
from datetime import datetime

RESULT_CSV = "task_monitor_results.csv"
TASK_BINARY = "./task"
NUM_TASKS = 4
DURATION = 10  # Maximum expected task duration (for pidstat)

# Schedulers
SCHEDULERS = {
    "CFS": lambda: [TASK_BINARY],
    "RR": lambda: ["sudo", "chrt", "-r", "10", TASK_BINARY],
    "FIFO": lambda: ["sudo", "chrt", "-f", "10", TASK_BINARY],
}

def monitor_pid(pid, interval=1):
    """Monitor CPU usage of a PID using pidstat"""
    try:
        cmd = f"pidstat -h -u -r -p {pid} {interval} {DURATION}"
        out = subprocess.check_output(cmd, shell=True, text=True)
        return out
    except Exception as e:
        return f"Monitoring failed: {e}"

def run_task_and_monitor(cmd, label, task_id, output_list):
    start = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pid = proc.pid

    # Start monitor in parallel
    monitor_thread = Thread(target=lambda: output_list.append({
        "Scheduler": label,
        "Task_ID": task_id,
        "Start_Time": datetime.now().isoformat(),
        "PID": pid,
        "Monitor": monitor_pid(pid)
    }))
    monitor_thread.start()

    stdout, stderr = proc.communicate()
    end = time.time()

    task_time = None
    try:
        task_time = float(stdout.strip().split()[-1])
    except:
        task_time = end - start

    for entry in output_list:
        if entry["Task_ID"] == task_id and entry["Scheduler"] == label:
            entry["End_Time"] = datetime.now().isoformat()
            entry["Wall_Clock"] = end - start
            entry["Task_Output_Time"] = task_time
            break

    monitor_thread.join()

def run_scheduler(label):
    print(f"\n== Running {label} ==")
    results = []
    threads = []

    for i in range(NUM_TASKS):
        cmd = SCHEDULERS[label]()
        t = Thread(target=run_task_and_monitor, args=(cmd, label, i+1, results))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    
    return results

def write_csv(results):
    with open(RESULT_CSV, "w", newline="") as f:
        fieldnames = ["Scheduler", "Task_ID", "PID", "Start_Time", "End_Time", "Wall_Clock", "Task_Output_Time", "Monitor"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"\n✅ Results saved to {RESULT_CSV}")

def main():
    all_results = []
    for scheduler in SCHEDULERS.keys():
        results = run_scheduler(scheduler)
        all_results.extend(results)
    write_csv(all_results)

if __name__ == "__main__":
    main()