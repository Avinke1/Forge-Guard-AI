from pathlib import Path
import hashlib
import math

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "ai4i" / "ai4i2020.csv"
OUT_DIR = ROOT / "data" / "processed" / "ai4i"

EXPECTED_COLUMNS = [
    "UDI",
    "Product ID",
    "Type",
    "Air temperature [K]",
    "Process temperature [K]",
    "Rotational speed [rpm]",
    "Torque [Nm]",
    "Tool wear [min]",
    "Machine failure",
    "TWF",
    "HDF",
    "PWF",
    "OSF",
    "RNF",
]


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if not RAW_FILE.is_file():
        raise FileNotFoundError(f"Raw file not found: {RAW_FILE}")

    df = pd.read_csv(RAW_FILE, encoding="utf-8-sig")

    print("=== SOURCE VALIDATION ===")
    print(f"Raw file: {RAW_FILE}")
    print(f"SHA-256: {sha256_file(RAW_FILE)}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "Column names/order do not match the expected source.\n"
            f"Actual: {list(df.columns)}"
        )

    print(f"Missing values: {int(df.isna().sum().sum())}")
    print(f"Duplicate rows: {int(df.duplicated().sum())}")
    print(f"Duplicate UDI values: {int(df['UDI'].duplicated().sum())}")
    print("Type counts:")
    print(df["Type"].value_counts().sort_index().to_string())

    flag_columns = ["Machine failure", "TWF", "HDF", "PWF", "OSF", "RNF"]
    print("Flag values:")
    for column in flag_columns:
        print(f"  {column}: {sorted(df[column].dropna().unique().tolist())}")

    numeric_checks = {
        "Rotational speed [rpm]": "negative rpm",
        "Torque [Nm]": "negative torque",
        "Tool wear [min]": "negative tool wear",
    }
    for column, label in numeric_checks.items():
        print(f"{label}: {int((df[column] < 0).sum())}")

    failure = df["Machine failure"].eq(1)
    mode_columns = ["TWF", "HDF", "PWF", "OSF", "RNF"]
    mode_count = df[mode_columns].sum(axis=1)

    no_mode = int((failure & mode_count.eq(0)).sum())
    mode_without_failure = int((~failure & mode_count.gt(0)).sum())
    multiple_modes = int((mode_count.gt(1)).sum())

    print("Quirk counts:")
    print(f"  Failure with no mode: {no_mode}")
    print(f"  Mode with no failure: {mode_without_failure}")
    print(f"  Two or more modes: {multiple_modes}")

    if df.isna().sum().sum() != 0:
        raise ValueError("Missing values found; stop and investigate.")
    if df["UDI"].duplicated().any():
        raise ValueError("Duplicate UDI values found; stop and investigate.")
    if not set(df["Type"].unique()).issubset({"L", "M", "H"}):
        raise ValueError("Unexpected Type value found.")
    for column in flag_columns:
        if not set(df[column].unique()).issubset({0, 1}):
            raise ValueError(f"Unexpected flag values in {column}.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # These timestamps are ARTIFICIAL, generated only for project ordering.
    timestamps = (
        pd.Timestamp("2026-01-01T00:00:00")
        + pd.to_timedelta(df["UDI"] - 1, unit="min")
    ).dt.strftime("%Y-%m-%dT%H:%M:%S")

    readings = pd.DataFrame({
        "timestamp": timestamps,
        "machine_id": "AI4I-" + df["Type"].astype(str),
        "air_temperature_c": (
            df["Air temperature [K]"] - 273.15
        ).round(2),
        "process_temperature_c": (
            df["Process temperature [K]"] - 273.15
        ).round(2),
        "rpm": df["Rotational speed [rpm]"],
        "torque_nm": df["Torque [Nm]"],
        "tool_wear_min": df["Tool wear [min]"],
        "label": df["Machine failure"].astype(int),
    })

    meta = pd.DataFrame({
        "timestamp": timestamps,
        "machine_id": "AI4I-" + df["Type"].astype(str),
        "udi": df["UDI"],
        "product_id": df["Product ID"],
        "type": df["Type"],
        "machine_failure": df["Machine failure"].astype(int),
        "twf": df["TWF"].astype(int),
        "hdf": df["HDF"].astype(int),
        "pwf": df["PWF"].astype(int),
        "osf": df["OSF"].astype(int),
        "rnf": df["RNF"].astype(int),
        "temp_diff_c": (
            df["Process temperature [K]"]
            - df["Air temperature [K]"]
        ).round(2),
        "power_w": (
            df["Torque [Nm]"]
            * df["Rotational speed [rpm]"]
            * 2 * math.pi / 60
        ).round(1),
        "wear_torque_min_nm": (
            df["Tool wear [min]"] * df["Torque [Nm]"]
        ).round(1),
    })

    readings_path = OUT_DIR / "readings.csv"
    meta_path = OUT_DIR / "meta.csv"

    readings.to_csv(readings_path, index=False, encoding="utf-8")
    meta.to_csv(meta_path, index=False, encoding="utf-8")

    print("\n=== OUTPUT VALIDATION ===")
    print(f"Readings rows: {len(readings)}")
    print(f"Meta rows: {len(meta)}")
    print(f"Failure labels = 1: {int(readings['label'].sum())}")
    print("Machine counts:")
    print(readings["machine_id"].value_counts().sort_index().to_string())
    print(
        "Air temperature range (C): "
        f"{readings['air_temperature_c'].min():.2f}–"
        f"{readings['air_temperature_c'].max():.2f}"
    )
    print(
        "Process temperature range (C): "
        f"{readings['process_temperature_c'].min():.2f}–"
        f"{readings['process_temperature_c'].max():.2f}"
    )
    print("First readings row:")
    print(readings.iloc[0].to_dict())
    print(f"Readings output: {readings_path}")
    print(f"Meta output: {meta_path}")

    expected = {
        "rows": 10000,
        "failures": 339,
        "AI4I-L": 6000,
        "AI4I-M": 2997,
        "AI4I-H": 1003,
        "no_mode": 9,
        "mode_without_failure": 18,
        "multiple_modes": 24,
    }

    actual = {
        "rows": len(readings),
        "failures": int(readings["label"].sum()),
        **{
            machine: int((readings["machine_id"] == machine).sum())
            for machine in ["AI4I-L", "AI4I-M", "AI4I-H"]
        },
        "no_mode": no_mode,
        "mode_without_failure": mode_without_failure,
        "multiple_modes": multiple_modes,
    }

    print("\n=== EXPECTED RESULT CHECK ===")
    all_match = True
    for key, expected_value in expected.items():
        actual_value = actual[key]
        status = "MATCH" if actual_value == expected_value else "DOES NOT MATCH"
        print(
            f"{status}: {key}: actual={actual_value}, "
            f"expected={expected_value}"
        )
        all_match &= actual_value == expected_value

    if all_match:
        print("STRUCTURAL CHECK: PASS")
    else:
        print("STRUCTURAL CHECK: FAIL — investigate before proceeding.")


if __name__ == "__main__":
    main()