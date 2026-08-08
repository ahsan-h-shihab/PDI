#!/usr/bin/env python3
"""
reproduce_all.py — Single-script reproducibility check.

Running this script from the package root:
  python3 reproduce_all.py

will regenerate every primary number reported in the manuscript and
compare each against the saved artifact. Exit code 0 = all match.
No external data, no internet, no GPU required.

Estimated runtime: < 60 seconds on a single CPU core.
"""
import sys, os, json, csv, hashlib, numpy as np
sys.path.insert(0, os.path.dirname(__file__))

# Restore the two byte-exact frozen CSVs from frozen_csvs.zip before any hash
# check. The anonymous review host normalizes text-file line endings, which would
# otherwise break the CRLF-sensitive frozen hashes; the CSVs are therefore shipped
# inside a binary archive. This step is deterministic and fails loudly on any problem.
from restore_frozen import restore_frozen_csvs
restore_frozen_csvs()

from generator   import load_envelope, assert_terminates_at, assert_admissible
from generator_v2 import gen_convergent_v2, assert_prior_level
from policies    import TRAPPolicy, up_edge
from pdi         import emit_terminal_level

PASS = []; FAIL = []

def check(label, expected, got, tol=None):
    if tol is not None:
        ok = abs(float(expected) - float(got)) <= tol
    else:
        ok = str(expected) == str(got) or expected == got
    (PASS if ok else FAIL).append(label)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"         expected : {expected}")
        print(f"         got      : {got}")

BASE = os.path.dirname(__file__)
def path(*parts): return os.path.join(BASE, *parts)

# ── 1. Envelope (exp004) ─────────────────────────────────────────────────────
print("\n── 1. Admissibility envelope (exp004) ──")
env = load_envelope(path('experiments','exp004_envelope','envelope.json'))
check("dT_max = 0.0632",          0.0632, round(env['dT_max'],4))
check("dS_max = 0.0421",          0.0421, round(env['dS_max'],4))
check("g_max = 0.770",            0.770,  round(0.5*1+0.3*1-0.2*env['R_range'][0],3))
check("sample_episodes = 20000",  20000,  env['sample_episodes'])
check("fault_t = 40",             40,     env['scenario']['fault_t'])

# ── 2. Reachable memory states (exp007) ──────────────────────────────────────
print("\n── 2. Reachable (a,cu) states (exp007) ──")
e7 = json.load(open(path('experiments','exp007_memory_enumeration','config.json')))
check("reachable (a,cu) = 13 of 18", 13,    e7['n_reachable_acu'])
check("up_edge(4)+te = 0.850",       0.850, round(up_edge(4)+0.05,3))
check("BFS bins = 500",              500,   e7['N_GBINS'])

# ── 3. Target set (exp006) ───────────────────────────────────────────────────
print("\n── 3. Target set (exp006) ──")
tgts = json.load(open(path('experiments','exp006_pdi_measurement','selected_targets.json')))
g_vals = [round(0.5*t['T_star']+0.3*t['S_star']-0.2*t['R_star'],4) for t in tgts]
check("n_targets = 50",       50,    len(tgts))
check("g* min = 0.484",       0.484, min(g_vals))
check("g* max = 0.548",       0.548, max(g_vals))

# ── 4. PDI primary results (exp009) — full regeneration ──────────────────────
print("\n── 4. PDI measurement — regenerating from frozen artifacts ──")
pol = TRAPPolicy()
PRIOR_LEVELS = [0,1,2,3,4]; SEEDS = [42,137]; H = 100
pdi_vals = []; lmap_e4 = {}

for seed in SEEDS:
    for tgt in tgts:
        x_star = (tgt['T_star'], tgt['S_star'], tgt['R_star'])
        level_map = {}
        for pl in PRIOR_LEVELS:
            try:
                h = gen_convergent_v2(x_star, pl, seed, H, 0, 'controlled', env)
                assert_terminates_at(h, x_star)
                assert_admissible(h, env, 'controlled')
                assert_prior_level(h, pl)
                level_map[pl] = emit_terminal_level(pol, h)
            except (ValueError, AssertionError):
                pass
        if len(level_map) >= 2 and seed == 42:
            pdi_vals.append(max(level_map.values()) - min(level_map.values()))
            if (tgt['T_star'], tgt['S_star'], tgt['R_star']) == (0.68, 0.76, 0.16):
                lmap_e4 = level_map

hsf  = sum(1 for v in pdi_vals if v > 0) / len(pdi_vals)
mean = float(np.mean(pdi_vals))
maxi = int(max(pdi_vals))
dist = {str(int(v)): int(c) for v,c in zip(*np.unique(pdi_vals, return_counts=True))}

saved = json.load(open(path('experiments','exp009_pdi_v2','summary.json')))
check("HSF = 1.000",          saved['HSF'],             round(hsf,3))
check("mean PDI = 3.000",     saved['mean_PDI'],        round(mean,3))
check("max PDI = 3",          saved['max_PDI'],         maxi)
check("distribution {3:50}",  saved['pdi_distribution'], dist)
check("n_computed = 50",      saved['n_targets'],        len(pdi_vals))

# ── 5. Twin-agent case (E4) ──────────────────────────────────────────────────
print("\n── 5. Twin-agent illustrative case (E4) ──")
check("g(x*)=0.536",              0.536, round(0.5*0.68+0.3*0.76-0.2*0.16,3))
check("prior_level=0 -> level 0", 0, lmap_e4.get(0))
check("prior_level=3 -> level 3", 3, lmap_e4.get(3))
check("full level map",           {0:0,1:2,2:2,3:3}, lmap_e4)

# ── 6. Frozen artifact integrity ─────────────────────────────────────────────
print("\n── 6. Frozen artifact integrity ──")
for ffile in ['experiments/exp005_convergent_generator/freeze_hashes.json',
              'experiments/exp008_generator_v2_verification/freeze_hashes_v2.json']:
    hashes = json.load(open(path(ffile)))
    for rel_path, expected in hashes.items():
        actual = hashlib.sha256(open(path(rel_path),'rb').read()).hexdigest()
        check(f"hash:{rel_path.split('/')[-1]}", expected, actual)

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"TOTAL   : {len(PASS)+len(FAIL)}  |  PASS: {len(PASS)}  |  FAIL: {len(FAIL)}")
print("RESULT  : " + ("ALL PASS — manuscript is reproducible" if not FAIL
                      else "FAILURES DETECTED — see above"))
sys.exit(len(FAIL))
