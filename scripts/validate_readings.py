from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "processed" / "ai4i" / "readings.csv"

EXPECTED_COLUMNS = [
    "timestamp",
    "machine_id",
    "air_temperature_c",
    "process_temperature_c",
    "rpm",
    "torque_nm",
    "tool_wear_min",
    "label",
]

EXPECTED_MACHINE_COUNTS = {
    "AI4I-L": 6000,
    "AI4I-M": 2997,
    "AI4I-H": 1003,
}

EXPECTED_FAILURES = 339


def main():
    if not DATA_PATH.is_file():
        print(f"FAIL: Dataset not found: {DATA_PATH}")
        return 1

    df = pd.read_csv(DATA_PATH)
    checks = {}

    checks["row_count"] = len(df) == 10000
    checks["column_names"] = df.columns.tolist() == EXPECTED_COLUMNS
    checks["missing_values"] = not df.isnull().any().any()
    checks["duplicate_rows"] = not df.duplicated().any()

    if "timestamp" in df.columns:
        timestamps = pd.to_datetime(df["timestamp"], errors="coerce")
        checks["valid_timestamps"] = timestamps.notna().all()
        checks["unique_timestamps"] = not timestamps.duplicated().any()
        checks["chronological_order"] = timestamps.is_monotonic_increasing
        checks["one_minute_intervals"] = (
            timestamps.diff().iloc[1:]
            == pd.Timedelta(minutes=1)
        ).all()
    else:
        checks["timestamp_checks"] = False

    if "machine_id" in df.columns:
        checks["machine_categories"] = (
            df["machine_id"].isin(EXPECTED_MACHINE_COUNTS).all()
        )
        checks["machine_counts"] = (
            df["machine_id"].value_counts().to_dict()
            == EXPECTED_MACHINE_COUNTS
        )

    numeric_columns = [
        "air_temperature_c",
        "process_temperature_c",
        "rpm",
        "torque_nm",
        "tool_wear_min",
        "label",
    ]

    checks["numeric_columns"] = all(
        col in df.columns
        and pd.api.types.is_numeric_dtype(df[col])
        for col in numeric_columns
    )

    for col in [
        "air_temperature_c",
        "process_temperature_c",
        "rpm",
    ]:
        if col in df.columns:
            checks[f"{col}_positive"] = (df[col] > 0).all()

    if "torque_nm" in df.columns:
        checks["torque_nonnegative"] = (df["torque_nm"] >= 0).all()

    if "tool_wear_min" in df.columns:
        checks["tool_wear_nonnegative"] = (
            df["tool_wear_min"] >= 0
        ).all()

    if "label" in df.columns:
        checks["binary_labels"] = df["label"].isin([0, 1]).all()
        checks["failure_count"] = (
            int(df["label"].sum()) == EXPECTED_FAILURES
        )

    print("=== FORGEGUARD DATA VALIDATION ===")
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}: {name}")

    failures = [name for name, passed in checks.items() if not passed]
    print(f"\nPassed: {len(checks) - len(failures)}/{len(checks)}")
    print("Overall:", "PASS" if not failures else "FAIL")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())