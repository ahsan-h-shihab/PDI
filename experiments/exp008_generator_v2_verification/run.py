"""exp008: verification of generator_v2. Hard gates: S1, ADM, S4, prior_level."""
import sys,json,csv,subprocess,time,hashlib
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
# Restore byte-exact frozen CSVs from frozen_csvs.zip before the inline hash checks
# below (the anonymous host normalizes text line endings; CSVs ship in a binary archive).
try:
    from restore_frozen import restore_frozen_csvs as _rfc
    _rfc(verbose=False)
except Exception as _e:
    pass  # if the archive is absent (e.g. original dev tree), fall through to existing checks

from generator   import load_envelope, assert_terminates_at, assert_admissible
from generator_v2 import (gen_convergent_v2, assert_reproducible_v2,
                           assert_prior_level, get_memory_at_H2)
from policies import TRAPPolicy
from pdi import emit_terminal_level

EXP      = _HERE
ENV_PATH = _os.path.join(_PKG_ROOT, 'experiments/exp004_envelope/envelope.json')
COMMIT   = _git_commit(_PKG_ROOT)

# integrity check (exp005 frozen)
for freeze in [_os.path.join(_PKG_ROOT, 'experiments/exp005_convergent_generator/freeze_hashes.json')]:
    hashes=json.load(open(freeze))
    for path,expected in hashes.items():
        actual=hashlib.sha256(open(path,'rb').read()).hexdigest()
        assert actual==expected, f"TAMPERED: {path}"
print("exp005 integrity: PASS")

envelope = load_envelope(ENV_PATH)
pol      = TRAPPolicy()
targets  = json.load(open(_os.path.join(_PKG_ROOT, 'experiments/exp006_pdi_measurement/selected_targets.json')))
test_tgts= [(t['T_star'],t['S_star'],t['R_star']) for t in targets[:10]]

PRIOR_LEVELS = [0,1,2,3,4]
CU_TARGETS   = [0,2]          # cu=0 and cu=k-1=2
SEEDS        = [42,137]
MODES        = ['controlled']
H            = 100

json.dump(dict(experiment_id='exp008_generator_v2_verification',
               code_commit=COMMIT,exp005_ref='ce8adce',
               prior_levels=PRIOR_LEVELS,cu_targets=CU_TARGETS,
               seeds=SEEDS,modes=MODES,H=H,n_targets=len(test_tgts)),
          _wopen(f'{EXP}/config.json','w'),indent=2)
json.dump(dict(prior_levels=PRIOR_LEVELS,cu_targets=CU_TARGETS,
               seeds=SEEDS,H=H),
          _wopen(f'{EXP}/parameters.json','w'),indent=2)
_wopen(f'{EXP}/seed.txt','w').write('\n'.join(map(str,SEEDS))+'\n')

raw_rows=[]; n_s1=n_adm=n_s4=n_pl=n_oos=0; t0=time.time()

for mode in MODES:
    for x_star in test_tgts:
        for prior_level in PRIOR_LEVELS:
            for cu_tgt in CU_TARGETS:
                for seed in SEEDS:
                    row=dict(mode=mode,T_star=x_star[0],S_star=x_star[1],
                             R_star=x_star[2],prior_level=prior_level,
                             cu_target=cu_tgt,seed=seed,
                             s1_pass=None,adm_pass=None,
                             s4_pass=None,pl_pass=None,
                             actual_a_H2=None,actual_cu_H2=None,
                             terminal_level=None,error='')
                    try:
                        h=gen_convergent_v2(x_star,prior_level,seed,H,
                                            cu_tgt,mode,envelope)
                        # S1
                        try: assert_terminates_at(h,x_star); row['s1_pass']=True
                        except AssertionError as e:
                            row['s1_pass']=False; row['error']+=f"S1:{e} "; n_s1+=1
                        # ADM
                        try: assert_admissible(h,envelope,mode); row['adm_pass']=True
                        except AssertionError as e:
                            row['adm_pass']=False; row['error']+=f"ADM:{e} "; n_adm+=1
                        # S4
                        try:
                            assert_reproducible_v2(x_star,prior_level,seed,H,
                                                   cu_tgt,mode,envelope)
                            row['s4_pass']=True
                        except AssertionError as e:
                            row['s4_pass']=False; row['error']+=f"S4:{e} "; n_s4+=1
                        # prior_level
                        a_H2,cu_H2=get_memory_at_H2(h)
                        row['actual_a_H2']=a_H2; row['actual_cu_H2']=cu_H2
                        try:
                            assert_prior_level(h,prior_level); row['pl_pass']=True
                        except AssertionError as e:
                            row['pl_pass']=False; row['error']+=f"PL:{e} "; n_pl+=1
                        row['terminal_level']=emit_terminal_level(pol,h)
                    except ValueError as e:
                        row['error']+=f"OOS:{e}"; n_oos+=1
                    raw_rows.append(row)

elapsed=time.time()-t0
fields=['mode','T_star','S_star','R_star','prior_level','cu_target','seed',
        's1_pass','adm_pass','s4_pass','pl_pass',
        'actual_a_H2','actual_cu_H2','terminal_level','error']
with _wopen(f'{EXP}/raw_results.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); [w.writerow(r) for r in raw_rows]

hard=n_s1+n_adm+n_s4+n_pl
print(f"\n{'='*60}")
print(f"exp008  commit={COMMIT}  {elapsed:.1f}s")
print(f"{'='*60}")
print(f"histories attempted : {len(raw_rows)}")
print(f"S1  failures  (HARD): {n_s1}")
print(f"ADM failures  (HARD): {n_adm}")
print(f"S4  failures  (HARD): {n_s4}")
print(f"PL  failures  (HARD): {n_pl}")
print(f"OOS (logged)        : {n_oos}")
print(f"{'='*60}")
print("HARD GATE: "+("PASSED" if hard==0 else f"FAILED ({hard} failures)"))
if hard>0:
    fails=[r for r in raw_rows if r.get('s1_pass')==False
           or r.get('adm_pass')==False or r.get('s4_pass')==False
           or r.get('pl_pass')==False]
    print("\nFirst 5 failures:")
    for r in fails[:5]:
        print(f"  pl={r['prior_level']} cu={r['cu_target']} "
              f"a_H2={r['actual_a_H2']} err={r['error'][:80]}")

# Level map summary (seed=42, mode=controlled, first target)
x0=test_tgts[0]
print(f"\nLevel map for x*={x0} seed=42 controlled:")
for pl in PRIOR_LEVELS:
    for cu in CU_TARGETS:
        matching=[r for r in raw_rows
                  if r['T_star']==x0[0] and r['S_star']==x0[1]
                  and r['R_star']==x0[2] and r['prior_level']==pl
                  and r['cu_target']==cu and r['seed']==42
                  and r['mode']=='controlled'
                  and r.get('pl_pass') is not None]
        if matching:
            r=matching[0]
            print(f"  prior_level={pl} cu_tgt={cu} -> "
                  f"a[H-2]={r['actual_a_H2']} cu[H-2]={r['actual_cu_H2']} "
                  f"terminal={r['terminal_level']}")
