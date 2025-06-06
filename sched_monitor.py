from bcc import BPF
from time import sleep, time
from collections import defaultdict
import math
import os

bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

BPF_HASH(ts_switch_in, u32, u64);
BPF_HASH(ts_wakeup, u32, u64);
BPF_HASH(ctx_switches, u32, u64);
BPF_HASH(latency_us, u32, u64);
BPF_HASH(latency_cnt, u32, u64);
BPF_HASH(run_time_ms, u32, u64);
BPF_HASH(runtime_cnt, u32, u64);
BPF_HASH(migrations, u32, u64);
BPF_HASH(rq_len, u32, u64);

// Context switch
TRACEPOINT_PROBE(sched, sched_switch) {
    u32 prev = args->prev_pid;
    u32 next = args->next_pid;
    u64 ts = bpf_ktime_get_ns();

    u64 *wts = ts_wakeup.lookup(&next);
    if (wts) {
        u64 delta = (ts - *wts) / 1000;
        u64 *lat = latency_us.lookup_or_init(&next, &delta);
        *lat += delta;

        u64 one = 1;
        u64 *cnt = latency_cnt.lookup_or_init(&next, &one);
        (*cnt)++;
        ts_wakeup.delete(&next);
    }

    ts_switch_in.update(&prev, &ts);
    u64 *c = ctx_switches.lookup_or_init(&prev, &ts);
    (*c)++;

    u64 *intime = ts_switch_in.lookup(&next);
    if (intime) {
        u64 dur = (ts - *intime) / 1000000;
        u64 *r = run_time_ms.lookup_or_init(&next, &dur);
        *r += dur;

        u64 one = 1;
        u64 *rc = runtime_cnt.lookup_or_init(&next, &one);
        (*rc)++;

        ts_switch_in.delete(&next);
    }

    return 0;
}

// Wakeup events
TRACEPOINT_PROBE(sched, sched_wakeup) {
    u32 pid = args->pid;
    u64 ts = bpf_ktime_get_ns();
    ts_wakeup.update(&pid, &ts);
    return 0;
}

TRACEPOINT_PROBE(sched, sched_wakeup_new) {
    u32 pid = args->pid;
    u64 ts = bpf_ktime_get_ns();
    ts_wakeup.update(&pid, &ts);
    return 0;
}

// Migrations
TRACEPOINT_PROBE(sched, sched_migrate_task) {
    u32 pid = args->pid;
    u64 one = 1;
    u64 *c = migrations.lookup_or_init(&pid, &one);
    (*c)++;
    return 0;
}

// Approx queue sample
int kprobe__run_rebalance_domains(struct pt_regs *ctx) {
    u32 cpu = bpf_get_smp_processor_id();
    u64 one = 1;
    u64 *c = rq_len.lookup_or_init(&cpu, &one);
    (*c)++;
    return 0;
}
"""

b = BPF(text=bpf_text)

def collect_data():
    ctx = b.get_table("ctx_switches")
    lat = b.get_table("latency_us")
    latcnt = b.get_table("latency_cnt")
    run = b.get_table("run_time_ms")
    runcnt = b.get_table("runtime_cnt")
    mig = b.get_table("migrations")
    rq = b.get_table("rq_len")

    # Derived
    ctx_total = sum(ctx.values())
    latency_sum = sum(lat.values())
    latency_cnt = sum(latcnt.values()) or 1
    runtime_sum = sum(run.values())
    runtime_sqsum = sum([v.value ** 2 for v in run.values()])
    runtime_cnt = sum(runcnt.values()) or 1
    rq_total = sum(rq.values())
    rq_sqsum = sum([v.value ** 2 for v in rq.values()])
    rq_cnt = len(rq.values()) or 1

    # Derived Metrics
    latency_avg = latency_sum / latency_cnt
    runtime_avg = runtime_sum / runtime_cnt
    runtime_var = (runtime_sqsum / runtime_cnt) - (runtime_avg ** 2)
    rq_sd = math.sqrt((rq_sqsum / rq_cnt) - ((rq_total / rq_cnt) ** 2)) if rq_cnt else 0

    fairness = (runtime_sum ** 2) / (len(run) * runtime_sqsum) if runtime_sqsum else 0

    print("\n================ Scheduler Metrics (60s) ================\n")
    print(f"🌀 Avg Context Switches/sec       : {ctx_total // 60}")
    print(f"⏱️  Avg Scheduling Latency (μs)   : {int(latency_avg)}")
    print(f"🕒 Avg Task Runtime (ms)           : {int(runtime_avg)}")
    print(f"⚖️  CPU Time Fairness (Jain Index): {fairness:.3f}")
    print(f"📊 CPU Load Imbalance (σ rq len)  : {rq_sd:.2f}")
    print("\n=========================================================\n")

    # Optional: Print per-PID breakdowns
    # for pid, val in ctx.items():
    #     print(f"PID {pid.value}: {val.value} context switches")

    # Clear maps
    for m in [ctx, lat, latcnt, run, runcnt, mig, rq]:
        m.clear()

print("✅ Scheduler monitor started. Gathering data every 60s...\nPress Ctrl+C to stop.\n")
try:
    while True:
        sleep(60)
        collect_data()
except KeyboardInterrupt:
    print("Exiting.")