import hashlib, json, sys, os
# Restore the byte-exact frozen CSV from frozen_csvs.zip before hashing (the
# anonymous host normalizes text line endings; the CSV ships in a binary archive).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from restore_frozen import restore_frozen_csvs
restore_frozen_csvs()
hashes=json.load(open('experiments/exp008_generator_v2_verification/freeze_hashes_v2.json'))
fail=0
for path,expected in hashes.items():
    actual=hashlib.sha256(open(path,'rb').read()).hexdigest()
    status="OK" if actual==expected else "TAMPERED"
    if actual!=expected: fail+=1
    print(f"[{status}] {path}")
print("\nexp008/generator_v2 freeze integrity: "+("ALL PASS" if fail==0 else f"{fail} VIOLATION(S)"))
sys.exit(fail)
