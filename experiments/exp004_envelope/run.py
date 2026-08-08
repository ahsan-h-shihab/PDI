"""exp004: derive the admissibility envelope EMPIRICALLY from gen_trace.
No statistical multiplier is chosen; the envelope is the simulator's own
observed support. Separates ORDINARY drift steps from the SCRIPTED fault jump
at t=TF so the dynamical envelope is not inflated by scenario scripting."""
import json, subprocess, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
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

import sys; sys.path.insert(0, _PKG_ROOT)
from sim import gen_trace, TF, TR, T_END

EXP=_HERE
M=20000; SEED=20240601
rng=np.random.default_rng(SEED)

dT_ord, dS_ord = [], []      # ordinary per-step diffs (exclude scripted fault step t=TF)
dT_fault=[]                  # the scripted fault jump magnitudes at t=TF
Trng=[1,0]; Srng=[1,0]; Rrng=[1,0]
for _ in range(M):
    T,S,R=gen_trace(rng)
    dT=np.diff(T); dS=np.diff(S)
    for t in range(1,T_END):
        if t==TF: dT_fault.append(abs(dT[t-1]))          # scripted shock, recorded separately
        else:     dT_ord.append(abs(dT[t-1])); dS_ord.append(abs(dS[t-1]))
    Trng=[min(Trng[0],T.min()),max(Trng[1],T.max())]
    Srng=[min(Srng[0],S.min()),max(Srng[1],S.max())]
    Rrng=[min(Rrng[0],R.min()),max(Rrng[1],R.max())]

dT_ord=np.array(dT_ord); dS_ord=np.array(dS_ord); dT_fault=np.array(dT_fault)
def q(a,p): return float(np.quantile(a,p))

env=dict(
  experiment_id="exp004_envelope", code_commit=_git_commit(_PKG_ROOT),
  sample_episodes=M, sample_steps=int(dT_ord.size+dT_fault.size), seed=SEED,
  # ORDINARY-STEP dynamical envelope (this is what Controlled Mode uses):
  dT_max_ordinary_q9999=q(dT_ord,0.9999), dT_max_ordinary_max=float(dT_ord.max()),
  dS_max_ordinary_q9999=q(dS_ord,0.9999), dS_max_ordinary_max=float(dS_ord.max()),
  # chosen envelope = 99.99th pct of ordinary steps (simulator-derived, excludes scripted shock):
  dT_max=q(dT_ord,0.9999), dS_max=q(dS_ord,0.9999),
  # scripted fault jump, recorded for Natural Mode / audit (NOT folded into envelope):
  fault_step=TF, dT_fault_min=float(dT_fault.min()), dT_fault_max=float(dT_fault.max()),
  # value ranges (A3):
  T_range=[float(Trng[0]),float(Trng[1])], S_range=[float(Srng[0]),float(Srng[1])],
  R_range=[float(Rrng[0]),float(Rrng[1])],
  scenario=dict(fault_t=TF, recovery_t=TR, horizon=T_END),
  note="Controlled Mode uses dT_max/dS_max (ordinary-step 99.99pct). Natural Mode also "
       "obeys scenario schedule incl. fault jump at fault_step. R not autoregressive -> no dR bound.")
json.dump(env, _wopen(f"{EXP}/envelope.json","w"), indent=2)
json.dump(dict(M=M,seed=SEED,quantile=0.9999), _wopen(f"{EXP}/parameters.json","w"), indent=2)
_wopen(f"{EXP}/seed.txt","w").write(f"{SEED}\n")

fig,ax=plt.subplots(1,2,figsize=(10,4))
ax[0].hist(dT_ord,bins=100,color="steelblue"); ax[0].axvline(env["dT_max"],color="r",ls="--",label=f"envelope dT_max={env['dT_max']:.4f}")
ax[0].axvspan(dT_fault.min(),dT_fault.max(),color="orange",alpha=.3,label=f"scripted fault |dT|∈[{dT_fault.min():.2f},{dT_fault.max():.2f}]")
ax[0].set_title("ordinary |dT| per step (log y)"); ax[0].set_yscale("log"); ax[0].legend(fontsize=7)
ax[1].hist(dS_ord,bins=100,color="seagreen"); ax[1].axvline(env["dS_max"],color="r",ls="--",label=f"envelope dS_max={env['dS_max']:.4f}")
ax[1].set_title("ordinary |dS| per step (log y)"); ax[1].set_yscale("log"); ax[1].legend(fontsize=7)
plt.tight_layout(); plt.savefig(f"{EXP}/figures/step_support.png",dpi=130)

print(json.dumps({k:env[k] for k in ["dT_max","dS_max","dT_max_ordinary_max","dS_max_ordinary_max",
      "dT_fault_min","dT_fault_max","T_range","S_range","R_range","sample_steps"]}, indent=2))
