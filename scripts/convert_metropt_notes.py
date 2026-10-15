"""ForgeGuard AI - convert the MetroPT-3 source notes into the agent's format.

Reads:  knowledge/metropt3_notes_source.csv          (never changed)
Writes: data/processed/metropt3/notes.csv           note_id, machine_id, timestamp, text, source, synthetic
        data/processed/metropt3/fault_events.csv    event_id, machine_id, failure, severity, start, end,
                                                    maintenance_report_as_written
"""

from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "knowledge" / "metropt3_notes_source.csv"
OUT_DIR = ROOT / "data" / "processed" / "metropt3"
MACHINE_ID = "APU-01"
ISO = "%Y-%m-%dT%H:%M:%S"

SOURCE_COLUMNS = ["note_id", "timestamp_start", "timestamp_end", "note_type", "component",
                  "note_text", "source", "source_url"]

# Official UCI failure table: (event, start, end, maintenance report as written)
OFFICIAL_FAILURES = [
    ("F1", "2020-04-18T00:00:00", "2020-04-18T23:59:00", ""),
    ("F2", "2020-05-29T23:30:00", "2020-05-30T06:00:00",
     "Maintenance on 30Apr at 12:00 (as written; before the failure - TO CHECK)"),
    ("F3", "2020-06-05T10:00:00", "2020-06-07T14:30:00", "Maintenance on 8Jun at 16:00"),
    ("F4", "2020-07-15T14:30:00", "2020-07-15T19:00:00", "Maintenance on 16Jul at 00:00"),
]

EXPECTED_NOTE_TIMES = ["2020-04-18T23:59:00", "2020-05-30T06:00:00", "2020-06-07T14:30:00",
                       "2020-06-08T16:00:00", "2020-07-15T19:00:00", "2020-07-16T00:00:00"]


def stop(message):
    print(f"\nSTOP: {message}")
    sys.exit(1)


def to_time(value, record, field):
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        stop(f"Invalid {field} in {record}: {value!r}")
    return parsed


def main():
    if not SOURCE.is_file():
        stop(f"Source notes not found: {SOURCE}")
    source = pd.read_csv(SOURCE, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if list(source.columns) != SOURCE_COLUMNS:
        stop(f"Unexpected source columns: {list(source.columns)}")
    if len(source) != 6:
        stop(f"Expected 6 source rows, found {len(source)}")

    notes, failures = [], []
    for position, row in source.reset_index(drop=True).iterrows():
        record = row["note_id"].strip()
        note_type = row["note_type"].strip().lower()
        start = to_time(row["timestamp_start"], record, "timestamp_start")
        if note_type == "failure_report":
            end = to_time(row["timestamp_end"], record, "timestamp_end")
            time = end  # failure report: END of the failure window
            text = (f"Air leak failure report (severity: high stress), window "
                    f"{start:%d %b %Y %H:%M} to {end:%d %b %Y %H:%M}. "
                    f"Source: UCI MetroPT-3 failure table (source record {record}).")
            failures.append((start.strftime(ISO), end.strftime(ISO)))
        elif note_type == "maintenance_record":
            time = start  # maintenance record: START time
            if not row["note_text"].strip():
                stop(f"Empty note_text in {record}")
            text = f"{row['note_text'].strip()} (source record {record})"
        else:
            stop(f"Unknown note_type in {record}: {row['note_type']!r}")
        notes.append([f"N-{position + 1}", MACHINE_ID, time.strftime(ISO), text, "maintenance", "false"])

    if failures != [(s, e) for _, s, e, _ in OFFICIAL_FAILURES]:
        stop(f"Failure windows in the source do not match the official UCI table: {failures}")

    notes = pd.DataFrame(notes, columns=["note_id", "machine_id", "timestamp", "text", "source", "synthetic"])
    events = pd.DataFrame(
        [[event, MACHINE_ID, "Air leak", "High stress", start, end, report]
         for event, start, end, report in OFFICIAL_FAILURES],
        columns=["event_id", "machine_id", "failure", "severity", "start", "end",
                 "maintenance_report_as_written"],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    notes.to_csv(OUT_DIR / "notes.csv", index=False, encoding="utf-8")
    events.to_csv(OUT_DIR / "fault_events.csv", index=False, encoding="utf-8")

    print("METROPT-3 NOTES CONVERSION")
    print(f"Source rows: {len(source)} - notes written: {len(notes)} - fault events written: {len(events)}")
    for _, row in notes.iterrows():
        print(f"  {row['note_id']}  {row['timestamp']}  {row['text'][:60]}")
    checks = [
        notes["timestamp"].tolist() == EXPECTED_NOTE_TIMES,
        notes["note_id"].tolist() == [f"N-{i}" for i in range(1, 7)],
        len(events) == 4,
    ]
    print("\nEXPECTED COUNT CHECK:", "PASS" if all(checks) else "FAIL - report to the team lead")


if __name__ == "__main__":
    main()