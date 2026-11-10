"""The checker must pass a correct file and catch every rule break in the submission guidelines."""
from pathlib import Path

import pytest

from case3.submission import check_submission

IDS = ["BR-V2-000001", "BR-V2-000002", "BR-V2-000003"]
GOOD = "Record_ID,Defect_Found\nBR-V2-000001,Yes\nBR-V2-000002,No\nBR-V2-000003,No\n"


def write(tmp_path: Path, text: str, name="case_3_predictions.csv", raw: bytes | None = None) -> Path:
    p = tmp_path / name
    p.write_bytes(raw if raw is not None else text.encode("utf-8"))
    return p


def test_good_file_passes(tmp_path):
    assert check_submission(write(tmp_path, GOOD), IDS) == []


def test_crlf_line_endings_accepted(tmp_path):
    assert check_submission(write(tmp_path, GOOD.replace("\n", "\r\n")), IDS) == []


def test_row_order_may_differ(tmp_path):
    text = "Record_ID,Defect_Found\nBR-V2-000003,No\nBR-V2-000001,Yes\nBR-V2-000002,No\n"
    assert check_submission(write(tmp_path, text), IDS) == []


@pytest.mark.parametrize("label, text, expect", [
    ("wrong header", GOOD.replace("Defect_Found", "defect_found"), "header"),
    ("extra column", GOOD.replace("Defect_Found\n", "Defect_Found,p\n"), "header"),
    ("missing id", GOOD.replace("BR-V2-000003,No\n", ""), "missing"),
    ("duplicate id", GOOD.replace("BR-V2-000003", "BR-V2-000002"), "duplicate"),
    ("unknown id", GOOD.replace("BR-V2-000003", "BR-V2-999999"), "unknown"),
    ("lowercase label", GOOD.replace(",Yes", ",yes"), "labels"),
    ("probability label", GOOD.replace(",Yes", ",0.83"), "labels"),
    ("blank label", GOOD.replace(",Yes", ","), "labels"),
    ("trailing space", GOOD.replace(",No\n", ",No \n", 1), "spaces"),
    ("case-changed id", GOOD.replace("BR-V2-000001", "br-v2-000001"), "missing"),
    ("extra record", GOOD + "BR-V2-000004,No\n", "records"),
])
def test_rule_breaks_are_caught(tmp_path, label, text, expect):
    problems = check_submission(write(tmp_path, text), IDS)
    assert any(expect in p for p in problems), (label, problems)


def test_bom_caught(tmp_path):
    p = write(tmp_path, "", raw=b"\xef\xbb\xbf" + GOOD.encode())
    assert any("byte-order mark" in x for x in check_submission(p, IDS))


def test_wrong_filename_caught(tmp_path):
    p = write(tmp_path, GOOD, name="case_3_predictions_template.csv")
    assert any("filename" in x for x in check_submission(p, IDS))
