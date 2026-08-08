"""
Freeze integrity check for exp005.
Run this at any point to confirm no frozen artifact has been modified.
Exits with code 0 if all hashes match; code 1 if any mismatch is found.
"""
import hashlib, json, sys

hashes = json.load(open('experiments/exp005_convergent_generator/freeze_hashes.json'))
fail = 0
for path, expected in hashes.items():
    try:
        actual = hashlib.sha256(open(path, 'rb').read()).hexdigest()
        status = "OK" if actual == expected else "TAMPERED"
        if actual != expected:
            fail += 1
            print(f"[{status}] {path}")
            print(f"         expected: {expected}")
            print(f"         actual:   {actual}")
        else:
            print(f"[{status}] {path}")
    except FileNotFoundError:
        print(f"[MISSING] {path}")
        fail += 1

print()
if fail == 0:
    print("exp005 freeze integrity: ALL PASS")
else:
    print(f"exp005 freeze integrity: {fail} VIOLATION(S) DETECTED")
sys.exit(fail)
