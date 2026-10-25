from datetime import date, datetime
from pathlib import Path

import pytest

from prime import db, evidence, synthetic
from prime.tools import Toolbox

TODAY = date(2026, 10, 13)
NOW = datetime(2026, 10, 13, 9, 0, 0)
FIRST = date(2026, 9, 13)                       # day 1 = TODAY - 30


def d(n: int) -> str:
    """ISO date of scenario day n (1..30)."""
    return date.fromordinal(FIRST.toordinal() + n - 1).isoformat()


def make(tmp_path: Path, scenario=None, name="t.db"):
    conn = db.connect(tmp_path / name)
    data = synthetic.build(TODAY, scenario)
    synthetic.load_into(conn, data)
    evidence.load_evidence(conn)
    return conn, Toolbox(conn, tmp_path / (name + ".ics"), now=NOW), data


@pytest.fixture()
def loaded(tmp_path):
    return make(tmp_path)


@pytest.fixture()
def no_failure(tmp_path):
    return make(tmp_path, synthetic.Scenario(failure_days=None), "nf.db")
