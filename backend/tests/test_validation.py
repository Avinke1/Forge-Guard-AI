"""Tests 1 (CLAUDE.md section 11): validation, plus upload checks and data-file integrity."""

import hashlib
from datetime import datetime

import pandas as pd
import pytest

from backend.app.datasets import read_csv_as_text
from backend.app.settings import REPO_ROOT
from backend.app.validation import (
    UploadError,
    check_upload,
    parse_timestamps,
    resolve_dataset,
    validate,
)
from backend.tests.conftest import frame

HEADER = "timestamp,machine_id,vibration_mm_s,temperature_c,pressure_bar,sound_db,rpm,label"


def _events(out, kind, machine_id=None):
    return [e for e in out.quality_events if e.kind == kind and (machine_id is None or e.machine_id == machine_id)]


# ---------------------------------------------------------------- errors


def test_missing_machine_id_column_is_error(synthetic_ds):
    raw = frame("timestamp,vibration_mm_s\n2026-10-14T00:00:00,2.1\n")
    out = validate(raw, None, synthetic_ds)
    assert out.report.ok is False
    assert any("machine_id" in e for e in out.report.errors)
    assert out.readings.empty


def test_missing_timestamp_column_is_error(synthetic_ds):
    out = validate(frame("machine_id,rpm\nFP-01,1200\n"), None, synthetic_ds)
    assert not out.report.ok
    assert any("timestamp" in e for e in out.report.errors)


def test_no_sensor_columns_is_error(synthetic_ds):
    out = validate(frame("timestamp,machine_id,colour\n2026-10-14T00:00:00,FP-01,red\n"), None, synthetic_ds)
    assert not out.report.ok
    assert any("No sensor columns" in e for e in out.report.errors)


def test_zero_rows_is_error(synthetic_ds):
    out = validate(frame(HEADER), None, synthetic_ds)
    assert not out.report.ok
    assert any("no data rows" in e for e in out.report.errors)


def test_only_unreadable_rows_is_error(synthetic_ds):
    out = validate(frame(HEADER + "\nnot-a-time,FP-01,2,60,170,70,1200,0\n"), None, synthetic_ds)
    assert not out.report.ok
    assert out.report.rows_kept == 0


# ---------------------------------------------------------------- synthetic fleet demo (planted cases)


def test_synthetic_demo_counts(synthetic_out):
    r = synthetic_out.report
    assert r.ok and r.errors == []
    assert (r.rows_in, r.rows_kept, r.rows_dropped) == (1724, 1724, 0)
    assert r.synthetic is True
    assert len(synthetic_out.notes) == 20


def test_rpm_minus_50_is_sensor_error_not_a_value(synthetic_out):
    df = synthetic_out.readings
    row = df[(df.machine_id == "DS-02") & (df.timestamp == datetime(2026, 10, 15, 20, 0))]
    assert len(row) == 1
    assert pd.isna(row["rpm"].iloc[0])  # set to empty -> detection can never flag it
    msgs = [w for w in synthetic_out.report.warnings if "sensor error" in w.lower()]
    assert len(msgs) == 1 and "DS-02 rpm = -50" in msgs[0] and "not treated as an anomaly" in msgs[0]
    events = _events(synthetic_out, "sensor_error")
    assert len(events) == 1 and events[0].machine_id == "DS-02" and events[0].sensor == "rpm"


def test_three_empty_cells_reported(synthetic_out):
    events = _events(synthetic_out, "empty_cell")
    assert len(events) == 3
    assert {e.machine_id for e in events} == {"DS-02"}
    assert len([w for w in synthetic_out.report.warnings if w.startswith("Empty cell: DS-02")]) == 3
    df = synthetic_out.readings.set_index("row_id")
    for e in events:
        assert pd.isna(df.loc[e.row_ids[0], e.sensor])


def test_ds02_gap_reported(synthetic_out):
    gaps = _events(synthetic_out, "gap")
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.machine_id == "DS-02"
    assert gap.start == datetime(2026, 10, 15, 2, 45) and gap.end == datetime(2026, 10, 15, 4, 0)
    assert any(w.startswith("Data gap: DS-02") for w in synthetic_out.report.warnings)


def test_label_column_removed(synthetic_out, metropt_out):
    assert "label" not in synthetic_out.readings.columns
    assert "label" not in metropt_out.readings.columns


def test_row_ids_are_original_1_based_rows(synthetic_out):
    raw = read_csv_as_text(REPO_ROOT / "data/processed/synthetic_fleet/readings.csv")
    df = synthetic_out.readings.set_index("row_id")
    for i in (0, 287, 1612, 1723):
        rid = f"R{i + 1}"
        assert df.loc[rid, "machine_id"] == raw.loc[i, "machine_id"]
        assert df.loc[rid, "timestamp"] == pd.Timestamp(raw.loc[i, "timestamp"])
    assert synthetic_out.readings["row_id"].is_unique


def test_no_other_warnings_on_clean_machines(synthetic_out):
    for mid in ("FP-01", "FP-02", "HP-01", "HP-02", "DS-01"):
        assert not [e for e in synthetic_out.quality_events if e.machine_id == mid]


# ---------------------------------------------------------------- warnings on uploaded files


def test_unreadable_timestamp_duplicates_and_unknown_columns(synthetic_ds):
    raw = frame(
        HEADER + ",colour\n"
        "2026-10-14T00:00:00,FP-01,2,60,170,70,1200,0,red\n"
        "2026-10-14T00:00:00,FP-01,2,60,170,70,1200,0,red\n"   # exact duplicate -> dropped
        "2026-10-14T00:15:00,FP-01,2,60,170,70,1200,0,red\n"
        "2026-10-14T00:15:00,FP-01,3,61,171,71,1201,0,red\n"   # same time, other values -> dropped
        "yesterday,FP-01,2,60,170,70,1200,0,red\n"             # unreadable timestamp -> dropped
        "2026-10-14T00:30:00,FP-01,abc,60,170,70,1200,0,red\n"  # unreadable value -> empty
    )
    out = validate(raw, None, synthetic_ds)
    r = out.report
    assert r.ok
    assert (r.rows_in, r.rows_kept, r.rows_dropped) == (6, 3, 3)
    text = " | ".join(r.warnings)
    assert "Ignored unknown columns: colour" in text
    assert "Duplicate row R2" in text
    assert "R4" in text and "repeats an earlier timestamp" in text
    assert "Unreadable timestamp 'yesterday'" in text
    assert "Unreadable value 'abc'" in text
    assert list(out.readings["row_id"]) == ["R1", "R3", "R6"]
    assert "colour" not in out.readings.columns


def test_timezone_suffix_is_dropped_as_wall_clock():
    parsed = parse_timestamps(pd.Series(["2026-10-14T08:00:00+05:30", "2026-10-14T08:00:00Z", "2026-10-14 08:00", "now"]))
    assert list(parsed[:3]) == [pd.Timestamp("2026-10-14T08:00:00")] * 3
    assert pd.isna(parsed[3])


def test_warnings_are_capped(synthetic_ds):
    rows = "\n".join(f"2026-10-14T{h:02d}:00:00,FP-01,,60,170,70,1200,0" for h in range(24))
    out = validate(frame(HEADER + "\n" + rows), None, synthetic_ds)
    empty_lines = [w for w in out.report.warnings if w.startswith("Empty cell")]
    assert len(empty_lines) == 20
    assert any("and 4 more warnings" in w for w in out.report.warnings)
    assert len([e for e in out.quality_events if e.kind == "empty_cell"]) == 24


# ---------------------------------------------------------------- MetroPT-3


def test_metropt_demo_counts_and_low_raw_rows_skipped(metropt_out):
    r = metropt_out.report
    assert r.ok and r.synthetic is False
    assert (r.rows_in, r.rows_kept) == (1898, 1898)
    df = metropt_out.readings
    assert int(df["skip_detection"].sum()) == 6
    assert (df.loc[df.skip_detection, "raw_rows"] < 10).all()
    assert len(_events(metropt_out, "low_raw_rows")) == 6
    assert len(metropt_out.notes) == 6


def test_metropt_small_negative_pressure_is_normal(metropt_out, metropt_ds):
    assert _events(metropt_out, "sensor_error") == []
    raw = frame(
        "timestamp,machine_id,tp2_bar,raw_rows,label\n"
        "2020-07-08T15:20:00,APU-01,-0.03,30,0\n"
        "2020-07-08T15:25:00,APU-01,-5.0,30,0\n"
    )
    out = validate(raw, None, metropt_ds)
    assert out.readings["tp2_bar"].iloc[0] == pytest.approx(-0.03)
    assert pd.isna(out.readings["tp2_bar"].iloc[1])
    assert len(_events(out, "sensor_error")) == 1


def test_metropt_full_history_validates(metropt_ds):
    raw = read_csv_as_text(metropt_ds.full_readings_path)
    out = validate(raw, None, metropt_ds)
    assert out.report.ok
    assert out.report.rows_kept == 50782
    assert "label" not in out.readings.columns


# ---------------------------------------------------------------- notes


def test_bad_notes_are_ignored_with_warnings(synthetic_ds):
    readings = frame(HEADER + "\n2026-10-14T00:00:00,FP-01,2,60,170,70,1200,0\n")
    notes = frame(
        "note_id,machine_id,timestamp,text,source,synthetic\n"
        "N-1,FP-01,2026-10-14T01:00:00,ok note,inspection,true\n"
        "N-2,FP-01,2026-10-14T01:00:00,bad source,email,true\n"
        "N-3,XX-99,2026-10-14T01:00:00,other machine,maintenance,true\n"
        "N-1,FP-01,2026-10-14T02:00:00,duplicate id,inspection,true\n"
    )
    out = validate(readings, notes, synthetic_ds)
    assert list(out.notes["note_id"]) == ["N-1"]
    text = " | ".join(out.report.warnings)
    assert "N-2 has source 'email'" in text
    assert "N-3 is for machine 'XX-99'" in text
    assert "duplicate note_id N-1" in text


def test_notes_missing_column_ignored_not_error(synthetic_ds):
    readings = frame(HEADER + "\n2026-10-14T00:00:00,FP-01,2,60,170,70,1200,0\n")
    out = validate(readings, frame("note_id,text\nN-1,hello\n"), synthetic_ds)
    assert out.report.ok
    assert out.notes.empty
    assert any(w.startswith("Notes file ignored") for w in out.report.warnings)


# ---------------------------------------------------------------- upload checks and dataset choice


@pytest.mark.parametrize(
    "name,size,expected",
    [
        ("readings.txt", 100, "Only .csv files"),
        ("readings", 100, "Only .csv files"),
        ("readings.csv", 0, "empty"),
        ("readings.csv", 10 * 1024 * 1024 + 1, "too large"),
    ],
)
def test_check_upload_rejects(name, size, expected):
    with pytest.raises(UploadError, match=expected):
        check_upload(name, size)


def test_check_upload_accepts_csv_up_to_10_mb():
    check_upload("Readings.CSV", 10 * 1024 * 1024)


def test_resolve_dataset():
    assert resolve_dataset(["timestamp", "machine_id", "rpm", "sound_db"]).id == "synthetic_fleet"
    assert resolve_dataset(["timestamp", "machine_id", "tp2_bar", "oil_temperature_c"]).id == "metropt3"
    assert resolve_dataset(["rpm"], "metropt3").id == "metropt3"
    with pytest.raises(UploadError, match="Unknown dataset"):
        resolve_dataset(["rpm"], "nope")
    with pytest.raises(UploadError, match="No sensor columns"):
        resolve_dataset(["timestamp", "machine_id", "colour"])


# ---------------------------------------------------------------- rule 9: data files never change


def test_verified_data_and_config_files_unchanged():
    manifest = (REPO_ROOT / "docs" / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    checked = 0
    for line in manifest:
        digest, _, rel = line.strip().partition("  ")
        if not rel.startswith(("data/processed/", "config/")):
            continue
        actual = hashlib.sha256((REPO_ROOT / rel).read_bytes()).hexdigest()
        assert actual == digest, f"{rel} changed - data/processed and config files are verified and final"
        checked += 1
    assert checked == 11  # 2 config files + 9 processed data files
