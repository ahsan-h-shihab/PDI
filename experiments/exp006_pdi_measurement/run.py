"""
exp006: PDI measurement on TRAPPolicy using frozen generator (exp005).
Target list is pre-frozen in selected_targets.json.
No target is added, removed, or re-selected after this script starts.
"""
import sys, json, csv, subprocess, time, hashlib
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
# Restore byte-exact frozen CSVs from frozen_csvs.zip before the inline hash checks
# below (the anonymous host normalizes text line endings; CSVs ship in a binary archive).
try:
    from restore_frozen import restore_frozen_csvs as _rfc
    _rfc(verbose=False)
except Exception as _e:
    pass  # if the archive is absent (e.g. original dev tree), fall through to existing checks


from generator import load_envelope, gen_convergent, FAMILIES
from generator import assert_terminates_at, assert_admissible
from policies import TRAPPolicy, to_state
from pdi import emit_terminal_level

EXP      = _HERE
ENV_PATH = _os.path.join(_PKG_ROOT, 'experiments/exp004_envelope/envelope.json')
COMMIT   = _git_commit(_PKG_ROOT)

# --- Integrity check: exp005 must be unmodified ---
hashes = json.load(open(
    _os.path.join(_PKG_ROOT, 'experiments/exp005_convergent_generator/freeze_hashes.json')))
for path,expected in hashes.items():
    try:
        actual = hashlib.sha256(open(path,'rb').read()).hexdigest()
        assert actual==expected, f"exp005 TAMPERED: {path}"
    except FileNotFoundError:
        raise RuntimeError(f"exp005 artifact missing: {path}")
print("exp005 integrity: PASS")

envelope = load_envelope(ENV_PATH)
targets  = json.load(open(f'{EXP}/selected_targets.json'))
pol      = TRAPPolicy()          # canonical default parameters

SEEDS  = [42, 137]              # primary + robustness seed
MODES  = ['controlled']         # Natural Mode is exp007 (robustness)
H      = 100

# --- Persist config before any computation ---
cfg = dict(experiment_id='exp006_pdi_measurement', code_commit=COMMIT,
           exp005_ref='exp005_convergent_generator@ce8adce',
           envelope_path=ENV_PATH, n_targets=len(targets),
           seeds=SEEDS, modes=MODES, H=H, families=list(FAMILIES),
           policy='TRAPPolicy(default: w=(.5,.3,.2) te=.05 tr=.10 k=3)',
           h1_falsification='HSF<0.10 AND mean_PDI<0.10',
           h2_falsification='mean_PDI non-monotone in k across k={2,3,4}')
json.dump(cfg, open(f'{EXP}/config.json','w'), indent=2)
json.dump(dict(seeds=SEEDS,modes=MODES,H=H,n_targets=len(targets),
               families=list(FAMILIES)),
          open(f'{EXP}/parameters.json','w'), indent=2)
open(f'{EXP}/seed.txt','w').write('\n'.join(map(str,SEEDS))+'\n')

# ── PDI computation ──────────────────────────────────────────────────────────
raw_rows = []
t0 = time.time()

for mode in MODES:
    for seed in SEEDS:
        for tgt in targets:
            x_star = (tgt['T_star'], tgt['S_star'], tgt['R_star'])
            level_map = {}
            oos_families = []

            for family in FAMILIES:
                row = dict(mode=mode, seed=seed,
                           T_star=x_star[0], S_star=x_star[1], R_star=x_star[2],
                           family=family, terminal_level=None,
                           s1_pass=None, adm_pass=None, oos=False, error='')
                try:
                    h = gen_convergent(x_star, family, seed, H, mode, envelope)
                    # spot-check S1 and ADM on every history (not just exp005 grid)
                    assert_terminates_at(h, x_star)
                    assert_admissible(h, envelope, mode)
                    row['s1_pass'] = True; row['adm_pass'] = True
                    lvl = emit_terminal_level(pol, h)
                    row['terminal_level'] = lvl
                    level_map[family] = lvl
                except (ValueError, AssertionError) as e:
                    row['oos'] = True; row['error'] = str(e)[:120]
                    oos_families.append(family)
                raw_rows.append(row)

            # PDI computation: only over families that succeeded
            if len(level_map) >= 2:
                levels = list(level_map.values())
                pdi_range = max(levels) - min(levels)
                import itertools
                pairs = list(itertools.combinations(level_map.keys(), 2))
                n_dis = sum(1 for f1,f2 in pairs
                            if level_map[f1] != level_map[f2])
                pdi_dis = n_dis / len(pairs) if pairs else 0.0
            elif len(level_map) == 1:
                pdi_range = 0; pdi_dis = 0.0
            else:
                pdi_range = None; pdi_dis = None

            # append aggregate row
            raw_rows.append(dict(
                mode=mode, seed=seed,
                T_star=x_star[0], S_star=x_star[1], R_star=x_star[2],
                family='__AGGREGATE__',
                terminal_level=None,
                s1_pass=None, adm_pass=None, oos=False,
                error=f'pdi_range={pdi_range} pdi_dis={pdi_dis:.4f} '
                      f'n_families={len(level_map)} oos={oos_families}'))

elapsed = time.time() - t0

# ── Save raw results ─────────────────────────────────────────────────────────
fields = ['mode','seed','T_star','S_star','R_star','family',
          'terminal_level','s1_pass','adm_pass','oos','error']
with open(f'{EXP}/raw_results.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); [w.writerow(r) for r in raw_rows]

# ── Processed results (per target, primary seed=42, controlled) ──────────────
proc_rows = []
for tgt in targets:
    x_star = (tgt['T_star'], tgt['S_star'], tgt['R_star'])
    agg = [r for r in raw_rows
           if r['family']=='__AGGREGATE__'
           and r['T_star']==x_star[0] and r['S_star']==x_star[1]
           and r['R_star']==x_star[2] and r['seed']==42
           and r['mode']=='controlled']
    if not agg: continue
    err_str = agg[0]['error']
    pdi_range = None; pdi_dis = None
    for part in err_str.split():
        if part.startswith('pdi_range='): pdi_range=part.split('=')[1]
        if part.startswith('pdi_dis='):   pdi_dis=float(part.split('=')[1])
    fam_rows = [r for r in raw_rows
                if r['family']!='__AGGREGATE__'
                and r['T_star']==x_star[0] and r['S_star']==x_star[1]
                and r['R_star']==x_star[2] and r['seed']==42
                and r['mode']=='controlled']
    levels = {r['family']:r['terminal_level'] for r in fam_rows
              if r['terminal_level'] is not None}
    proc_rows.append(dict(T_star=x_star[0], S_star=x_star[1], R_star=x_star[2],
                          pdi_range=pdi_range, pdi_dis=pdi_dis,
                          known_levels=tgt['known_levels'],
                          level_F1=levels.get('F1_degrade'),
                          level_F2=levels.get('F2_recover'),
                          level_F3=levels.get('F3_counter_primed'),
                          level_F4=levels.get('F4_counter_reset'),
                          n_families=len(levels)))

with open(f'{EXP}/processed_results.csv','w',newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(proc_rows[0]))
    w.writeheader(); [w.writerow(r) for r in proc_rows]

# ── Compute summary statistics ───────────────────────────────────────────────
pdi_vals = []
for r in proc_rows:
    try: pdi_vals.append(int(r['pdi_range']))
    except (TypeError,ValueError): pass

hsf  = sum(1 for v in pdi_vals if v>0)/len(pdi_vals) if pdi_vals else None
mean_pdi = float(np.mean(pdi_vals)) if pdi_vals else None
max_pdi  = int(max(pdi_vals)) if pdi_vals else None

summary = dict(n_targets=len(targets), n_computed=len(pdi_vals),
               HSF=hsf, mean_PDI=mean_pdi, max_PDI=max_pdi,
               pdi_distribution={str(int(v)):int(c) for v,c in zip(*np.unique(pdi_vals,return_counts=True))} if pdi_vals else {},
               elapsed_s=round(elapsed,2))
json.dump(summary, open(f'{EXP}/summary.json','w'), indent=2,
          default=lambda x: int(x) if hasattr(x,'item') else x)

# ── Figures ───────────────────────────────────────────────────────────────────
# Fig 1: PDI distribution (bar chart)
fig,ax = plt.subplots(figsize=(5,3.5))
vals,cnts = np.unique(pdi_vals, return_counts=True)
ax.bar(vals, cnts, color='steelblue', width=0.6)
ax.set_xlabel('PDI_range (authorization levels)'); ax.set_ylabel('count of targets')
ax.set_title(f'exp006: PDI distribution (n={len(pdi_vals)} targets, TRAPPolicy, controlled)')
ax.set_xticks(range(int(max(vals))+1))
for v,c in zip(vals,cnts): ax.text(v,c+0.3,str(c),ha='center',fontsize=9)
plt.tight_layout()
plt.savefig(f'{EXP}/figures/pdi_distribution.png', dpi=130)
plt.close()

# Fig 2: PDI surface projected onto ARS (g) axis
import sys; sys.path.insert(0, _PKG_ROOT)
from policies import BANDS
g_vals = [0.5*r['T_star']+0.3*r['S_star']-0.2*r['R_star'] for r in proc_rows]
pdi_plot = [int(r['pdi_range']) if r['pdi_range'] not in (None,'None') else 0
            for r in proc_rows]
fig,ax = plt.subplots(figsize=(6,3.5))
sc = ax.scatter(g_vals, pdi_plot, c=pdi_plot, cmap='Reds', s=40,
                vmin=0, vmax=max(pdi_plot) if pdi_plot else 1)
for b in BANDS: ax.axvline(b, color='grey', ls='--', lw=0.7, alpha=0.5)
ax.set_xlabel('ARS g(x*) = 0.5T+0.3S-0.2R')
ax.set_ylabel('PDI_range (levels)')
ax.set_title('exp006: PDI vs ARS readiness (band edges shown)')
plt.colorbar(sc, ax=ax, label='PDI_range')
plt.tight_layout()
plt.savefig(f'{EXP}/figures/pdi_vs_ars.png', dpi=130)
plt.close()

# ── Console summary ───────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"exp006 summary  (commit {COMMIT}, {elapsed:.1f}s)")
print(f"{'='*60}")
print(f"targets computed   : {len(pdi_vals)}/{len(targets)}")
print(f"HSF                : {hsf:.3f}" if hsf is not None else "HSF: n/a")
print(f"mean PDI           : {mean_pdi:.3f}" if mean_pdi is not None else "mean PDI: n/a")
print(f"max PDI            : {max_pdi}")
print(f"PDI distribution   : {dict(zip([int(v) for v in vals],[int(c) for c in cnts]))}")
print(f"{'='*60}")
# H1 evaluation
if hsf is not None and mean_pdi is not None:
    h1_fail = hsf<0.10 and mean_pdi<0.10
    print(f"H1 (PDI non-trivial, HSF>=0.10 OR mean>=0.10): "
          f"{'NOT SUPPORTED' if h1_fail else 'SUPPORTED'}")
    if h1_fail:
        print("*** H1 FALSIFIED — stopping and reporting as pre-registered ***")
print(f"{'='*60}")
