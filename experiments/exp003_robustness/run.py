"""exp003: robustness of the multi-level (path-dependence existence) result
to discretization granularity and random seed. Mines only real gen_trace
trajectories; no hand-crafted histories."""
import os, json, csv, sys, subprocess, numpy as np
from collections import defaultdict
# Portable roots: this file lives at <PKG_ROOT>/experiments/exp003_robustness/run.py
_HERE     = os.path.dirname(os.path.abspath(__file__))
_PKG_ROOT = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir))
sys.path.insert(0, _PKG_ROOT)
from sim import gen_trace, T_END
from policies import TRAPPolicy
from pdi import emit_level_series

EXP_DIR = _HERE
BIN_WIDTHS = [0.01, 0.02, 0.03, 0.05, 0.08]      # discretization granularity sweep
SEEDS      = [1, 7, 12345, 2024, 99999]           # independent mining seeds
N_EPISODES = 4000
MIN_OCC    = 5                                     # recurrence threshold
pol = TRAPPolicy()

def mine(seed, binw):
    cond_levels, cond_count = defaultdict(set), defaultdict(int)
    rng = np.random.default_rng(seed)
    for _ in range(N_EPISODES):
        T, S, R = gen_trace(rng)
        a = emit_level_series(pol, np.column_stack([T, S, R]))
        for t in range(T_END):
            key = (round(T[t]/binw), round(S[t]/binw), round(R[t]/binw))
            cond_levels[key].add(int(a[t])); cond_count[key] += 1
    recurring = [k for k in cond_levels if cond_count[k] >= MIN_OCC]
    multi = [k for k in recurring if len(cond_levels[k]) >= 2]
    spreads = [max(cond_levels[k]) - min(cond_levels[k]) for k in multi]
    return dict(distinct=len(cond_levels), recurring=len(recurring),
                multi=len(multi),
                pct_multi=100*len(multi)/max(1, len(recurring)),
                mean_spread=float(np.mean(spreads)) if spreads else 0.0,
                max_spread=int(max(spreads)) if spreads else 0)

rows = []
for binw in BIN_WIDTHS:
    for seed in SEEDS:
        r = mine(seed, binw); r.update(bin_width=binw, seed=seed); rows.append(r)
        print(f"binw={binw:<4} seed={seed:<6} recurring={r['recurring']:<6} "
              f"multi%={r['pct_multi']:5.1f} mean_spread={r['mean_spread']:.2f}")

# --- persist artifacts (never overwrite; this dir is unique to exp003) ---
try:
    commit = subprocess.run(["git","-C",_PKG_ROOT,"rev-parse","--short","HEAD"],
                            capture_output=True, text=True).stdout.strip() or "nogit"
except Exception:
    commit = "nogit"
with open(f"{EXP_DIR}/raw_results.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=["bin_width","seed","distinct","recurring",
                                      "multi","pct_multi","mean_spread","max_spread"])
    w.writeheader(); [w.writerow(r) for r in rows]

# processed: aggregate over seeds per bin width
proc = []
for binw in BIN_WIDTHS:
    sub = [r for r in rows if r["bin_width"]==binw]
    pm = [r["pct_multi"] for r in sub]
    proc.append(dict(bin_width=binw, pct_multi_mean=float(np.mean(pm)),
                     pct_multi_std=float(np.std(pm)),
                     pct_multi_min=float(np.min(pm)), pct_multi_max=float(np.max(pm)),
                     mean_spread_mean=float(np.mean([r["mean_spread"] for r in sub]))))
with open(f"{EXP_DIR}/processed_results.csv","w",newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(proc[0])); w.writeheader(); [w.writerow(r) for r in proc]

json.dump(dict(experiment_id="exp003_robustness", code_commit=commit,
               n_episodes=N_EPISODES, min_occurrences=MIN_OCC,
               bin_widths=BIN_WIDTHS, seeds=SEEDS, policy="TRAPPolicy(default)",
               signal="0.5T+0.3S-0.2R", bands=[0.20,0.35,0.50,0.65,0.80]),
          open(f"{EXP_DIR}/config.json","w"), indent=2)
json.dump(dict(bin_widths=BIN_WIDTHS, seeds=SEEDS, n_episodes=N_EPISODES,
               min_occurrences=MIN_OCC), open(f"{EXP_DIR}/parameters.json","w"), indent=2)
open(f"{EXP_DIR}/seed.txt","w").write("mining seeds: "+", ".join(map(str,SEEDS))+"\n")

# figure: pct_multi vs bin width, one line per seed + mean
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.figure(figsize=(6,4))
for seed in SEEDS:
    ys = [next(r["pct_multi"] for r in rows if r["bin_width"]==bw and r["seed"]==seed) for bw in BIN_WIDTHS]
    plt.plot(BIN_WIDTHS, ys, "o-", alpha=.5, label=f"seed {seed}")
plt.plot(BIN_WIDTHS, [p["pct_multi_mean"] for p in proc], "ks-", lw=2.5, label="mean")
plt.xlabel("bin width"); plt.ylabel("% recurring conditions that are multi-level")
plt.title("exp003: path-dependence prevalence vs discretization & seed")
plt.ylim(0,100); plt.grid(alpha=.3); plt.legend(fontsize=8)
plt.tight_layout(); plt.savefig(f"{EXP_DIR}/figures/pct_multi_vs_binwidth.png", dpi=130)
print("\nartifacts written to", EXP_DIR)
