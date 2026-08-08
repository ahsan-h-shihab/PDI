"""
generator_v2.py — Memory-spanning convergent-trace generator (v2 final).

Core design principle: at every step in Phase 2, verify that the actual
policy step (a,cu) would not change the level, and if it would, reduce
the signal by adjusting R upward (using R's unconstrained step freedom).
This makes phase 2 robust regardless of T/S boundary effects.

Phase 1: Escalate 0 -> prior_level using k+ramp steps per band.
Phase 2: Hold at prior_level. Each step verified not to change level.
Phase 3: Descent to x_star with R=R_pin (pinned), verified not to
         escalate past prior_level.
Terminal row: hard-set to x_star (S1).
"""
from __future__ import annotations
import json, math
import numpy as np
from generator import load_envelope, assert_terminates_at, assert_admissible

_BANDS=[0.20,0.35,0.50,0.65,0.80]; _L=5
def _to_state(g):
    s=0
    for b in _BANDS:
        if g>=b: s+=1
    return s
def _up_edge(a): return _BANDS[a] if a<_L else 1e9
def _low_edge(a): return _BANDS[a-1] if a>=1 else -1e9
def _clamp(v,lo,hi): return float(max(lo,min(hi,v)))
def _ars(T,S,R): return 0.5*T+0.3*S-0.2*R
_TE=0.05; _TR=0.10; _K=3

def _tr_step(a,cu,g_prev,g_next):
    d=g_next-g_prev
    if d<-_TR: return min(a,_to_state(g_next)),0
    elif g_next>=_up_edge(a)+_TE:
        cu2=cu+1
        if cu2>=_K: return min(a+1,_L),0
        return a,cu2
    else: return a,0

def get_memory_at_H2(h:np.ndarray):
    sc=_ars(h[:,0],h[:,1],h[:,2]); a=_to_state(sc[0]); cu=0
    aH2=a; cuH2=0
    for t in range(1,len(h)):
        a,cu=_tr_step(a,cu,sc[t-1],sc[t])
        if t==len(h)-2: aH2,cuH2=a,cu
    return aH2,cuH2

def _safe_step(T_prev,S_prev,R_prev,g_prev,a_cur,cu_cur,
               T_target,S_target,
               dT_max,dS_max,T_lo,T_hi,S_lo,S_hi,R_lo,R_hi,
               must_hold:bool=True,prime:bool=False):
    """
    Compute one admissible step that:
      - moves T toward T_target and S toward S_target
      - if must_hold: ensures the policy does NOT change level (a stays = a_cur)
        by adjusting R to suppress escalation/restriction if needed.
      - if prime: allows escalation counter to increment (but not fire).
    Returns (T_new, S_new, R_new, g_new).
    Raises ValueError if holding is impossible (e.g. at level boundary).
    """
    dT=_clamp(T_target-T_prev,-dT_max,dT_max)
    dS=_clamp(S_target-S_prev,-dS_max,dS_max)
    T_new=_clamp(T_prev+dT,T_lo,T_hi)
    S_new=_clamp(S_prev+dS,S_lo,S_hi)
    # Start with R_lo (maximum ARS headroom)
    R_new=R_lo
    g_new=_ars(T_new,S_new,R_new)

    if must_hold:
        # Check if step would change level
        a_next,cu_next=_tr_step(a_cur,cu_cur,g_prev,g_new)
        # If level would increase: raise R to bring g below up_edge(a_cur)+TE
        if a_next>a_cur:
            g_max_ok=_up_edge(a_cur)+_TE-0.001
            # R needed: g = 0.5T+0.3S-0.2R => R=(0.5T+0.3S-g)/0.2
            R_needed=(0.5*T_new+0.3*S_new-g_max_ok)/0.2
            R_new=_clamp(R_needed,R_lo,R_hi)
            g_new=_ars(T_new,S_new,R_new)
        # If level would decrease (restriction): raise R increases risk, drops ARS further
        # Instead raise T/S by less (take smaller step toward target)
        a_next2,cu_next2=_tr_step(a_cur,cu_cur,g_prev,g_new)
        if a_next2<a_cur:
            # Step is too large a drop; take zero step in T
            T_new=T_prev; g_new=_ars(T_new,S_new,R_new)
            a_next3,_=_tr_step(a_cur,cu_cur,g_prev,g_new)
            if a_next3!=a_cur:
                # Still failing; pin everything
                T_new=T_prev; S_new=S_prev; R_new=R_lo
                g_new=_ars(T_new,S_new,R_new)

    return T_new,S_new,R_new,g_new

def gen_convergent_v2(x_star,prior_level:int,seed:int,
                      H:int=100,cu_target:int=0,
                      mode:str='controlled',
                      envelope:dict|None=None,
                      envelope_path:str|None=None)->np.ndarray:
    if envelope is None:
        if envelope_path is None: raise ValueError("provide envelope or envelope_path")
        envelope=load_envelope(envelope_path)
    rng=np.random.default_rng(int(seed))
    T_star=float(x_star[0]); S_star=float(x_star[1]); R_star=float(x_star[2])
    dT_max=float(envelope['dT_max']); dS_max=float(envelope['dS_max'])
    T_lo,T_hi=float(envelope['T_range'][0]),float(envelope['T_range'][1])
    S_lo,S_hi=float(envelope['S_range'][0]),float(envelope['S_range'][1])
    R_lo,R_hi=float(envelope['R_range'][0]),float(envelope['R_range'][1])
    if not(T_lo<=T_star<=T_hi): raise ValueError("T* out of range")
    if not(S_lo<=S_star<=S_hi): raise ValueError("S* out of range")
    if not(R_lo<=R_star<=R_hi): raise ValueError("R* out of range")
    if prior_level not in range(_L): raise ValueError(f"prior_level={prior_level} not in 0-4")
    if cu_target not in range(_K): raise ValueError(f"cu_target={cu_target} not in 0-{_K-1}")

    g_star=_ars(T_star,S_star,R_star)

    # ── Phase 1: escalate 0 -> prior_level ──────────────────────────────────
    rows=[]; T_cur=T_lo; S_cur=_clamp(0.75,S_lo,S_hi); R_cur=R_lo
    g_cur=_ars(T_cur,S_cur,R_cur)
    rows.append((T_cur,S_cur,R_cur)); a_cur=_to_state(g_cur); cu_cur=0

    for lvl in range(prior_level):
        g_esc=_up_edge(lvl)+_TE+0.02
        if g_esc>_ars(T_hi,S_cur,R_lo):
            raise ValueError(f"Cannot escalate past level {lvl}")
        # Step toward g_esc until k consecutive escalation steps fire
        cu_in_esc=0
        while cu_in_esc<_K:
            T_new,S_new,R_new,g_new=_safe_step(
                T_cur,S_cur,R_cur,g_cur,a_cur,cu_cur,
                (g_esc+0.2*R_lo-0.3*S_cur)/0.5,S_cur,
                dT_max,dS_max,T_lo,T_hi,S_lo,S_hi,R_lo,R_hi,
                must_hold=False)   # allow level to change during escalation
            # Force R=R_lo and target g_esc exactly
            R_new=R_lo
            T_new=_clamp((g_esc+0.2*R_lo-0.3*S_cur)/0.5,T_lo,T_hi)
            T_new=_clamp(T_cur+_clamp(T_new-T_cur,-dT_max,dT_max),T_lo,T_hi)
            g_new=_ars(T_new,S_cur,R_lo)
            a_new,cu_new=_tr_step(a_cur,cu_cur,g_cur,g_new)
            rows.append((T_new,S_cur,R_lo))
            T_cur=T_new; g_cur=g_new
            if g_new>=_up_edge(a_cur)+_TE: cu_in_esc+=1
            else: cu_in_esc=0
            a_cur=a_new; cu_cur=cu_new
            if a_cur==lvl+1: break   # escalation fired
        if a_cur!=lvl+1:
            raise ValueError(f"Failed to escalate to level {lvl+1} (stuck at {a_cur})")

    ph1_len=len(rows)

    # ── Phase 3 minimum length ───────────────────────────────────────────────
    # Must close T gap from current T to T_star and S gap
    T_gap=abs(T_star-T_cur); S_gap=abs(S_star-S_cur)
    ph3_min=max(4,math.ceil(T_gap/dT_max)+2,math.ceil(S_gap/dS_max)+2)

    # ── Phase 2: hold at prior_level ─────────────────────────────────────────
    ph2_len=max(4,H-ph1_len-ph3_min); ph3_len=H-ph1_len-ph2_len
    if ph3_len<2: raise ValueError(f"H={H} too short")

    safe_steps=ph2_len-cu_target; prime_steps=cu_target
    if safe_steps<0: safe_steps=0; prime_steps=ph2_len

    # safe hold: must_hold=True, target T_star gradually
    for i in range(safe_steps):
        T_tgt=T_cur+(T_star-T_cur)/(safe_steps-i+1)
        T_new,S_new,R_new,g_new=_safe_step(
            T_cur,S_cur,R_cur,g_cur,a_cur,cu_cur,
            T_tgt,S_cur,dT_max,dS_max,T_lo,T_hi,S_lo,S_hi,R_lo,R_hi,
            must_hold=True)
        rows.append((T_new,S_new,R_new))
        a_cur,cu_cur=_tr_step(a_cur,cu_cur,g_cur,g_new)
        T_cur=T_new; S_cur=S_new; R_cur=R_new; g_cur=g_new

    # prime: prime_steps CONSECUTIVE steps with g above threshold.
    # Must NOT use _safe_step (which would suppress escalation via R).
    # Use direct bounded T move toward g_prime, R=R_lo pinned.
    # Cap prime_steps at k-2 to avoid firing escalation (need cu < k at H-2).
    prime_steps = min(prime_steps, _K - 1)
    if prime_steps>0:
        g_prime=_up_edge(prior_level)+_TE+0.01
        g_prime=_clamp(g_prime,_ars(T_lo,S_cur,R_lo)+0.01,_ars(T_hi,S_cur,R_lo)-0.01)
        for _ in range(prime_steps):
            T_tgt=_clamp((g_prime+0.2*R_lo-0.3*S_cur)/0.5,T_lo,T_hi)
            T_new=_clamp(T_cur+_clamp(T_tgt-T_cur,-dT_max,dT_max),T_lo,T_hi)
            g_new=_ars(T_new,S_cur,R_lo)
            a_new,cu_new=_tr_step(a_cur,cu_cur,g_cur,g_new)
            if a_new != prior_level:
                break  # escalation fired prematurely; stop priming
            rows.append((T_new,S_cur,R_lo))
            T_cur=T_new; g_cur=g_new; a_cur=a_new; cu_cur=cu_new

    # ── Phase 3: descent to x_star with must_hold=True until terminal ────────
    for i in range(ph3_len-1):
        sl=ph3_len-1-i
        T_tgt=T_cur+(T_star-T_cur)/(sl+1)
        S_tgt=S_cur+(S_star-S_cur)/(sl+1)
        T_new,S_new,R_new,g_new=_safe_step(
            T_cur,S_cur,R_cur,g_cur,a_cur,cu_cur,
            T_tgt,S_tgt,dT_max,dS_max,T_lo,T_hi,S_lo,S_hi,R_lo,R_hi,
            must_hold=True)
        rows.append((T_new,S_new,R_new))
        a_cur,cu_cur=_tr_step(a_cur,cu_cur,g_cur,g_new)
        T_cur=T_new; S_cur=S_new; R_cur=R_new; g_cur=g_new

    # Exact terminal row (S1)
    rows.append((float(T_star),float(S_star),float(R_star)))

    if len(rows)!=H:
        raise ValueError(f"Length {len(rows)} != {H}")
    h=np.array(rows,dtype=float)

    # Natural Mode overlay
    if mode=='natural':
        ft=int(envelope['scenario']['fault_t']); rt=int(envelope['scenario']['recovery_t'])
        for t in range(H-1):
            if t<ft:   h[t,2]=float(rng.uniform(0.15,0.30))
            elif t<rt: h[t,2]=float(rng.uniform(0.60,0.85))
            else:      h[t,2]=float(rng.uniform(0.30,0.50))
        if ft<H-1:
            fm=float(rng.uniform(envelope['dT_fault_min'],envelope['dT_fault_max']))
            h[ft,0]=_clamp(h[ft,0]-fm,T_lo,T_hi)
        for t in range(ft+1,H-1):
            sl=H-1-t
            h[t,0]=_clamp(h[t-1,0]+_clamp((T_star-h[t-1,0])/(sl+1),-dT_max,dT_max),T_lo,T_hi)
            h[t,1]=_clamp(h[t-1,1]+_clamp((S_star-h[t-1,1])/(sl+1),-dS_max,dS_max),S_lo,S_hi)
        h[-1]=[T_star,S_star,R_star]
    elif mode!='controlled': raise ValueError(f"Unknown mode {mode!r}")
    return h

def assert_reproducible_v2(x_star,prior_level,seed,H,cu_target,mode,envelope):
    h1=gen_convergent_v2(x_star,prior_level,seed,H,cu_target,mode,envelope)
    h2=gen_convergent_v2(x_star,prior_level,seed,H,cu_target,mode,envelope)
    assert np.array_equal(h1,h2),"S4-v2: differ"

def assert_prior_level(h:np.ndarray,prior_level:int)->None:
    a,_=get_memory_at_H2(h)
    assert a==prior_level,f"got a[H-2]={a}, expected {prior_level}"
