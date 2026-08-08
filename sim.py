import numpy as np

# Authorization policies now live in `policies.py` (core: Base/Static/Symmetric/
# TRAP) and `variants.py` (experimental trust-/risk-only baselines). The
# simulator is policy-agnostic: run() calls policy.update(...) and never branches
# on policy type. Importing `variants` registers the 'trust'/'risk' method
# strings that Tables V & VII reproduce. The band substrate and transition rules
# are re-exported so any external script importing them from `sim` still works.
from policies import (
    BANDS, to_state, up_edge, low_edge,            # band substrate (re-exported)
    tr_static, tr_tdaa, tr_sym,                    # transition rules (re-exported)
    BasePolicy, make_policy, POLICY_REGISTRY,      # policy interface + registry
    StaticPolicy, SymmetricPolicy, TRAPPolicy, TDAAPolicy,
)
import variants  # noqa: F401  (import side effect: registers 'trust' and 'risk')
from variants import TrustOnlyPolicy, RiskOnlyPolicy  # re-exported for convenience

TF, TR, T_END = 40, 60, 100


def gen_trace(rng):
    T = np.zeros(T_END); S = np.zeros(T_END); R = np.zeros(T_END)
    T[0] = rng.uniform(0.60, 0.75); S[0] = rng.uniform(0.65, 0.85)
    for t in range(T_END):
        if t > 0: T[t] = T[t-1] + rng.normal(0, 0.015); S[t] = S[t-1] + rng.normal(0, 0.01)
        if t == TF: T[t] -= rng.uniform(0.20, 0.40); S[t] -= rng.uniform(0.10, 0.25)
        if t >= TR: T[t] += rng.uniform(0.005, 0.015); S[t] += rng.uniform(0.003, 0.010)
        R[t] = rng.uniform(0.15, 0.30) if t < TF else (rng.uniform(0.60, 0.85) if t < TR else rng.uniform(0.30, 0.50))
        T[t] = min(1, max(0, T[t])); S[t] = min(1, max(0, S[t]))
    return T, S, R


def metrics(a, T):
    ch = int(np.sum(a[1:] != a[:-1])); AS = 1 - ch/(T_END-1)
    rr = next((t-TF for t in range(TF, T_END) if t > 0 and a[t] < a[t-1]), np.nan)
    rt = next((t-TR for t in range(TR, T_END) if t > 0 and a[t] > a[t-1]), np.nan)
    inc = [t for t in range(1, T_END) if a[t] > a[t-1]]
    per = (sum(1 for t in inc if TF <= t < TR)/len(inc)) if inc else np.nan
    rec = [t for t in inc if t >= TR]; prr = (sum(1 for t in rec if T[t] < 0.60)/len(rec)) if rec else np.nan
    return AS, rr, rt, per, prr


def run(method=None, n=100, seed=42, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3, policy=None):
    """Monte Carlo evaluation of a single authorization policy.

    Pass either a legacy `method` string ('static'|'trust'|'risk'|'sym'|'tdaa'|
    'trap') OR a ready policy object via `policy=`. The simulator builds the
    policy once, then calls policy.update(T, S, R) per trajectory in place of the
    old if/elif dispatch -- everything else (seeding, trace generation, metrics,
    return contract) is unchanged.

    Because gen_trace runs before, and independently of, the policy, a fixed seed
    yields identical traces for every policy. A future experiment runner can
    therefore sweep policies under identical conditions with no change here:

        for pol in [StaticPolicy(), SymmetricPolicy(), TRAPPolicy()]:
            results[type(pol).__name__] = run(policy=pol, seed=42)
    """
    rng = np.random.default_rng(seed); acc = {x: [] for x in ['AS', 'RR', 'RT', 'PER', 'PRR']}
    pol = policy if policy is not None else make_policy(method, w=w, te=te, tr=tr, k=k)
    for _ in range(n):
        T, S, R = gen_trace(rng)
        a = pol.update(T, S, R)
        AS, rr, rt, per, prr = metrics(a, T); acc['AS'].append(AS)
        for key, v in [('RR', rr), ('RT', rt), ('PER', per), ('PRR', prr)]:
            if not np.isnan(v): acc[key].append(v)
    M = lambda x: (np.mean(x) if x else float('nan')); SD = lambda x: (np.std(x) if x else float('nan'))
    return {kk: M(v) for kk, v in acc.items()} | {'ASsd': SD(acc['AS'])}


def run_records(method=None, n=100, seed=42, w=(0.5, 0.3, 0.2), te=0.05, tr=0.10, k=3, policy=None):
    """Yield one record per Monte Carlo trajectory (per-run granularity).

    This is the per-run companion to run(). It re-uses the EXACT same random
    stream (np.random.default_rng(seed)), the EXACT same gen_trace, and the EXACT
    same metrics -- no metric is added or changed. The difference is only in what
    is exposed: run() NaN-filters RR/RT/PER/PRR and returns aggregates, discarding
    the per-trajectory values; run_records() yields them unfiltered, tagged with a
    run_id and the final authorization state, for structured export.

    Guarantee: aggregating these records with run()'s own NaN-filtering rule
    reproduces run()'s dict exactly (asserted in the test suite). Trajectory i
    here is the SAME trace run() used on its i-th iteration, so per-run rows are
    consistent with the authoritative table values.

    `final_state` is the authorization band at the last timestep (a[-1]); it is a
    single int read off the already-computed trajectory, i.e. negligible overhead.

    Yields dicts: {run_id, seed, AS, RR, RT, PER, PRR, final_state}.
    """
    rng = np.random.default_rng(seed)
    pol = policy if policy is not None else make_policy(method, w=w, te=te, tr=tr, k=k)
    for i in range(n):
        T, S, R = gen_trace(rng)
        a = pol.update(T, S, R)
        AS, rr, rt, per, prr = metrics(a, T)
        yield {'run_id': i, 'seed': seed,
               'AS': AS, 'RR': rr, 'RT': rt, 'PER': per, 'PRR': prr,
               'final_state': int(a[-1])}


print("=== BASELINE (w=.5/.3/.2, te=.05, tr=.10, k=3) ===")
for nm, ky in [("Static", "static"), ("Trust-Only", "trust"), ("Risk-Only", "risk"), ("Symmetric", "sym"), ("TDAA", "tdaa")]:
    r = run(ky); print(f"{nm:11s} AS={r['AS']:.2f}(±{r['ASsd']:.2f}) RR={r['RR']:.2f} RT={r['RT']:.2f} | PER={r['PER']:.2f} PRR={r['PRR']:.2f}")
print("\n=== SENS A weights ===")
for w in [(0.3, 0.4, 0.3), (0.4, 0.4, 0.2), (0.5, 0.3, 0.2), (0.6, 0.2, 0.2)]:
    r = run('tdaa', w=w); print(f"{w} AS={r['AS']:.2f} RR={r['RR']:.2f} RT={r['RT']:.2f}")
print("=== SENS B theta_e ===")
for te in [0.03, 0.05, 0.07]:
    r = run('tdaa', te=te); print(f"te={te} AS={r['AS']:.2f} RR={r['RR']:.2f} RT={r['RT']:.2f}")
print("=== SENS C theta_r ===")
for tr in [0.05, 0.10, 0.15]:
    r = run('tdaa', tr=tr); print(f"tr={tr} AS={r['AS']:.2f} RR={r['RR']:.2f} RT={r['RT']:.2f}")
print("=== SENS D k ===")
for k in [2, 3, 4]:
    r = run('tdaa', k=k); print(f"k={k} AS={r['AS']:.2f} RR={r['RR']:.2f} RT={r['RT']:.2f}")
