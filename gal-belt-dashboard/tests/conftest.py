import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data import load, normalise  # noqa: E402


@pytest.fixture(scope="session")
def df():
    res = load()
    assert res.ok
    return res.df


@pytest.fixture(scope="session")
def raw():
    return pd.read_csv(ROOT / "data" / "gal_belt_data.csv", dtype=str)


def other_tool_faulty(raw: pd.DataFrame) -> pd.DataFrame:
    """Same data, but Tool-02 is the bad one and Tool-05 is fine."""
    out = raw.copy()
    out["Tool_Status"] = "Normal"
    out["Belt_Defect"] = "No"
    out.loc[out["Tool_ID"] == "Tool-02", ["Tool_Status", "Belt_Defect"]] = ["Overdue", "Y"]
    return out


def sample_rows(raw: pd.DataFrame, n=20, seed=1) -> pd.DataFrame:
    return raw.sample(n=n, random_state=seed).reset_index(drop=True)


def no_defects(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out["Belt_Defect"] = "No"
    return out
