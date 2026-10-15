from datetime import datetime, timedelta

import pandas as pd
import pytest

from backend.app.datasets import get_dataset, load_demo_frames
from backend.app.pipeline import AnalysisBundle, analyze
from backend.app.validation import ValidationOutput, read_csv_bytes, validate

SYNTHETIC_HEADER = "timestamp,machine_id,vibration_mm_s,temperature_c,pressure_bar,sound_db,rpm,label"


def frame(csv_text: str) -> pd.DataFrame:
    """Build a raw readings/notes frame exactly as an upload would arrive."""
    return read_csv_bytes(csv_text.strip().encode("utf-8"), "test.csv")


def synthetic_rows(machine_id: str, vibrations: list[float], start: datetime = datetime(2026, 10, 14), step_min: int = 15,
                   temperatures: list[float] | None = None) -> str:
    """CSV text for one synthetic machine; all sensors normal except the given vibration/temperature values."""
    lines = [SYNTHETIC_HEADER]
    for i, vib in enumerate(vibrations):
        ts = (start + timedelta(minutes=step_min * i)).strftime("%Y-%m-%dT%H:%M:%S")
        temp = temperatures[i] if temperatures else 60.0
        lines.append(f"{ts},{machine_id},{vib},{temp},170,70,1200,0")
    return "\n".join(lines)


def case(result, machine_id: str):
    return next(c for c in result.cases if c.machine_id == machine_id)


@pytest.fixture(scope="session")
def synthetic_ds():
    return get_dataset("synthetic_fleet")


@pytest.fixture(scope="session")
def metropt_ds():
    return get_dataset("metropt3")


@pytest.fixture(scope="session")
def synthetic_out(synthetic_ds) -> ValidationOutput:
    readings, notes = load_demo_frames("synthetic_fleet")
    return validate(readings, notes, synthetic_ds)


@pytest.fixture(scope="session")
def metropt_out(metropt_ds) -> ValidationOutput:
    readings, notes = load_demo_frames("metropt3")
    return validate(readings, notes, metropt_ds)


@pytest.fixture(scope="session")
def synthetic_run() -> AnalysisBundle:
    readings, notes = load_demo_frames("synthetic_fleet")
    return analyze(readings, notes, "synthetic_fleet")


@pytest.fixture(scope="session")
def metropt_run() -> AnalysisBundle:
    readings, notes = load_demo_frames("metropt3")
    return analyze(readings, notes, "metropt3")
