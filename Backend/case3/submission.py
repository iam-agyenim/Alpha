"""Check a predictions file against every rule in the Case 3 submission guidelines.

    python -m case3.submission output/case_3_predictions.csv <case_3_test_inputs.csv>

Any deviation means the organisers discard the file without scoring, so this is strict on purpose.
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pandas as pd

FILENAME = "case_3_predictions.csv"
HEADER = ["Record_ID", "Defect_Found"]
LABELS = {"Yes", "No"}
MAX_BYTES = 1_000_000
MAX_FIELD = 128


def check_submission(path: Path, test_ids) -> list[str]:
    """Return a list of problems; an empty list means the file passes every check."""
    path = Path(path)
    problems: list[str] = []
    if path.name != FILENAME:
        problems.append(f"filename is {path.name!r}, must be {FILENAME!r}")
    if path.is_symlink():
        problems.append("file is a symbolic link")
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES:
        problems.append(f"file is {len(raw)} bytes (max {MAX_BYTES})")
    if raw.startswith(b"\xef\xbb\xbf"):
        problems.append("file starts with a UTF-8 byte-order mark")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return problems + ["file is not valid UTF-8"]

    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        return problems + ["file is empty"]
    if rows[0] != HEADER:
        problems.append(f"header is {rows[0]}, must be {HEADER}")
    body = rows[1:]
    expected = [str(i) for i in pd.Series(test_ids).astype(str)]
    if len(body) != len(expected):
        problems.append(f"{len(body)} records, must be exactly {len(expected)}")

    bad_shape = [i + 2 for i, r in enumerate(body) if len(r) != 2]
    if bad_shape:
        problems.append(f"{len(bad_shape)} records without exactly 2 fields (first at line {bad_shape[0]})")
    fields = [f for r in body for f in r]
    if any(len(f) > MAX_FIELD for f in fields):
        problems.append(f"a field is longer than {MAX_FIELD} characters")
    if any(f != f.strip() or any(ord(ch) < 32 for ch in f) for f in fields):
        problems.append("a field has leading/trailing spaces, tabs, newlines or control characters")

    ids = [r[0] for r in body if r]
    labels = [r[1] for r in body if len(r) > 1]
    bad_labels = sorted(set(labels) - LABELS)
    if bad_labels:
        problems.append(f"labels other than Yes/No: {bad_labels[:5]}")
    dupes = len(ids) - len(set(ids))
    if dupes:
        problems.append(f"{dupes} duplicate Record_IDs")
    missing, unknown = set(expected) - set(ids), set(ids) - set(expected)
    if missing:
        problems.append(f"{len(missing)} test Record_IDs missing (e.g. {sorted(missing)[:3]})")
    if unknown:
        problems.append(f"{len(unknown)} unknown Record_IDs (e.g. {sorted(unknown)[:3]})")
    return problems


if __name__ == "__main__":
    sub, test = Path(sys.argv[1]), Path(sys.argv[2])
    issues = check_submission(sub, pd.read_csv(test, dtype={"Record_ID": str})["Record_ID"])
    print("PASSED: file meets every format rule" if not issues else "FAILED:\n- " + "\n- ".join(issues))
    sys.exit(1 if issues else 0)
