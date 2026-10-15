"""Create the SYNTHETIC 6-machine demo fleet for ForgeGuard AI.

Writes: data/processed/synthetic_fleet/readings.csv, notes.csv, machines.csv
Everything here is SYNTHETIC (made up on purpose, with planted problems).
Limits are illustrative project thresholds, not calibrated.
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "synthetic_fleet"
SEED = 42

MACHINES = [
    ("FP-01", "forging press"),
    ("FP-02", "forging press"),
    ("HP-01", "hydraulic pump"),
    ("HP-02", "hydraulic pump"),
    ("DS-01", "drive shaft"),
    ("DS-02", "drive shaft"),
]

# sensor: (mean, sd, clip_low, clip_high, decimals)
NORMAL = {
    "vibration_mm_s": (2.0, 0.4, 0.8, 3.5, 2),
    "temperature_c": (60.0, 4.0, 40.0, 75.0, 1),
    "pressure_bar": (165.0, 8.0, 140.0, 190.0, 1),
    "sound_db": (70.0, 2.5, 60.0, 78.0, 1),
    "rpm": (1200.0, 10.0, 1170.0, 1230.0, 0),
}

NOTES = [
    ("N-1", "FP-01", "2026-10-14T08:30:00", "inspection", "Start-of-week inspection on FP-01: no issues found."),
    ("N-2", "FP-02", "2026-10-14T09:00:00", "inspection", "Start-of-week inspection on FP-02: no issues found."),
    ("N-3", "HP-01", "2026-10-14T09:30:00", "inspection", "Start-of-week inspection on HP-01: no issues found."),
    ("N-4", "HP-02", "2026-10-14T10:00:00", "maintenance", "Intake filter on HP-02 cleaned."),
    ("N-5", "DS-01", "2026-10-14T10:30:00", "inspection", "Coupling bolts on DS-01 checked, all tight."),
    ("N-6", "DS-02", "2026-10-14T11:00:00", "inspection", "Start-of-week inspection on DS-02: no issues found."),
    ("N-7", "FP-01", "2026-10-14T15:00:00", "maintenance", "Die changed on FP-01 for a new part batch."),
    ("N-8", "FP-02", "2026-10-14T18:00:00", "maintenance", "Lube oil filter on FP-02 due for replacement; scheduled for 16 Oct."),
    ("N-9", "DS-02", "2026-10-15T02:50:00", "error_log", "DS-02 sensor gateway restarted; readings may be missing for about one hour."),
    ("N-10", "DS-01", "2026-10-15T10:10:00", "inspection", "Hammer impact work on the frame next to DS-01 between 10:10 and 10:20."),
    ("N-11", "FP-02", "2026-10-15T14:20:00", "error_log", "FP-02 high temperature alarm acknowledged by operator."),
    ("N-12", "FP-02", "2026-10-15T16:30:00", "maintenance", "FP-02 lube oil level topped up; oil looked dark."),
    ("N-13", "HP-01", "2026-10-15T16:45:00", "maintenance", "Slight bearing noise reported on HP-01, bearing greased."),
    ("N-14", "DS-02", "2026-10-15T20:10:00", "maintenance", "DS-02 rpm sensor cable found loose and re-seated."),
    ("N-15", "FP-01", "2026-10-16T07:00:00", "inspection", "Routine check on FP-01: all readings normal."),
    ("N-16", "HP-01", "2026-10-16T07:30:00", "inspection", "Operator reports HP-01 sounds louder than usual."),
    ("N-17", "FP-02", "2026-10-16T09:00:00", "maintenance", "Lube oil filter on FP-02 replaced."),
    ("N-18", "HP-02", "2026-10-16T10:30:00", "maintenance", "Relief valve on HP-02 adjusted after service."),
    ("N-19", "HP-02", "2026-10-16T11:10:00", "error_log", "HP-02 high pressure alarm."),
    ("N-20", "DS-01", "2026-10-16T14:00:00", "inspection", "Routine check on DS-01: no issues found."),
]


def stop(message):
    print(f"\nSTOP: {message}")
    sys.exit(1)


def normal_block(rng, n):
    data = {}
    for sensor, (mean, sd, low, high, decimals) in NORMAL.items():
        values = np.clip(rng.normal(mean, sd, n), low, high)
        data[sensor] = values.round(decimals) if decimals else np.round(values).astype(int)
    return data


def main():
    rng = np.random.default_rng(SEED)
    times = pd.date_range("2026-10-14T00:00:00", "2026-10-16T23:45:00", freq="15min")
    if len(times) != 288:
        stop(f"Expected 288 timestamps, got {len(times)}")

    frames = []
    for machine_id, _ in MACHINES:
        df = pd.DataFrame({"timestamp": times, "machine_id": machine_id, **normal_block(rng, len(times))})
        df["temperature_c"] = df["temperature_c"].astype(float)
        df["pressure_bar"] = df["pressure_bar"].astype(float)
        df["sound_db"] = df["sound_db"].astype(float)
        df["rpm"] = df["rpm"].astype(float)  # float so DS-02 can hold an empty cell later
        df["label"] = 0
        t = df["timestamp"]

        if machine_id == "HP-01":
            # bearing wear on 16 Oct: ramp 3.5 -> 6.3 from 04:00 to 07:45 (label 0), then 7.0-8.0 + loud
            ramp = (t >= "2026-10-16T04:00:00") & (t <= "2026-10-16T07:45:00")
            df.loc[ramp, "vibration_mm_s"] = np.round(np.linspace(3.5, 6.3, int(ramp.sum())), 2)
            worn = t >= "2026-10-16T08:00:00"
            df.loc[worn, "vibration_mm_s"] = np.round(rng.uniform(7.0, 8.0, int(worn.sum())), 2)
            df.loc[worn, "sound_db"] = np.round(rng.uniform(86.0, 90.0, int(worn.sum())), 1)
            df.loc[worn, "label"] = 1

        if machine_id == "FP-02":
            warm = (t >= "2026-10-15T13:00:00") & (t <= "2026-10-15T13:45:00")
            df.loc[warm, "temperature_c"] = np.round(np.linspace(76.0, 88.0, int(warm.sum())), 1)
            hot = (t >= "2026-10-15T14:00:00") & (t <= "2026-10-15T16:00:00")
            hot_values = np.round(rng.uniform(91.0, 95.5, int(hot.sum())), 1)
            df.loc[hot, "temperature_c"] = hot_values
            df.loc[t == "2026-10-15T15:00:00", "temperature_c"] = 96.0
            df.loc[hot, "label"] = 1

        if machine_id == "HP-02":
            high = (t >= "2026-10-16T11:00:00") & (t <= "2026-10-16T12:00:00")
            df.loc[high, "pressure_bar"] = np.round(rng.uniform(228.0, 237.0, int(high.sum())), 1)
            df.loc[t == "2026-10-16T11:30:00", "pressure_bar"] = 238.0
            df.loc[high, "label"] = 1

        if machine_id == "DS-01":
            df.loc[t == "2026-10-15T10:15:00", "vibration_mm_s"] = 9.0  # one-reading spike, label stays 0

        if machine_id == "DS-02":
            df.loc[t == "2026-10-14T09:00:00", "temperature_c"] = np.nan
            df.loc[t == "2026-10-15T12:00:00", "pressure_bar"] = np.nan
            df.loc[t == "2026-10-16T18:30:00", "sound_db"] = np.nan
            df.loc[t == "2026-10-15T20:00:00", "rpm"] = -50
            gap = (t >= "2026-10-15T03:00:00") & (t <= "2026-10-15T03:45:00")
            df = df.loc[~gap].copy()

        frames.append(df)

    readings = pd.concat(frames, ignore_index=True)
    readings["rpm"] = readings["rpm"].astype("Int64")
    readings["timestamp"] = readings["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    notes = pd.DataFrame(NOTES, columns=["note_id", "machine_id", "timestamp", "source", "text"])
    notes["synthetic"] = "true"
    notes = notes[["note_id", "machine_id", "timestamp", "text", "source", "synthetic"]]

    machines = pd.DataFrame(MACHINES, columns=["machine_id", "machine_type"])
    machines["synthetic"] = "true"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    readings.to_csv(OUTPUT_DIR / "readings.csv", index=False)
    notes.to_csv(OUTPUT_DIR / "notes.csv", index=False)
    machines.to_csv(OUTPUT_DIR / "machines.csv", index=False)

    per_machine = readings.groupby("machine_id").size().to_dict()
    labels = readings.groupby("machine_id")["label"].sum().to_dict()
    empty_cells = int(readings[list(NORMAL)].isna().sum().sum())
    print("SYNTHETIC FLEET SUMMARY (all data is SYNTHETIC)")
    print(f"Readings rows: {len(readings):,} · machines: {readings['machine_id'].nunique()}")
    print(f"Rows per machine: {per_machine}")
    print(f"label = 1 rows: {int(readings['label'].sum())} · per machine: {labels}")
    print(f"Empty sensor cells (DS-02 only): {empty_cells}")
    print(f"Notes: {len(notes)} · Machines: {len(machines)}")

    checks = [
        len(readings) == 1_724,
        readings["machine_id"].nunique() == 6,
        int(readings["label"].sum()) == 78,
        empty_cells == 3,
        len(notes) == 20,
        len(machines) == 6,
    ]
    print("EXPECTED COUNT CHECK:", "PASS" if all(checks) else "FAIL")


if __name__ == "__main__":
    main()
