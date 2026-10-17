"""Tests 2 (detection), 3 (transient rule) and 6 (MetroPT demo) - CLAUDE.md section 11."""

from datetime import datetime

import numpy as np
import pandas as pd

from backend.app.detection import detect, find_runs, zscores
from backend.app.validation import validate
from backend.tests.conftest import case, frame, synthetic_rows

D = datetime


def _limit(result, machine_id, sensor):
    return [a for a in case(result, machine_id).anomalies if a.sensor == sensor and a.method == "limit"]


# ---------------------------------------------------------------- test 2: planted synthetic cases


def test_hp01_vibration_and_sound_from_16_oct_0800(synthetic_run):
    r = synthetic_run.result
    for sensor, peak in (("vibration_mm_s", 8.0), ("sound_db", 90.0)):
        (a,) = _limit(r, "HP-01", sensor)
        assert a.start == D(2026, 10, 16, 8, 0) and a.end == D(2026, 10, 16, 23, 45)
        assert len(a.row_ids) == 64 and a.peak == peak


def test_hp01_ramp_seen_early_by_zscore(synthetic_run):
    z = [a for a in case(synthetic_run.result, "HP-01").anomalies if a.method == "zscore"]
    assert [(a.sensor, a.start) for a in z] == [("vibration_mm_s", D(2026, 10, 16, 4, 0))]


def test_fp02_temperature_14_to_16(synthetic_run):
    (a,) = _limit(synthetic_run.result, "FP-02", "temperature_c")
    assert (a.start, a.end) == (D(2026, 10, 15, 14, 0), D(2026, 10, 15, 16, 0))
    assert len(a.row_ids) == 9 and a.peak == 96.0
    assert "above the 90" in a.reason


def test_hp02_pressure_11_to_12(synthetic_run):
    (a,) = _limit(synthetic_run.result, "HP-02", "pressure_bar")
    assert (a.start, a.end) == (D(2026, 10, 16, 11, 0), D(2026, 10, 16, 12, 0))
    assert len(a.row_ids) == 5 and a.peak == 238.0


def test_no_anomaly_on_ds01_fp01_ds02(synthetic_run):
    for mid in ("DS-01", "FP-01", "DS-02"):
        assert case(synthetic_run.result, mid).anomalies == []


def test_ds01_spike_shown_as_ignored_context(synthetic_run):
    (t,) = synthetic_run.detection.transients
    assert (t.machine_id, t.sensor, t.start) == ("DS-01", "vibration_mm_s", D(2026, 10, 15, 10, 15))
    assert "ignored" in t.message


def test_anomaly_ids_unique_and_rows_belong_to_machine(synthetic_run):
    r = synthetic_run.result
    ids = [a.anomaly_id for c in r.cases for a in c.anomalies]
    assert len(ids) == len(set(ids)) and all(i.startswith("A-") for i in ids)
    machine_of = {x.row_id: x.machine_id for x in r.readings}
    for c in r.cases:
        for a in c.anomalies:
            assert a.machine_id == c.machine_id
            assert {machine_of[rid] for rid in a.row_ids} == {c.machine_id}


# ---------------------------------------------------------------- test 3: transient rule


def test_one_high_reading_alone_is_no_anomaly(synthetic_ds):
    v = validate(frame(synthetic_rows("FP-01", [2, 2, 2, 9.0, 2, 2])), None, synthetic_ds)
    out = detect(v.readings, synthetic_ds)
    assert out.anomalies == []
    assert len(out.transients) == 1 and out.transients[0].row_ids == ["R4"]


def test_two_high_readings_in_a_row_is_anomaly(synthetic_ds):
    v = validate(frame(synthetic_rows("FP-01", [2, 2, 2, 9.0, 7.0, 2])), None, synthetic_ds)
    out = detect(v.readings, synthetic_ds)
    (a,) = out.anomalies
    assert (a.method, a.sensor, a.row_ids, a.peak) == ("limit", "vibration_mm_s", ["R4", "R5"], 9.0)
    assert out.transients == []


def test_gap_breaks_a_run(synthetic_ds):
    text = synthetic_rows("FP-01", [2, 2, 9.0]) + "\n2026-10-14T05:00:00,FP-01,9.0,60,170,70,1200,0\n" \
        "2026-10-14T05:15:00,FP-01,2,60,170,70,1200,0"
    out = detect(validate(frame(text), None, synthetic_ds).readings, synthetic_ds)
    assert out.anomalies == [] and len(out.transients) == 2


def test_zscore_uses_only_past_values_and_needs_two_in_a_row(synthetic_ds):
    rng = np.random.default_rng(0)
    temps = list(np.round(60 + rng.normal(0, 0.5, 40), 2)) + [80.0, 80.0, 60.0]
    v = validate(frame(synthetic_rows("FP-01", [2.0] * 43, temperatures=temps)), None, synthetic_ds)
    out = detect(v.readings, synthetic_ds)
    (a,) = out.anomalies
    assert (a.method, a.sensor, a.row_ids, a.direction) == ("zscore", "temperature_c", ["R41", "R42"], "high")
    assert a.z_peak > 3 and abs(a.baseline_mean - 60) < 1  # baseline excludes the 80s

    temps[41] = 60.0  # only one high reading left -> transient rule removes it
    v = validate(frame(synthetic_rows("FP-01", [2.0] * 43, temperatures=temps)), None, synthetic_ds)
    assert detect(v.readings, synthetic_ds).anomalies == []


def test_zscore_ignored_when_baseline_is_flat():
    values = pd.Series([5.0] * 40 + [50.0, 50.0])
    z, _ = zscores(values, 32)
    assert z.iloc[:41].isna().all()  # baseline std is 0 up to and including the first 50.0
    assert z.iloc[41] > 3  # the baseline now contains one 50.0, so it is no longer flat


def test_find_runs():
    flags = np.array([0, 1, 1, 0, 1, 1, 1], dtype=bool)
    breaks = np.array([0, 0, 0, 0, 0, 1, 0], dtype=bool)
    assert find_runs(flags, breaks) == [(1, 2), (4, 4), (5, 6)]


# ---------------------------------------------------------------- test 6: MetroPT-3 demo (F4 is the held-out check)


def test_metropt_anomaly_overlaps_f4(metropt_run):
    f4_start, f4_end = D(2020, 7, 15, 14, 30), D(2020, 7, 15, 19, 0)
    anomalies = case(metropt_run.result, "APU-01").anomalies
    assert any(a.start <= f4_end and a.end >= f4_start for a in anomalies)


def test_metropt_uses_zscore_only_and_never_raw_rows(metropt_run):
    for a in case(metropt_run.result, "APU-01").anomalies:
        assert a.method == "zscore"
        assert a.sensor != "raw_rows"
        assert len(a.row_ids) >= 12  # sustained: at least 12 windows = 1 h


def test_metropt_low_raw_rows_windows_skipped(metropt_run):
    df = metropt_run.validation.readings
    skipped = set(df.loc[df.skip_detection, "row_id"])
    assert len(skipped) == 6
    for a in metropt_run.detection.anomalies:
        assert not skipped & set(a.row_ids)


def test_zscore_peak_is_the_windows_real_extreme(metropt_run, synthetic_run):
    for bundle in (metropt_run, synthetic_run):
        values = {r.row_id: r.model_dump() for r in bundle.result.readings}
        for c in bundle.result.cases:
            for a in c.anomalies:
                if a.method != "zscore":
                    continue
                window = [values[rid][a.sensor] for rid in a.row_ids if values[rid][a.sensor] is not None]
                assert a.peak == (min(window) if "fell" in a.reason else max(window))
    apu = {a.sensor: a for a in case(metropt_run.result, "APU-01").anomalies}
    assert "fell as low as 6.28 bar" in apu["reservoirs_bar"].reason
    assert "rose as high as 100 %" in apu["low_pressure_alarm_pct"].reason
