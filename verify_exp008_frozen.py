import hashlib, json, sys
hashes=json.load(open('experiments/exp008_generator_v2_verification/freeze_hashes_v2.json'))
fail=0
for path,expected in hashes.items():
    actual=hashlib.sha256(open(path,'rb').read()).hexdigest()
    status="OK" if actual==expected else "TAMPERED"
    if actual!=expected: fail+=1
    print(f"[{status}] {path}")
print("\nexp008/generator_v2 freeze integrity: "+("ALL PASS" if fail==0 else f"{fail} VIOLATION(S)"))
sys.exit(fail)
