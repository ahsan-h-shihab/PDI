"""exp005 (re-run after bug fixes): verification of convergent-trace generator."""
import sys, json, csv, subprocess, time
import numpy as np
import os as _os
_HERE     = _os.path.dirname(_os.path.abspath(__file__))
_PKG_ROOT = _os.path.abspath(_os.path.join(_HERE, _os.pardir, _os.pardir))
def _git_commit(_root):
    """Return short git hash, or 'nogit' if unavailable (downloaded copy / no git)."""
    try:
        import subprocess as _sp
        return _sp.run(["git","-C",_root,"rev-parse","--short","HEAD"],
                       capture_output=True, text=True).stdout.strip() or "nogit"
    except Exception:
        return "nogit"

# --- frozen-artifact preservation guard (added for portable reproducibility package) ---
# Re-running a generator script must not clobber frozen artifacts shipped with the package.
# Set the environment variable PDI_REGEN=1 to force regeneration into a fresh directory.
_PRESERVE_FROZEN = _os.environ.get("PDI_REGEN", "") != "1"
class _NullSink:
    def write(self, *a, **k): return 0
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def close(self): pass
def _wopen(_path, _mode="w", *a, **k):
    if _PRESERVE_FROZEN and "w" in _mode and _os.path.exists(_path):
        print(f"[preserve] keeping existing frozen artifact: {_os.path.relpath(_path, _PKG_ROOT)}")
        return _NullSink()
    return open(_path, _mode, *a, **k)

sys.path.insert(0, _PKG_ROOT)
from generator import (load_envelope, gen_convergent, FAMILIES,
                       assert_terminates_at, assert_admissible,
                       assert_reproducible, assert_families_distinct)
from policies import TRAPPolicy, BANDS
from pdi import emit_terminal_level

EXP      = _HERE
ENV_PATH = _os.path.join(_PKG_ROOT, 'experiments/exp004_envelope/envelope.json')
COMMIT   = _git_commit(_PKG_ROOT)
envelope = load_envelope(ENV_PATH)
pol      = TRAPPolicy()
T_lo,T_hi = envelope["T_range"]; S_lo,S_hi = envelope["S_range"]
R_lo,R_hi = envelope["R_range"]

# Target grid: band mid-points 1-4, R in {0.20,0.40,0.65,0.80}
# Higher R values ensure F4 is physically feasible on some targets
targets = []
band_mids = [(BANDS[i]+BANDS[i+1])/2 for i in range(4)]
for g_mid in band_mids:
    for R_star in [0.20, 0.40, 0.65, 0.80]:
        S_star = 0.70
        T_star = (g_mid + 0.2*R_star - 0.3*S_star) / 0.5
        if not (T_lo<=T_star<=T_hi): continue
        if not (S_lo<=S_star<=S_hi): continue
        if not (R_lo<=R_star<=R_hi): continue
        targets.append((round(T_star,6), round(S_star,6), round(R_star,6)))

SEEDS=[42,137,2024]; MODES=["controlled","natural"]; H=100
params=dict(targets=targets,seeds=SEEDS,modes=MODES,H=H,
            families=list(FAMILIES),envelope_path=ENV_PATH)
json.dump(params,_wopen(f"{EXP}/parameters.json","w"),indent=2)
_wopen(f"{EXP}/seed.txt","w").write("seeds: "+", ".join(map(str,SEEDS))+"\n")
json.dump(dict(experiment_id="exp005_convergent_generator",code_commit=COMMIT,
               n_targets=len(targets),seeds=SEEDS,modes=MODES,H=H),
          _wopen(f"{EXP}/config.json","w"),indent=2)

raw_rows=[]; n_s1=n_adm=n_s4=n_s3ok=n_s3ins=n_oos=0
t0=time.time()
for mode in MODES:
    for x_star in targets:
        for seed in SEEDS:
            level_map={}
            for family in FAMILIES:
                row=dict(mode=mode,T_star=x_star[0],S_star=x_star[1],
                         R_star=x_star[2],family=family,seed=seed,
                         s1_pass=None,adm_pass=None,s4_pass=None,
                         terminal_level=None,error="")
                try:
                    h=gen_convergent(x_star,family,seed,H,mode,envelope)
                    try: assert_terminates_at(h,x_star); row["s1_pass"]=True
                    except AssertionError as e: row["s1_pass"]=False; row["error"]+=f"S1:{e} "; n_s1+=1
                    try: assert_admissible(h,envelope,mode); row["adm_pass"]=True
                    except AssertionError as e: row["adm_pass"]=False; row["error"]+=f"ADM:{e} "; n_adm+=1
                    try: assert_reproducible(x_star,family,seed,H,mode,envelope); row["s4_pass"]=True
                    except AssertionError as e: row["s4_pass"]=False; row["error"]+=f"S4:{e} "; n_s4+=1
                    lvl=emit_terminal_level(pol,h); row["terminal_level"]=lvl; level_map[family]=lvl
                except ValueError as e:
                    row["error"]+=f"OOS:{e}"; n_oos+=1
                raw_rows.append(row)
            if len(level_map)>=2:
                try: assert_families_distinct(level_map); n_s3ok+=1
                except AssertionError: n_s3ins+=1
elapsed=time.time()-t0

fields=["mode","T_star","S_star","R_star","family","seed",
        "s1_pass","adm_pass","s4_pass","terminal_level","error"]
with _wopen(f"{EXP}/raw_results.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); [w.writerow(r) for r in raw_rows]
proc=dict(n_histories=len(raw_rows),n_s1_fail=n_s1,n_adm_fail=n_adm,
          n_s4_fail=n_s4,n_s3_distinct=n_s3ok,n_s3_insensitive=n_s3ins,
          n_oos=n_oos,elapsed_s=round(elapsed,2))
json.dump(proc,_wopen(f"{EXP}/processed_results.json","w"),indent=2)

print(f"\n{'='*60}")
print(f"exp005 (fixed)  commit={COMMIT}  {elapsed:.1f}s")
print(f"{'='*60}")
print(f"targets          : {len(targets)}")
print(f"histories tried  : {len(raw_rows)}")
print(f"S1  failures     : {n_s1}  (HARD)")
print(f"ADM failures     : {n_adm}  (HARD)")
print(f"S4  failures     : {n_s4}  (HARD)")
print(f"out-of-support   : {n_oos}  (logged, expected for F4/low-R)")
print(f"S3-distinct (ok) : {n_s3ok}")
print(f"S3-insensitive   : {n_s3ins}  (logged, not hard fail)")
print(f"{'='*60}")
hard=n_s1+n_adm+n_s4
print("HARD GATE: " + ("PASSED — zero S1/ADM/S4 failures" if hard==0
                       else f"FAILED ({hard} failures) — see raw_results.csv"))

# Show a sample of successful distinct cases
distinct_rows=[r for r in raw_rows if r.get("s1_pass") and r.get("adm_pass")]
if distinct_rows:
    print("\nSample verified histories (first 5 unique x*):")
    seen=set()
    for r in distinct_rows:
        key=(r["mode"],r["T_star"],r["S_star"],r["R_star"],r["seed"])
        if key not in seen:
            seen.add(key); lvl=r["terminal_level"]
            print(f"  {r['mode']:10} T={r['T_star']:.3f} S={r['S_star']:.3f} "
                  f"R={r['R_star']:.3f} seed={r['seed']} family={r['family']:20} lvl={lvl}")
        if len(seen)>=5: break
