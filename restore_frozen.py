#!/usr/bin/env python3
"""
restore_frozen.py — Restore byte-exact frozen CSV artifacts from a binary archive.

WHY THIS EXISTS
---------------
Two frozen result artifacts,

    experiments/exp005_convergent_generator/raw_results.csv
    experiments/exp008_generator_v2_verification/raw_results.csv

were written with CRLF line endings and are pinned by SHA-256 in
freeze_hashes.json / freeze_hashes_v2.json. The anonymous review host
(anonymous.4open.science) normalizes the line endings of any file it detects
as text, which silently rewrites those two CSVs to LF and breaks their frozen
hashes. Binary files (e.g. a .zip) are served byte-for-byte unchanged.

To preserve the exact bytes through the host, the two CSVs are shipped inside
`frozen_csvs.zip` (a binary archive). This module restores them to their exact
original paths before any hash verification runs. It is deterministic and
fails loudly on any problem.

USAGE
-----
    from restore_frozen import restore_frozen_csvs
    restore_frozen_csvs()          # restores the two CSVs, or raises on failure

Run standalone:
    python3 restore_frozen.py      # restores and prints a report; exit 0 on success
"""
import os
import sys
import json
import zipfile
import hashlib

_HERE = os.path.dirname(os.path.abspath(__file__))
_ARCHIVE = os.path.join(_HERE, "frozen_csvs.zip")

# (path relative to package root, freeze-hash file that pins it)
_FROZEN_CSVS = [
    ("experiments/exp005_convergent_generator/raw_results.csv",
     "experiments/exp005_convergent_generator/freeze_hashes.json"),
    ("experiments/exp008_generator_v2_verification/raw_results.csv",
     "experiments/exp008_generator_v2_verification/freeze_hashes_v2.json"),
]


class FrozenRestoreError(RuntimeError):
    """Raised when the frozen CSVs cannot be restored to their exact bytes."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _expected_hash(freeze_hash_file: str, rel_path: str) -> str:
    fp = os.path.join(_HERE, freeze_hash_file)
    if not os.path.exists(fp):
        raise FrozenRestoreError(
            f"freeze-hash file missing: {freeze_hash_file} (cannot verify {rel_path})"
        )
    hashes = json.load(open(fp))
    if rel_path not in hashes:
        raise FrozenRestoreError(
            f"{rel_path} not listed in {freeze_hash_file}"
        )
    return hashes[rel_path]


def restore_frozen_csvs(verbose: bool = True) -> None:
    """Extract the two frozen CSVs from frozen_csvs.zip to their exact paths.

    Fails loudly (raises FrozenRestoreError) if:
      * frozen_csvs.zip is missing;
      * either expected CSV is missing from the archive;
      * the extracted bytes' SHA-256 does not equal the pinned frozen hash.
    """
    if not os.path.exists(_ARCHIVE):
        raise FrozenRestoreError(
            f"frozen_csvs.zip not found at {_ARCHIVE}. "
            "This archive ships the byte-exact frozen CSVs; it is required."
        )

    with zipfile.ZipFile(_ARCHIVE) as z:
        names = set(z.namelist())
        for rel_path, freeze_file in _FROZEN_CSVS:
            if rel_path not in names:
                raise FrozenRestoreError(
                    f"expected member missing from frozen_csvs.zip: {rel_path}"
                )
            data = z.read(rel_path)
            expected = _expected_hash(freeze_file, rel_path)
            actual = _sha256(data)
            if actual != expected:
                raise FrozenRestoreError(
                    f"SHA-256 mismatch for archived {rel_path}\n"
                    f"    expected (frozen): {expected}\n"
                    f"    archive contents:  {actual}\n"
                    "The archive does not contain the pinned frozen bytes; aborting."
                )
            # Write byte-for-byte to the exact path (binary mode: no newline translation).
            out_path = os.path.join(_HERE, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            # Re-read from disk and confirm the on-disk bytes now match the frozen hash.
            on_disk = _sha256(open(out_path, "rb").read())
            if on_disk != expected:
                raise FrozenRestoreError(
                    f"post-write SHA-256 mismatch for {rel_path}\n"
                    f"    expected (frozen): {expected}\n"
                    f"    on disk:           {on_disk}"
                )
            if verbose:
                print(f"  [restored] {rel_path} ({len(data)} bytes, sha256 {actual[:16]}...)")

    if verbose:
        print("  frozen CSVs restored from frozen_csvs.zip and verified against frozen hashes.")


if __name__ == "__main__":
    try:
        restore_frozen_csvs(verbose=True)
    except FrozenRestoreError as e:
        print(f"[FATAL] frozen CSV restoration failed:\n{e}", file=sys.stderr)
        sys.exit(1)
    print("restore_frozen: OK")
    sys.exit(0)
