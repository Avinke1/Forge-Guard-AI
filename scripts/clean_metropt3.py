"""ForgeGuard AI - CLEAN the MetroPT-3 sensor file (208 MB) and make agent-ready readings with features.

Put EITHER of these in data/raw/metropt3/ (the raw file is only read, never changed):
  - the zip from UCI (any .zip that contains MetroPT3(AirCompressor).csv), or
  - MetroPT3(AirCompressor).csv itself

CLEANING (every step is counted and printed - nothing is hidden, nothing is invented):
  C1 drop the unnamed index column          C5 check missing values (never filled with made-up values)
  C2 check timestamps can be read           C6 out-of-range values -> set empty and counted
  C3 remove exact duplicate rows            C7 digital signals must be 0 or 1
  C4 remove duplicate timestamps, sort      C8 gaps (no data) are dropped, never filled in

FEATURE ENGINEERING (per 5-minute window, using only data up to that time):
  7 sensor averages  + motor_current_max_a + compressor_loading_pct + compressor_loading_1h_pct
  + low_pressure_alarm_pct + raw_rows ; label (from the official failure table, for scoring only)

Writes:
  data/processed/metropt3/readings_full_5min.csv  all 5-minute windows, Feb-Sep 2020
  data/processed/metropt3/readings.csv            demo slice 8-16 Jul 2020 (contains failure F4)
  docs/METROPT3_CLEANING_REPORT.md                what was checked, removed and created
"""

from contextlib import contextmanager
from pathlib import Path
import hashlib
import sys
import zipfile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "metropt3"
OUT_DIR = ROOT / "data" / "processed" / "metropt3"
REPORT = ROOT / "docs" / "METROPT3_CLEANING_REPORT.md"
CSV_NAME = "MetroPT3(AirCompressor).csv"
EXPECTED_SHA256 = "db30ccb4ea402e3c8bf2c99db06e288d4f2a772f6928f9dbe26a920d69793e24"
MACHINE_ID = "APU-01"

# raw analog column -> (app column, lowest valid value, highest valid value)
ANALOG = {
    "TP2": ("tp2_bar", -0.1, 12.0),
    "TP3": ("tp3_bar", -0.1, 12.0),
    "H1": ("h1_bar", -0.1, 12.0),
    "DV_pressure": ("dv_pressure_bar", -0.1, 12.0),
    "Reservoirs": ("reservoirs_bar", -0.1, 12.0),
    "Oil_temperature": ("oil_temperature_c", 0.0, 120.0),
    "Motor_current": ("motor_current_a", 0.0, 15.0),
}
DIGITAL = ["COMP", "DV_eletric", "Towers", "MPG", "LPS", "Pressure_switch", "Oil_level", "Caudal_impulses"]

# Official air-leak failures (UCI MetroPT-3 page / Data Description_Metro.pdf), used for label only
FAILURES = [
    ("F1", "2020-04-18T00:00:00", "2020-04-18T23:59:00"),
    ("F2", "2020-05-29T23:30:00", "2020-05-30T06:00:00"),
    ("F3", "2020-06-05T10:00:00", "2020-06-07T14:30:00"),
    ("F4", "2020-07-15T14:30:00", "2020-07-15T19:00:00"),
]

WINDOW = "5min"
DEMO_START = pd.Timestamp("2020-07-08T00:00:00")
DEMO_END = pd.Timestamp("2020-07-16T23:55:00")
ISO = "%Y-%m-%dT%H:%M:%S"
COLUMNS = ["timestamp", "machine_id", "tp2_bar", "tp3_bar", "h1_bar", "dv_pressure_bar", "reservoirs_bar",
           "oil_temperature_c", "motor_current_a", "motor_current_max_a", "compressor_loading_pct",
           "compressor_loading_1h_pct", "low_pressure_alarm_pct", "raw_rows", "label"]


def stop(message):
    print(f"\nSTOP: {message}")
    sys.exit(1)


def find_raw():
    if not RAW_DIR.is_dir():
        stop(f"Folder not found: {RAW_DIR}\nCreate it and put the zip or the CSV inside.")
    csv_path = RAW_DIR / CSV_NAME
    if csv_path.is_file():
        return csv_path, None
    for zip_path in sorted(RAW_DIR.glob("*.zip")):
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                if member.endswith(CSV_NAME):
                    return zip_path, member
    stop(f"Neither {CSV_NAME} nor a zip containing it was found in:\n{RAW_DIR}")


@contextmanager
def open_raw(path, member):
    if member is None:
        with path.open("rb") as handle:
            yield handle
    else:
        with zipfile.ZipFile(path) as zf, zf.open(member) as handle:
            yield handle


def sha256_raw(path, member):
    digest = hashlib.sha256()
    with open_raw(path, member) as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    print("MetroPT-3 CLEANING + FEATURES: starting.")
    path, member = find_raw()
    print(f"Raw source: {path.name}" + (f" -> {member}" if member else ""))
    sha_ok = sha256_raw(path, member) == EXPECTED_SHA256
    print(f"Matches the official file: {sha_ok}")

    needed = ["timestamp", *ANALOG, *DIGITAL]
    with open_raw(path, member) as handle:
        header = list(pd.read_csv(handle, nrows=0).columns)
    missing_cols = [c for c in needed if c not in header]
    if missing_cols:
        stop(f"Required columns missing: {missing_cols}")
    with open_raw(path, member) as handle:
        raw = pd.read_csv(handle, usecols=needed)
    log = {"raw rows": len(raw), "raw columns": len(header)}

    # C1 - the unnamed index column is simply not read (usecols)
    log["C1 index column dropped"] = len(header) - len(needed)
    # C2 - timestamps
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    bad_times = int(raw["timestamp"].isna().sum())
    raw = raw.dropna(subset=["timestamp"])
    log["C2 unreadable timestamps removed"] = bad_times
    # C3 - exact duplicate rows
    before = len(raw)
    raw = raw.drop_duplicates()
    log["C3 exact duplicate rows removed"] = before - len(raw)
    # C4 - duplicate timestamps (keep first) + sort
    raw = raw.sort_values("timestamp", kind="stable")
    before = len(raw)
    raw = raw.drop_duplicates(subset="timestamp", keep="first")
    log["C4 duplicate timestamps removed"] = before - len(raw)
    # C5 - missing values (counted, never filled)
    for column in [*ANALOG, *DIGITAL]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    log["C5 missing values found (left empty)"] = int(raw[[*ANALOG, *DIGITAL]].isna().sum().sum())
    # C6 - physically impossible analog values -> empty
    out_of_range = 0
    for column, (_, low, high) in ANALOG.items():
        bad = (raw[column] < low) | (raw[column] > high)
        out_of_range += int(bad.sum())
        raw.loc[bad, column] = np.nan
    log["C6 out-of-range analog values set empty"] = out_of_range
    # C7 - digital signals must be 0 or 1
    bad_digital = 0
    for column in DIGITAL:
        bad = raw[column].notna() & ~raw[column].isin([0, 1])
        bad_digital += int(bad.sum())
        raw.loc[bad, column] = np.nan
    log["C7 digital values not 0/1 set empty"] = bad_digital
    # C8 - gaps are reported here and dropped after windowing
    log["C8 gaps longer than 1 hour (no data)"] = int((raw["timestamp"].diff() > pd.Timedelta(hours=1)).sum())
    log["rows after cleaning"] = len(raw)

    # 5-minute windows
    raw = raw.set_index("timestamp")
    raw["loading"] = (raw["COMP"] == 0).astype(float).where(raw["COMP"].notna())
    options = dict(origin="start_day", label="left", closed="left")
    grouped = raw.resample(WINDOW, **options)
    windows = grouped[list(ANALOG)].mean().rename(columns={k: v[0] for k, v in ANALOG.items()})
    windows["motor_current_max_a"] = grouped["Motor_current"].max()
    windows["compressor_loading_pct"] = grouped["loading"].mean() * 100
    windows["low_pressure_alarm_pct"] = grouped["LPS"].mean() * 100
    windows["raw_rows"] = grouped["COMP"].size()
    full = windows.loc[windows["raw_rows"] > 0].copy()
    log["empty 5-minute windows dropped (C8)"] = int((windows["raw_rows"] == 0).sum())
    # 1-hour compressor duty: average of the windows in the last 60 minutes (past data only)
    full["compressor_loading_1h_pct"] = full["compressor_loading_pct"].rolling("60min").mean()

    # label = 1 when the window overlaps an official failure (for scoring only)
    starts, ends = full.index, full.index + pd.Timedelta(WINDOW)
    full["label"] = 0
    per_failure = {}
    for event_id, start, end in FAILURES:
        overlap = (starts < pd.Timestamp(end)) & (ends > pd.Timestamp(start))
        per_failure[event_id] = int(overlap.sum())
        full.loc[overlap, "label"] = 1

    for column in ["tp2_bar", "tp3_bar", "h1_bar", "dv_pressure_bar", "reservoirs_bar",
                   "oil_temperature_c", "motor_current_a", "motor_current_max_a"]:
        full[column] = full[column].round(3)
    for column in ["compressor_loading_pct", "compressor_loading_1h_pct", "low_pressure_alarm_pct"]:
        full[column] = full[column].round(1)
    full.index.name = "timestamp"
    full = full.reset_index()
    demo = full.loc[(full["timestamp"] >= DEMO_START) & (full["timestamp"] <= DEMO_END)].copy()
    for frame in (full, demo):
        frame["timestamp"] = frame["timestamp"].dt.strftime(ISO)
        frame.insert(1, "machine_id", MACHINE_ID)
    full, demo = full[COLUMNS], demo[COLUMNS]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    full.to_csv(OUT_DIR / "readings_full_5min.csv", index=False, encoding="utf-8")
    demo.to_csv(OUT_DIR / "readings.csv", index=False, encoding="utf-8")

    sensor_cols = COLUMNS[2:-2]
    empty_cells = int(full[sensor_cols].isna().sum().sum())
    normal, fail = full[full["label"] == 0], full[full["label"] == 1]
    compare = {c: (round(normal[c].mean(), 2), round(fail[c].mean(), 2))
               for c in ["compressor_loading_pct", "compressor_loading_1h_pct", "low_pressure_alarm_pct",
                         "motor_current_max_a", "tp3_bar"]}

    print("\nCLEANING LOG")
    for name, value in log.items():
        print(f"  {name}: {value:,}")
    print("\nOUTPUT")
    print(f"  5-minute windows: {len(full):,} - first {full['timestamp'].iloc[0]} - last {full['timestamp'].iloc[-1]}")
    print(f"  columns: {len(COLUMNS)} - empty sensor cells: {empty_cells}")
    print(f"  label = 1 windows: {int(full['label'].sum())} - per failure: {per_failure}")
    print(f"  demo rows (8-16 Jul 2020): {len(demo):,} - label = 1 in demo: {int(demo['label'].sum())}")
    print("\nFEATURE CHECK (average in normal windows vs failure windows)")
    for name, (n_mean, f_mean) in compare.items():
        print(f"  {name}: normal {n_mean} - failure {f_mean}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# MetroPT-3 cleaning report (ForgeGuard AI)", "",
             "Source: UCI MetroPT-3 (dataset 791), MetroPT3(AirCompressor).csv, CC BY 4.0, real data.",
             f"Raw file matches the official SHA-256: {sha_ok}", "", "## Cleaning steps", "",
             "| Step | Result |", "|---|---|"]
    lines += [f"| {name} | {value:,} |" for name, value in log.items()]
    lines += ["", "Small negative pressures (down to about -0.03 bar) are sensor zero noise and are kept.",
              "Gaps (compressor off / no data) are dropped, never filled with made-up values.", "",
              "## Output columns (5-minute windows, machine APU-01)", "",
              "| Column | Meaning |", "|---|---|",
              "| timestamp | start of the 5-minute window (ISO 8601) |",
              "| machine_id | APU-01 (the metro train air compressor) |",
              "| tp2_bar ... motor_current_a | average of the 7 analog sensors in the window |",
              "| motor_current_max_a | highest motor current in the window (A) |",
              "| compressor_loading_pct | % of the window the compressor was loading (COMP = 0) |",
              "| compressor_loading_1h_pct | average loading % over the last 60 minutes (past data only) |",
              "| low_pressure_alarm_pct | % of the window the low-pressure signal LPS was active (below 7 bar) |",
              "| raw_rows | number of raw 10-second readings in the window (30 = complete) |",
              "| label | 1 if the window overlaps an official air-leak failure F1-F4; for scoring only, never an agent input |",
              "", "## Why these features (measured on this data)", "",
              "| Feature | Normal windows | Failure windows |", "|---|---|---|"]
    lines += [f"| {name} | {n_mean} | {f_mean} |" for name, (n_mean, f_mean) in compare.items()]
    lines += ["", f"Windows: {len(full):,} (full), {len(demo):,} (demo 8-16 Jul 2020). "
              f"Failure windows: {int(full['label'].sum())} {per_failure}.", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nOUTPUT FILES\n  {(OUT_DIR / 'readings_full_5min.csv').relative_to(ROOT)}\n"
          f"  {(OUT_DIR / 'readings.csv').relative_to(ROOT)}\n  {REPORT.relative_to(ROOT)}")

    checks = {
        "official raw file": sha_ok,
        "raw rows 1,516,948": log["raw rows"] == 1_516_948,
        "nothing removed in C2-C7": all(log[k] == 0 for k in log if k[:2] in {"C2", "C3", "C4", "C5", "C6", "C7"}),
        "windows 50,782": len(full) == 50_782,
        "label = 1 windows 994": int(full["label"].sum()) == 994,
        "per failure 288/78/574/54": per_failure == {"F1": 288, "F2": 78, "F3": 574, "F4": 54},
        "demo rows 1,898 / label 54": len(demo) == 1_898 and int(demo["label"].sum()) == 54,
        "empty sensor cells 0": empty_cells == 0,
        "loading much higher in failures": compare["compressor_loading_pct"][1] > 90 > 30 > compare["compressor_loading_pct"][0],
    }
    failed = [name for name, ok in checks.items() if not ok]
    print("\nEXPECTED COUNT CHECK:", "PASS" if not failed else "FAIL - report to the team lead")
    for name in failed:
        print(f"  did not match: {name}")


if __name__ == "__main__":
    main()
