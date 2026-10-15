import pandas as pd
import pytest

from backend.app.datasets import get_dataset, load_demo_frames
from backend.app.validation import ValidationOutput, read_csv_bytes, validate


def frame(csv_text: str) -> pd.DataFrame:
    """Build a raw readings/notes frame exactly as an upload would arrive."""
    return read_csv_bytes(csv_text.strip().encode("utf-8"), "test.csv")


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
