"""Step 2 - DETECT (CLAUDE.md section 5.2). Rules + statistics only, no machine learning.

Method A - LIMIT: value above warn_high or below warn_low (only where the dataset config has limits).
Method B - ZSCORE: z = (value - mean) / std of the machine's OWN previous N readings (shift by 1, so the
  current value is never part of its own baseline). Ignored when the baseline std is ~0 or fewer than
  N/2 past values exist. Plain mean/std (NOT median/MAD): measured on the synthetic fleet, median/MAD
  falsely flagged FP-01 and DS-01, mean/std did not (STEP 2 measurement).
TRANSIENT RULE: a flag counts only if it holds for at least `min_consecutive` consecutive readings of
  that machine + sensor (synthetic 2; MetroPT-3 12 = 1 h, tuned on F1-F3 only). A data gap longer than
  2x the normal interval breaks a run. MetroPT windows with raw_rows < 10 are left out completely.
A one-off LIMIT flag that is too short is returned as a Transient (shown as context, never evidence).
A z-score run lying completely inside a limit run on the same sensor is dropped as a duplicate.

The "label" column never reaches this module (validation removes it).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backend.app.datasets import DatasetConfig, SensorSpec

STD_EPSILON = 1e-9


@dataclass
class Detected:
    """One anomaly before ranking. anomaly_id and severity are filled in by the pipeline/ranking."""

    machine_id: str
    sensor: str
    method: str  # "limit" | "zscore"
    direction: str  # "high" | "low"
    start: datetime
    end: datetime
    peak: float  # the most extreme real reading, in sensor units
    unit: str
    row_ids: list[str]
    magnitude_ratio: float  # limit: fraction beyond the limit; zscore: |z| at the peak
    reason: str
    limit: float | None = None
    z_peak: float | None = None
    baseline_mean: float | None = None
    anomaly_id: str = ""

    @property
    def duration_hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600.0


@dataclass
class Transient:
    """A limit flag shorter than the transient rule allows: ignored, but shown as context."""

    machine_id: str
    sensor: str
    start: datetime
    end: datetime
    row_ids: list[str]
    message: str


@dataclass
class DetectionOutput:
    anomalies: list[Detected] = field(default_factory=list)
    transients: list[Transient] = field(default_factory=list)


# ---------------------------------------------------------------- helpers


def fmt_value(value: float) -> str:
    return f"{round(float(value), 2):g}"


def fmt_duration(td: timedelta) -> str:
    minutes = int(round(td.total_seconds() / 60))
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"
    return f"{mins} min"


def _ts(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%dT%H:%M:%S")


def find_runs(flags: np.ndarray, breaks: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (first, last) positions of runs of True. breaks[i] = reading i does not follow i-1."""
    runs: list[tuple[int, int]] = []
    start = None
    for i, flagged in enumerate(flags):
        if flagged and start is not None and breaks[i]:
            runs.append((start, i - 1))
            start = None
        if flagged and start is None:
            start = i
        elif not flagged and start is not None:
            runs.append((start, i - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    return runs


def _gap_breaks(times: pd.Series) -> np.ndarray:
    diffs = times.diff()
    normal = diffs.median()
    breaks = np.zeros(len(times), dtype=bool)
    if len(times) > 1 and not pd.isna(normal) and normal > pd.Timedelta(0):
        breaks = (diffs > 2 * normal).fillna(False).to_numpy(dtype=bool)
    return breaks


def zscores(values: pd.Series, window: int) -> tuple[pd.Series, pd.Series]:
    """(z, baseline mean) from the previous `window` readings; z is NaN where no valid baseline exists."""
    past = values.shift(1).rolling(window, min_periods=max(2, window // 2))
    mean, std = past.mean(), past.std()
    z = (values - mean) / std
    return z.where(std > STD_EPSILON), mean


def _baseline_text(ds: DatasetConfig) -> str:
    n = ds.zscore_window
    if ds.expected_interval is None:
        return f"its previous {n} readings"
    return f"its previous {n} readings (about {fmt_duration(ds.expected_interval * n)})"


# ---------------------------------------------------------------- methods


def _limit_runs(g: pd.DataFrame, spec: SensorSpec, ds: DatasetConfig, breaks: np.ndarray, out: DetectionOutput):
    values = g[spec.name]
    for direction, limit in (("high", spec.warn_high), ("low", spec.warn_low)):
        if limit is None:
            continue
        flags = (values > limit) if direction == "high" else (values < limit)
        for a, b in find_runs(flags.fillna(False).to_numpy(dtype=bool), breaks):
            seg = g.iloc[a : b + 1]
            seg_values = seg[spec.name]
            peak = float(seg_values.max() if direction == "high" else seg_values.min())
            start, end = seg["timestamp"].iloc[0], seg["timestamp"].iloc[-1]
            row_ids = list(seg["row_id"])
            word = "above" if direction == "high" else "below"
            n = b - a + 1
            if n < ds.min_consecutive:
                out.transients.append(
                    Transient(
                        machine_id=str(seg["machine_id"].iloc[0]),
                        sensor=spec.name,
                        start=start,
                        end=end,
                        row_ids=row_ids,
                        message=(
                            f"One-off {spec.label.lower()} reading of {fmt_value(peak)} {spec.unit} at {_ts(start)} "
                            f"({', '.join(row_ids)}), {word} the {fmt_value(limit)} {spec.unit} limit - ignored: a flag "
                            f"must last at least {ds.min_consecutive} consecutive readings."
                        ),
                    )
                )
                continue
            ratio = abs(peak - limit) / abs(limit) if limit != 0 else 1.0
            out.anomalies.append(
                Detected(
                    machine_id=str(seg["machine_id"].iloc[0]),
                    sensor=spec.name,
                    method="limit",
                    direction=direction,
                    start=start,
                    end=end,
                    peak=peak,
                    unit=spec.unit,
                    row_ids=row_ids,
                    magnitude_ratio=ratio,
                    limit=float(limit),
                    reason=(
                        f"{spec.label} {fmt_value(peak)} {spec.unit} {word} the {fmt_value(limit)} {spec.unit} limit "
                        f"for {fmt_duration(end - start)} ({n} readings)."
                    ),
                )
            )


def _zscore_runs(g: pd.DataFrame, spec: SensorSpec, ds: DatasetConfig, breaks: np.ndarray, out: DetectionOutput):
    values = g[spec.name]
    z, mean = zscores(values, ds.zscore_window)
    for direction in ("high", "low"):
        flags = (z >= ds.zscore_threshold) if direction == "high" else (z <= -ds.zscore_threshold)
        for a, b in find_runs(flags.fillna(False).to_numpy(dtype=bool), breaks):
            n = b - a + 1
            if n < ds.min_consecutive:
                continue
            seg = g.iloc[a : b + 1]
            seg_z = z.iloc[a : b + 1]
            at = int(np.nanargmax(seg_z.abs().to_numpy()))
            peak = float(seg[spec.name].iloc[at])
            z_peak = float(seg_z.iloc[at])
            base = float(mean.iloc[a + at])
            start, end = seg["timestamp"].iloc[0], seg["timestamp"].iloc[-1]
            verb = "rose to" if direction == "high" else "fell to"
            out.anomalies.append(
                Detected(
                    machine_id=str(seg["machine_id"].iloc[0]),
                    sensor=spec.name,
                    method="zscore",
                    direction=direction,
                    start=start,
                    end=end,
                    peak=peak,
                    unit=spec.unit,
                    row_ids=list(seg["row_id"]),
                    magnitude_ratio=abs(z_peak),
                    z_peak=z_peak,
                    baseline_mean=base,
                    reason=(
                        f"{spec.label} {verb} {fmt_value(peak)} {spec.unit} for {fmt_duration(end - start)} "
                        f"({n} readings); this machine's normal over {_baseline_text(ds)} is about "
                        f"{fmt_value(base)} {spec.unit} (z = {z_peak:+.1f})."
                    ),
                )
            )


def _drop_duplicate_zscore(anomalies: list[Detected]) -> list[Detected]:
    limits = [a for a in anomalies if a.method == "limit"]
    kept = []
    for a in anomalies:
        if a.method == "zscore" and any(
            lim.machine_id == a.machine_id and lim.sensor == a.sensor and lim.start <= a.start and a.end <= lim.end
            for lim in limits
        ):
            continue
        kept.append(a)
    return kept


# ---------------------------------------------------------------- entry point


def detect(readings: pd.DataFrame, ds: DatasetConfig) -> DetectionOutput:
    """Anomalies for every machine and detection sensor. `readings` is the validated frame."""
    out = DetectionOutput()
    if readings.empty:
        return out
    usable = readings
    if "skip_detection" in readings.columns:
        usable = readings.loc[~readings["skip_detection"].astype(bool)]
    sensors = [s for s in ds.detection_sensors if s in usable.columns]
    for _, g in usable.groupby("machine_id", sort=True):
        g = g.sort_values("timestamp", kind="stable").reset_index(drop=True)
        breaks = _gap_breaks(g["timestamp"])
        for name in sensors:
            spec = ds.sensors[name]
            g[name] = pd.to_numeric(g[name], errors="coerce").astype(float)
            if spec.warn_high is not None or spec.warn_low is not None:
                _limit_runs(g, spec, ds, breaks, out)
            _zscore_runs(g, spec, ds, breaks, out)
    out.anomalies = sorted(
        _drop_duplicate_zscore(out.anomalies), key=lambda a: (a.start, a.machine_id, a.sensor, a.method)
    )
    out.transients.sort(key=lambda t: (t.start, t.machine_id, t.sensor))
    return out
