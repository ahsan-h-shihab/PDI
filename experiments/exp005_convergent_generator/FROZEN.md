# exp005 — FROZEN ARTIFACT

Frozen at commit: ce8adce
Frozen at: 2024-07 (PDI paper implementation)

## Freeze declaration

This experiment directory is permanently frozen.
No file in this directory may be modified, overwritten, or deleted.
No file in generator.py may be modified in ways that affect exp005 outputs.

## What is frozen

- experiments/exp005_convergent_generator/config.json
- experiments/exp005_convergent_generator/parameters.json
- experiments/exp005_convergent_generator/seed.txt
- experiments/exp005_convergent_generator/raw_results.csv
- experiments/exp005_convergent_generator/processed_results.json
- experiments/exp005_convergent_generator/log.md
- experiments/exp005_convergent_generator/figures/  (empty at freeze)
- generator.py at commit ce8adce

## Verified properties at freeze

- S1 failures  : 0  (exact terminal convergence)
- ADM failures : 0  (admissibility A1-A4)
- S4 failures  : 0  (bit-exact reproducibility)
- OOS (logged) : 36 (F4/low-R*, physical constraint, expected)
- S3-insensitive: 48 (logged, not a hard failure)
- Total histories verified: 264

## Consumption contract for exp006 and beyond

exp006 MUST:
- load generator.py from commit ce8adce (or verify hash match)
- load envelope from experiments/exp004_envelope/envelope.json
- not re-run or re-verify exp005 assertions (they are done)
- reference exp005 by experiment ID in its own config.json
- not modify any file under experiments/exp005_convergent_generator/

If a correctness or reproducibility bug is discovered in generator.py
after this freeze, it must be:
1. documented in research_log.md under a new entry
2. fixed in a new generator version (e.g. generator_v2.py)
3. re-verified in a new experiment (e.g. exp005b_generator_v2)
exp005 itself remains untouched as the record of what was produced.

## Reproducibility verification command

python3 -c "
import sys; sys.path.insert(0,'/tmp/tdaa')
from generator import load_envelope, gen_convergent
from pdi import emit_terminal_level
from policies import TRAPPolicy
import numpy as np
env = load_envelope('experiments/exp004_envelope/envelope.json')
h = gen_convergent((0.21,0.70,0.65), 'F1_degrade', 42, 100, 'controlled', env)
assert h[-1,0]==0.21 and h[-1,1]==0.70 and h[-1,2]==0.65
pol = TRAPPolicy()
lvl = emit_terminal_level(pol, h)
print(f'Freeze verification: terminal level={lvl}, x*=(0.21,0.70,0.65) [PASS]')
"
