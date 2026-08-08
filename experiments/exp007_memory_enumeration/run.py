"""
exp007: Enumerate reachable (a, cu) states at step H-2 for representative
targets, under the empirical admissibility envelope (Controlled Mode).

Method: exhaustive forward reachability via BFS/dynamic-programming on the
discrete (a, cu) space, driven by the admissible signal moves derived from
the envelope. No hand-crafted histories; only moves the envelope permits.

For each target x* and each reachable (a[H-2], cu[H-2]) pair, compute the
terminal output a[H-1] = delta(a[H-2], cu[H-2], g*, sc[H-2]) and record
whether it differs from any other reachable pair => PDI potential.
"""
import sys, json, csv, subprocess, hashlib
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
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

sys.path.insert(0, _PKG_ROOT)

from policies import to_state, up_edge, low_edge, BANDS
from generator import load_envelope

EXP      = _HERE
ENV_PATH = _os.path.join(_PKG_ROOT, 'experiments/exp004_envelope/envelope.json')
COMMIT   = _git_commit(_PKG_ROOT)

# ── exp005/exp006 integrity check ────────────────────────────────────────────
for freeze_file in [
    _os.path.join(_PKG_ROOT, 'experiments/exp005_convergent_generator/freeze_hashes.json'),
]:
    hashes = json.load(open(freeze_file))
    for path, expected in hashes.items():
        actual = hashlib.sha256(open(path,'rb').read()).hexdigest()
        assert actual == expected, f"TAMPERED: {path}"
print("Frozen artifact integrity: PASS")

envelope = load_envelope(ENV_PATH)
dT_max   = envelope['dT_max']    # 0.0632
dS_max   = envelope['dS_max']    # 0.0421
T_lo,T_hi = envelope['T_range']
S_lo,S_hi = envelope['S_range']
R_lo,R_hi = envelope['R_range']

te = 0.05; tr_thresh = 0.10; k = 3   # default TRAP parameters
L  = 5                                 # max level

# ── ARS signal bounds ─────────────────────────────────────────────────────────
# g = 0.5T + 0.3S - 0.2R
# max single-step |dg| from T and S moves alone (R has no step bound):
#   |dg| <= 0.5*dT_max + 0.3*dS_max (T,S contribution)
# R can change arbitrarily each step, adding up to 0.2*(R_hi-R_lo)=0.2*0.7=0.14
# So max |dg| per step <= 0.5*dT_max + 0.3*dS_max + 0.2*(R_hi-R_lo)
dg_TS    = 0.5*dT_max + 0.3*dS_max    # T,S contribution to dg
dR_range = R_hi - R_lo
dg_max   = dg_TS + 0.2*dR_range       # absolute max |dg| per step

g_min = 0.5*T_lo + 0.3*S_lo - 0.2*R_hi   # min reachable ARS
g_max = 0.5*T_hi + 0.3*S_hi - 0.2*R_lo   # max reachable ARS

print(f"Envelope: dT_max={dT_max:.4f} dS_max={dS_max:.4f}")
print(f"dg_max per step: {dg_max:.4f}  (TS: {dg_TS:.4f} + R: {0.2*dR_range:.4f})")
print(f"g range: [{g_min:.3f}, {g_max:.3f}]")
print()

# ── Delta function (terminal decision) ───────────────────────────────────────
def delta(a_prev, cu_prev, g_star, g_prev):
    """Compute terminal level given policy memory (a_prev,cu_prev) and signals."""
    d = g_star - g_prev
    if d < -tr_thresh:
        return min(a_prev, to_state(g_star)), 'R'
    elif g_star >= up_edge(a_prev) + te:
        cu_new = cu_prev + 1
        if cu_new >= k:
            return min(a_prev + 1, L), 'E'
        else:
            return a_prev, 'H'
    else:
        return a_prev, 'H'

# ── Forward reachability: which (a,cu) are reachable at step H-2? ──────────
# State: (a, cu) — 6*3=18 pairs.
# Transition: given current state (a,cu) and signal sc[t], at t+1:
#   compute sc[t+1] in [sc[t]-dg_max, sc[t]+dg_max] ∩ [g_min,g_max]
#   apply tr_tdaa logic to determine (a',cu').
#
# We do reachability over SIGNAL VALUES, not full histories, to keep it
# tractable. We discretize g into fine bins and propagate.
#
# For each (a,cu,g_bin) triple, we track: reachable? yes/no.
# This is a standard BFS on (a, cu, g_bin).

N_GBINS = 500   # 500 bins over [g_min,g_max]
g_bins  = np.linspace(g_min, g_max, N_GBINS)
dg_bin  = (g_max - g_min) / (N_GBINS - 1)

def g_to_bin(g):
    return int(round((g - g_min) / (g_max - g_min) * (N_GBINS - 1)))

def bin_to_g(b):
    return g_min + b * (g_max - g_min) / (N_GBINS - 1)

def reachable_next_bins(g_bin):
    """Bins reachable from g_bin in one admissible step."""
    g_cur = bin_to_g(g_bin)
    g_lo  = max(g_min, g_cur - dg_max)
    g_hi  = min(g_max, g_cur + dg_max)
    b_lo  = max(0, int(np.floor((g_lo - g_min) / (g_max - g_min) * (N_GBINS-1))))
    b_hi  = min(N_GBINS-1, int(np.ceil((g_hi - g_min) / (g_max - g_min) * (N_GBINS-1))))
    return range(b_lo, b_hi+1)

def tr_step(a, cu, g_prev_bin, g_next_bin):
    """Apply one tr_tdaa step: given (a,cu) at step t, return (a',cu') at t+1."""
    g_prev = bin_to_g(g_prev_bin)
    g_next = bin_to_g(g_next_bin)
    d = g_next - g_prev
    a_new = a; cu_new = 0
    if d < -tr_thresh:
        a_new = min(a, to_state(g_next))
        cu_new = 0
    elif g_next >= up_edge(a) + te:
        cu_new = cu + 1
        if cu_new >= k:
            a_new = min(a + 1, L)
            cu_new = 0
        else:
            a_new = a
    else:
        a_new = a; cu_new = 0
    return a_new, cu_new

def enumerate_reachable(H=100):
    """
    BFS forward reachability over (a, cu, g_bin) for H-1 steps.
    Returns set of (a,cu,g_bin) triples reachable at step H-2
    (i.e., after H-2 transitions from step 0).
    """
    # Initial states: at step 0, a=to_state(g[0]), cu=0
    # g[0] can be anything in [g_min, g_max]
    current = set()
    for b in range(N_GBINS):
        g0 = bin_to_g(b)
        a0 = to_state(g0)
        current.add((a0, 0, b))   # (a, cu, g_bin) at step 0

    # Propagate H-2 steps (to reach step H-2)
    for step in range(H-2):
        next_states = set()
        for (a, cu, g_bin) in current:
            for g_next_bin in reachable_next_bins(g_bin):
                a_new, cu_new = tr_step(a, cu, g_bin, g_next_bin)
                next_states.add((a_new, cu_new, g_next_bin))
        current = next_states
        if step % 20 == 0:
            print(f"  step {step+1}/{H-2}: {len(current)} reachable (a,cu,g) states")

    return current

print("=== Enumerating reachable (a,cu,g) states at step H-2 ===")
reachable_H2 = enumerate_reachable(H=100)
print(f"Total reachable (a,cu,g_bin) triples at H-2: {len(reachable_H2)}")

# Collapse to (a,cu) pairs regardless of g_bin
reachable_acu = set((a,cu) for (a,cu,g) in reachable_H2)
print(f"Reachable (a,cu) pairs at H-2: {sorted(reachable_acu)}")
print(f"Total: {len(reachable_acu)} of 18 theoretical maximum")

# ── For representative targets: which (a,cu) are reachable AT that target? ──
# "At target x*" means: g_bin at H-2 must be consistent with approaching x*
# in one admissible step, i.e. g_prev in [g*-dg_max, g*+dg_max].

targets_json = json.load(open(
    _os.path.join(_PKG_ROOT, 'experiments/exp006_pdi_measurement/selected_targets.json')))
# Use first 8 targets + 2 from a wider range for coverage
targets = [(t['T_star'],t['S_star'],t['R_star']) for t in targets_json[:8]]

raw_rows = []
print(f"\n=== Per-target reachable memory and PDI potential ===")
for x_star in targets:
    g_star  = 0.5*x_star[0] + 0.3*x_star[1] - 0.2*x_star[2]
    g_star_bin = g_to_bin(np.clip(g_star, g_min, g_max))

    # Which (a,cu,g_prev_bin) at H-2 can transition to g_star in one step?
    reachable_at_target = {}   # (a,cu) -> set of achievable terminal levels
    for (a, cu, g_prev_bin) in reachable_H2:
        g_prev = bin_to_g(g_prev_bin)
        # Check admissibility: |g_star - g_prev| <= dg_max
        # (necessary but not sufficient; sufficient requires T,S,R split)
        if abs(g_star - g_prev) > dg_max + 1e-9:
            continue
        # Also: g_star itself must be reachable from g_prev in one step
        # (already guaranteed by the dg_max check for the signal aggregate)
        term_level, branch = delta(a, cu, g_star, g_prev)
        key = (a, cu)
        if key not in reachable_at_target:
            reachable_at_target[key] = set()
        reachable_at_target[key].add(term_level)

    # Aggregate terminal levels across all reachable (a,cu,g_prev) combinations
    acu_terminal = {}   # (a,cu) -> set of terminal levels
    for (a,cu), term_set in reachable_at_target.items():
        acu_terminal[(a,cu)] = term_set

    all_terminal_levels = set()
    for s in acu_terminal.values():
        all_terminal_levels |= s
    pdi_potential = max(all_terminal_levels) - min(all_terminal_levels) if all_terminal_levels else 0

    print(f"\nx*={x_star}  g*={g_star:.4f}  direct_band={to_state(g_star)}")
    print(f"  Reachable (a,cu) states at this target: {len(acu_terminal)}")
    print(f"  (a,cu) -> terminal level(s):")
    for (a,cu) in sorted(acu_terminal):
        lvls = sorted(acu_terminal[(a,cu)])
        marker = " <-- PDI" if len(lvls)>1 or (max(acu_terminal.values(),default={0})-{min(all_terminal_levels)}) else ""
        print(f"    a={a} cu={cu}: terminal={lvls}{marker}")
    print(f"  All reachable terminal levels: {sorted(all_terminal_levels)}")
    print(f"  PDI potential (max-min terminal): {pdi_potential}")

    for (a,cu),lvls in acu_terminal.items():
        raw_rows.append(dict(
            T_star=x_star[0], S_star=x_star[1], R_star=x_star[2],
            g_star=round(g_star,4), direct_band=to_state(g_star),
            a_prev=a, cu_prev=cu,
            terminal_levels=str(sorted(lvls)),
            pdi_potential=pdi_potential))

# ── Save ──────────────────────────────────────────────────────────────────────
json.dump(dict(experiment_id='exp007_memory_enumeration',
               code_commit=COMMIT, envelope_path=ENV_PATH,
               N_GBINS=N_GBINS, dg_max=dg_max,
               te=te, tr=tr_thresh, k=k, H=100,
               reachable_acu_pairs=sorted(str(x) for x in reachable_acu),
               n_reachable_acu=len(reachable_acu)),
          open(f'{EXP}/config.json','w'), indent=2)
json.dump(dict(N_GBINS=N_GBINS,te=te,tr=tr_thresh,k=k,H=100),
          open(f'{EXP}/parameters.json','w'), indent=2)
open(f'{EXP}/seed.txt','w').write('deterministic BFS; no random seed\n')

fields = ['T_star','S_star','R_star','g_star','direct_band',
          'a_prev','cu_prev','terminal_levels','pdi_potential']
with open(f'{EXP}/raw_results.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
    [w.writerow(r) for r in raw_rows]

# Processed: one row per target
seen = {}
for r in raw_rows:
    key = (r['T_star'],r['S_star'],r['R_star'])
    if key not in seen:
        seen[key] = dict(T_star=r['T_star'],S_star=r['S_star'],R_star=r['R_star'],
                         g_star=r['g_star'],direct_band=r['direct_band'],
                         n_acu_states=0, pdi_potential=r['pdi_potential'],
                         all_terminal_levels=set())
    seen[key]['n_acu_states'] += 1
    seen[key]['all_terminal_levels'] |= set(
        eval(r['terminal_levels']))
proc = []
for key,v in seen.items():
    v2 = dict(v); v2['all_terminal_levels']=str(sorted(v['all_terminal_levels']))
    proc.append(v2)
with open(f'{EXP}/processed_results.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(proc[0])); w.writeheader()
    [w.writerow(r) for r in proc]

# ── Figure: reachable (a,cu) pairs as a grid ─────────────────────────────────
fig,ax = plt.subplots(figsize=(6,4))
acu_list = sorted(reachable_acu)
a_vals = [x[0] for x in acu_list]; cu_vals = [x[1] for x in acu_list]
ax.scatter(a_vals, cu_vals, s=120, c='steelblue', zorder=3)
# mark unreachable
all_theory = [(a,cu) for a in range(L+1) for cu in range(k)]
unreach = [x for x in all_theory if x not in reachable_acu]
if unreach:
    ax.scatter([x[0] for x in unreach],[x[1] for x in unreach],
               s=120, c='lightgrey', marker='x', zorder=2)
ax.set_xlabel('a (authorization level)'); ax.set_ylabel('cu (escalation counter)')
ax.set_title(f'exp007: reachable (a,cu) at H-2 (blue=reachable, grey=unreachable)\n'
             f'{len(reachable_acu)}/18 pairs reachable')
ax.set_xticks(range(L+1)); ax.set_yticks(range(k))
ax.grid(alpha=.3); plt.tight_layout()
plt.savefig(f'{EXP}/figures/reachable_acu_grid.png', dpi=130); plt.close()
print(f"\nArtifacts saved to {EXP}")
