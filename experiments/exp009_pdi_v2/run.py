"""
exp009: PDI measurement using generator_v2.
Consumes: exp006 target list (frozen), generator_v2 (frozen at exp008).
Prior levels: {0,1,2,3,4}. Seeds: {42,137}. Mode: controlled.
Reports HSF, mean PDI, max PDI, distribution, H1 assessment.
"""
import sys,json,csv,subprocess,time,hashlib,itertools
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


from generator   import load_envelope, assert_terminates_at, assert_admissible
from generator_v2 import gen_convergent_v2, assert_prior_level, get_memory_at_H2
from policies import TRAPPolicy
from pdi import emit_terminal_level

EXP      = _HERE
ENV_PATH = _os.path.join(_PKG_ROOT, 'experiments/exp004_envelope/envelope.json')
COMMIT   = _git_commit(_PKG_ROOT)

# Integrity checks
for ffile,key in [
    ('experiments/exp005_convergent_generator/freeze_hashes.json', None),
    ('experiments/exp008_generator_v2_verification/freeze_hashes_v2.json', None)]:
    hashes=json.load(open(ffile))
    for path,expected in hashes.items():
        actual=hashlib.sha256(open(path,'rb').read()).hexdigest()
        assert actual==expected, f"TAMPERED: {path}"
print("Integrity checks: PASS")

envelope = load_envelope(ENV_PATH)
targets  = json.load(open('experiments/exp006_pdi_measurement/selected_targets.json'))
tgt_list = [(t['T_star'],t['S_star'],t['R_star']) for t in targets]
pol      = TRAPPolicy()

PRIOR_LEVELS = [0,1,2,3,4]
SEEDS        = [42, 137]
H            = 100

cfg=dict(experiment_id='exp009_pdi_v2',code_commit=COMMIT,
         exp006_targets='exp006_pdi_measurement/selected_targets.json',
         exp008_generator='generator_v2.py@2a44c91',
         prior_levels=PRIOR_LEVELS,seeds=SEEDS,H=H,
         policy='TRAPPolicy(default)',
         h1_falsification='HSF<0.10 AND mean_PDI<0.10 (pre-registered exp006)')
json.dump(cfg,open(f'{EXP}/config.json','w'),indent=2)
json.dump(dict(prior_levels=PRIOR_LEVELS,seeds=SEEDS,H=H),
          open(f'{EXP}/parameters.json','w'),indent=2)
open(f'{EXP}/seed.txt','w').write('\n'.join(map(str,SEEDS))+'\n')

raw_rows=[]; pdi_rows=[]; t0=time.time()

for seed in SEEDS:
    for x_star in tgt_list:
        level_map={}; oos=[]
        for pl in PRIOR_LEVELS:
            try:
                h=gen_convergent_v2(x_star,pl,seed,H,0,'controlled',envelope)
                assert_terminates_at(h,x_star)
                assert_admissible(h,envelope,'controlled')
                assert_prior_level(h,pl)
                lvl=emit_terminal_level(pol,h)
                level_map[pl]=lvl
                raw_rows.append(dict(seed=seed,T_star=x_star[0],S_star=x_star[1],
                                     R_star=x_star[2],prior_level=pl,
                                     terminal_level=lvl,oos=False,error=''))
            except (ValueError,AssertionError) as e:
                oos.append(pl)
                raw_rows.append(dict(seed=seed,T_star=x_star[0],S_star=x_star[1],
                                     R_star=x_star[2],prior_level=pl,
                                     terminal_level=None,oos=True,error=str(e)[:80]))
        # PDI over available prior levels
        if len(level_map)>=2:
            lvls=list(level_map.values())
            pdi_range=max(lvls)-min(lvls)
            pairs=list(itertools.combinations(level_map.values(),2))
            pdi_dis=sum(1 for a,b in pairs if a!=b)/len(pairs) if pairs else 0.0
        elif len(level_map)==1:
            pdi_range=0; pdi_dis=0.0
        else:
            pdi_range=None; pdi_dis=None
        pdi_rows.append(dict(seed=seed,T_star=x_star[0],S_star=x_star[1],
                             R_star=x_star[2],
                             pdi_range=pdi_range,pdi_dis=pdi_dis,
                             n_levels=len(level_map),oos_levels=str(oos),
                             level_map=str(level_map)))

elapsed=time.time()-t0

# Save raw
fields=['seed','T_star','S_star','R_star','prior_level','terminal_level','oos','error']
with open(f'{EXP}/raw_results.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); [w.writerow(r) for r in raw_rows]

# Save processed
fields2=['seed','T_star','S_star','R_star','pdi_range','pdi_dis',
         'n_levels','oos_levels','level_map']
with open(f'{EXP}/processed_results.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields2); w.writeheader(); [w.writerow(r) for r in pdi_rows]

# Summary statistics (primary seed=42)
pdi42=[r for r in pdi_rows if r['seed']==42 and r['pdi_range'] is not None]
pdi_vals=[r['pdi_range'] for r in pdi42]
hsf=sum(1 for v in pdi_vals if v>0)/len(pdi_vals) if pdi_vals else 0
mean_pdi=float(np.mean(pdi_vals)) if pdi_vals else 0
max_pdi=max(pdi_vals) if pdi_vals else 0
vals,cnts=np.unique(pdi_vals,return_counts=True)
summary=dict(n_targets=len(tgt_list),seed_primary=42,
             HSF=hsf,mean_PDI=mean_pdi,max_PDI=int(max_pdi),
             pdi_distribution={str(int(v)):int(c) for v,c in zip(vals,cnts)},
             elapsed_s=round(elapsed,2))
json.dump(summary,open(f'{EXP}/summary.json','w'),indent=2)

# H1 assessment
h1_fail=hsf<0.10 and mean_pdi<0.10

# Figures
fig,ax=plt.subplots(figsize=(5,3.5))
ax.bar([int(v) for v in vals],[int(c) for c in cnts],color='steelblue',width=0.6)
ax.set_xlabel('PDI_range (authorization levels)'); ax.set_ylabel('count')
ax.set_title(f'exp009: PDI distribution\nHSF={hsf:.3f} mean={mean_pdi:.3f} max={int(max_pdi)}')
for v,c in zip(vals,cnts): ax.text(int(v),int(c)+0.3,str(int(c)),ha='center',fontsize=9)
plt.tight_layout(); plt.savefig(f'{EXP}/figures/pdi_distribution.png',dpi=130); plt.close()

# PDI surface vs ARS
g_vals=[0.5*r['T_star']+0.3*r['S_star']-0.2*r['R_star'] for r in pdi42]
p_vals=[r['pdi_range'] for r in pdi42]
from policies import BANDS
fig,ax=plt.subplots(figsize=(6,3.5))
sc=ax.scatter(g_vals,p_vals,c=p_vals,cmap='Reds',s=40,vmin=0,vmax=max(p_vals) if p_vals else 1)
for b in BANDS: ax.axvline(b,color='grey',ls='--',lw=0.7,alpha=0.5)
ax.set_xlabel('g(x*) = 0.5T+0.3S-0.2R'); ax.set_ylabel('PDI_range')
ax.set_title('exp009: PDI vs ARS (band edges dashed)')
plt.colorbar(sc,ax=ax,label='PDI_range')
plt.tight_layout(); plt.savefig(f'{EXP}/figures/pdi_vs_ars.png',dpi=130); plt.close()

# Console output
print(f"\n{'='*60}")
print(f"exp009 PDI results  commit={COMMIT}  {elapsed:.1f}s")
print(f"{'='*60}")
print(f"targets            : {len(tgt_list)}")
print(f"HSF                : {hsf:.3f}")
print(f"mean PDI           : {mean_pdi:.3f}")
print(f"max PDI            : {int(max_pdi)}")
print(f"PDI distribution   : {dict(zip([int(v) for v in vals],[int(c) for c in cnts]))}")
print(f"{'='*60}")
print(f"H1 (HSF>=0.10 OR mean>=0.10): {'SUPPORTED' if not h1_fail else 'NOT SUPPORTED'}")
if not h1_fail:
    print("PDI is non-trivial and prevalent.")
else:
    print("*** H1 NOT SUPPORTED — reporting as-is ***")
print(f"{'='*60}")
print("\nSample level maps (seed=42, first 8 targets):")
for r in pdi42[:8]:
    print(f"  x*=({r['T_star']:.3f},{r['S_star']:.3f},{r['R_star']:.3f}) "
          f"PDI={r['pdi_range']} levels={r['level_map']}")
