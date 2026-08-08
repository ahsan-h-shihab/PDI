# Reproducibility Package
## When Identical Conditions Yield Different Authority: Measuring Path-Dependence in Trust-to-Authorization Policies

---

## Quick start

```bash
pip install numpy matplotlib
python3 reproduce_all.py
```

Expected output: 31 PASS, 0 FAIL, exit code 0.
Estimated runtime: < 60 seconds, single CPU core, no GPU, no internet.

`reproduce_all.py` (and the two `verify_*_frozen.py` scripts) automatically
restore the two byte-exact frozen CSV artifacts from `frozen_csvs.zip` before
checking their SHA-256 hashes — you do not need to run any extra step. If you
prefer to restore them explicitly first, run:

```bash
python3 restore_frozen.py
```

### Why the frozen CSVs ship inside `frozen_csvs.zip`

Two frozen result artifacts are pinned by SHA-256 and were written with CRLF
line endings:

* `experiments/exp005_convergent_generator/raw_results.csv`
* `experiments/exp008_generator_v2_verification/raw_results.csv`

The anonymous review host normalizes the line endings of any file it serves as
text, which silently rewrites those two CSVs to LF and breaks their frozen
hashes. Binary files (such as a `.zip`) are served byte-for-byte unchanged. To
preserve the exact bytes through the host, the two CSVs are shipped inside the
binary archive `frozen_csvs.zip`, and the verification scripts restore them to
their original paths (with CRLF intact) before hashing. The restoration is
deterministic and fails loudly if the archive is missing, a file is missing
from it, or the extracted bytes do not match the pinned frozen hash. The
ordinary CSV copies remain in the experiment directories so all existing
experiment scripts continue to work unchanged.

---

## What reproduce_all.py checks

`reproduce_all.py` regenerates and verifies the **primary PDI result** and
its **frozen supporting artifacts**: it recomputes the headline PDI
measurement (exp009) from the frozen generator and target set, and checks
every frozen SHA-256 hash. It does **not** run the exp003 natural-trajectory
robustness experiment, which is kept separate to keep the primary
reproduction lightweight (see below). Each row is recomputed from the frozen
source code and compared to the saved artifact:

| Claim | Source artifact |
|---|---|
| dT_max = 0.0632 | experiments/exp004_envelope/envelope.json |
| dS_max = 0.0421 | experiments/exp004_envelope/envelope.json |
| g_max = 0.770 | computed from envelope.json R_range |
| 20,000 episodes (envelope) | experiments/exp004_envelope/envelope.json |
| fault_t = 40 | experiments/exp004_envelope/envelope.json |
| 13 of 18 (a,cu) reachable | experiments/exp007_memory_enumeration/config.json |
| up_edge(4)+te = 0.850 | policies.py BANDS[4] + 0.05 |
| BFS discretisation 500 bins | experiments/exp007_memory_enumeration/config.json |
| n_targets = 50 | experiments/exp006_pdi_measurement/selected_targets.json |
| g* range [0.484, 0.548] | computed from selected_targets.json |
| HSF = 1.000 | regenerated + experiments/exp009_pdi_v2/summary.json |
| mean PDI = 3.000 | regenerated + experiments/exp009_pdi_v2/summary.json |
| max PDI = 3 | regenerated + experiments/exp009_pdi_v2/summary.json |
| distribution {3: 50} | regenerated + experiments/exp009_pdi_v2/summary.json |
| g(x*) = 0.536 (E4) | computed from (0.68, 0.76, 0.16) |
| prior_level=0 → terminal=0 | regenerated from generator_v2 + TRAPPolicy |
| prior_level=3 → terminal=3 | regenerated from generator_v2 + TRAPPolicy |
| full level map (E4) | regenerated + exp009_pdi_v2/processed_results.csv |
| 11 frozen artifact hashes | SHA-256 stored in freeze_hashes*.json |

---

## Natural-trajectory robustness (exp003)

`exp003` is a **separate natural-trajectory robustness experiment**. It mines
only real `gen_trace` simulator trajectories (no generator, no hand-crafted
histories) and reports how often naturally recurring conditions are reached
with more than one authorization level. It is **not** part of
`reproduce_all.py` — it is kept separate so the primary reproduction stays
lightweight. Regenerate it with:

```
python3 experiments/exp003_robustness/run.py
```

**Runtime note:** exp003 is substantially more expensive than the primary
reproduction (it runs 5 bin widths × 5 seeds × 4,000 episodes). On the
reference machine it takes on the order of two minutes, versus about one
second for `reproduce_all.py`.

## Experiment pipeline (in execution order)

Each experiment is self-contained. Run in this order to regenerate all artifacts:

```
exp003  python3 experiments/exp003_robustness/run.py
exp004  python3 experiments/exp004_envelope/run.py
exp005  python3 experiments/exp005_convergent_generator/run.py
exp006  # target selection embedded in exp009; see exp006_pdi_measurement/run.py
exp007  python3 experiments/exp007_memory_enumeration/run.py
exp008  python3 experiments/exp008_generator_v2_verification/run.py
exp009  python3 experiments/exp009_pdi_v2/run.py
```

Integrity checks (run after the pipeline):
```
python3 verify_exp005_frozen.py
python3 verify_exp008_frozen.py
python3 reproduce_all.py
```

---

## File inventory

### Core source files (never modified after freeze)
| File | Role |
|---|---|
| policies.py | Band substrate, tr_tdaa, tr_sym, TRAPPolicy, memoryless baseline |
| sim.py | gen_trace signal generator, Monte Carlo runner |
| variants.py | Trust-only / risk-only policy variants |
| pdi.py | Adapter: drive a policy over a history, read terminal level |
| generator.py | Pilot convergent-trace generator (exp005, frozen) |
| generator_v2.py | Memory-spanning generator (exp008, frozen) |

### Experiment directories
| Directory | Purpose | Primary output |
|---|---|---|
| exp003_robustness/ | Robustness of multi-level signal to bin width and seed | raw_results.csv, figures/ |
| exp004_envelope/ | Empirical admissibility envelope from gen_trace | envelope.json |
| exp005_convergent_generator/ | Verification of generator.py (Spec v2) | raw_results.csv (FROZEN) |
| exp006_pdi_measurement/ | Pilot PDI (null result, documented) + target selection | selected_targets.json |
| exp007_memory_enumeration/ | BFS of reachable (a,cu) states | config.json, raw_results.csv |
| exp008_generator_v2_verification/ | Verification of generator_v2.py | raw_results.csv (FROZEN) |
| exp009_pdi_v2/ | Primary PDI measurement | summary.json, processed_results.csv |

### Integrity files
| File | Role |
|---|---|
| experiments/exp005_convergent_generator/freeze_hashes.json | SHA-256 of all exp005 artifacts |
| experiments/exp008_generator_v2_verification/freeze_hashes_v2.json | SHA-256 of generator_v2.py + exp008 results |
| verify_exp005_frozen.py | Checks exp005 hashes |
| verify_exp008_frozen.py | Checks exp008/generator_v2 hashes |

---

## Scope of reported results

All primary results (HSF=1.000, mean PDI=3.000) are scoped to:
- Policy: TRAPPolicy (tr_tdaa), w=(0.5,0.3,0.2), te=0.05, tr=0.10, k=3
- Target set: 50 conditions with g* in [0.484, 0.548] (bands 2-3)
- Mode: Controlled Mode (empirical envelope, no scenario script)
- Prior levels: {0, 1, 2, 3} (level 4 OOS; level 5 structurally unreachable)
- Seeds: {42, 137}; H = 100 steps

See Section 7 of the manuscript for the full 10-limitation inventory.

---

## exp006 pilot null result

exp006 used a ramp-approach generator and produced PDI=0 at all targets.
This is documented as a pilot finding — a coverage failure of the ramp generator,
not a property of the policy. exp007 identified the cause (all histories produced
a[H-2]=2 regardless of intended family). exp008 verified the fix (generator_v2).
exp006 artifacts are retained unchanged under experiments/exp006_pdi_measurement/.
