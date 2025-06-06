import subprocess
import tempfile
import os

BPFTRACE_SCRIPT = """
tracepoint:sched:sched_switch
{
    @ctx_switches[args->prev_pid] += 1;
    @ts_switch_in[args->prev_pid] = nsecs;

    if (@ts_wakeup[args->next_pid]) {
        $lat = (nsecs - @ts_wakeup[args->next_pid]) / 1000;
        @latency_us[args->next_pid] += $lat;
        @latency_cnt[args->next_pid] += 1;
        delete(@ts_wakeup[args->next_pid]);
    }
}

tracepoint:sched:sched_switch
/ @ts_switch_in[args->next_pid] /
{
    $dur = (nsecs - @ts_switch_in[args->next_pid]) / 1000000;
    @run_time_ms[args->next_pid] += $dur;
    @runtime_cnt[args->next_pid] += 1;
    delete(@ts_switch_in[args->next_pid]);
}

tracepoint:sched:sched_wakeup,
tracepoint:sched:sched_wakeup_new
{
    @ts_wakeup[args->pid] = nsecs;
}

tracepoint:sched:sched_migrate_task
{
    @migrations[args->pid] += 1;
}

kprobe:run_rebalance_domains
{
    @rq_len[cpu] = hist(cpu);
}

interval:s:60 {
    printf("\\n================ Scheduler Stats (Last 60s) ================\\n");

    $ctx_total = 0;
    $lat_sum = 0; $lat_cnt = 0;
    $rt_sum = 0; $rt_cnt = 0;
    $fair_sum = 0; $fair_sq = 0; $n = 0;

    foreach(pid in @ctx_switches) {
        $ctx_total += @ctx_switches[pid];
    }

    foreach(pid in @latency_us) {
        $lat_sum += @latency_us[pid];
        $lat_cnt += @latency_cnt[pid];
    }

    foreach(pid in @run_time_ms) {
        $v = @run_time_ms[pid];
        $rt_sum += $v;
        $rt_cnt += @runtime_cnt[pid];
        $fair_sum += $v;
        $fair_sq += $v * $v;
        $n += 1;
    }

    $lat_avg = $lat_cnt > 0 ? $lat_sum / $lat_cnt : 0;
    $rt_avg = $rt_cnt > 0 ? $rt_sum / $rt_cnt : 0;
    $fairness = ($n > 0 && $fair_sq > 0) ? ($fair_sum * $fair_sum) / ($n * $fair_sq) : 0;

    printf("\\n📈 Derived Scheduler Metrics:\\n");
    printf("🌀 Avg Context Switches/sec       : %d\\n", $ctx_total / 60);
    printf("⏱️  Avg Scheduling Latency (μs)   : %d\\n", $lat_avg);
    printf("🕒 Avg Task Runtime (ms)           : %d\\n", $rt_avg);
    printf("⚖️  CPU Time Fairness (Jain Index): %.3f\\n", $fairness);

    printf("\\n🌀 Context Switches:\\n"); print(@ctx_switches);
    printf("\\n⏱️ Latency (μs):\\n"); print(@latency_us);
    printf("\\n🔁 Migrations:\\n"); print(@migrations);
    printf("\\n📊 Run Queue Histogram:\\n"); print(@rq_len);
    printf("\\n⏳ Runtime per PID (ms):\\n"); print(@run_time_ms);

    clear(@ctx_switches); clear(@latency_us); clear(@latency_cnt);
    clear(@run_time_ms); clear(@runtime_cnt);
    clear(@ts_switch_in); clear(@ts_wakeup);
    clear(@migrations); clear(@rq_len);
}
"""

def run_bpftrace():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".bt") as f:
        f.write(BPFTRACE_SCRIPT)
        script_path = f.name

    try:
        print(f"Running BPFTrace from: {script_path}")
        proc = subprocess.Popen(["sudo", "bpftrace", script_path],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True)

        while True:
            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break
            if line:
                print(line.strip())
    except KeyboardInterrupt:
        proc.terminate()
        print("BPFTrace monitoring stopped.")
    finally:
        os.remove(script_path)

if __name__ == "__main__":
    run_bpftrace()