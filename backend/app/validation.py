"""Step 1 - VALIDATE (CLAUDE.md section 5.1).

ERRORS stop the analysis: missing timestamp / machine_id column, no sensor columns of the dataset,
0 readable rows. File-level problems (not .csv, over 10 MB, not readable as CSV) raise UploadError,
which the API turns into HTTP 400 {"error": "..."}.

WARNINGS let the analysis continue: unreadable timestamps (row dropped), duplicate rows (dropped),
empty sensor cells (kept empty), unreadable or impossible values (set to empty, SENSOR ERROR - never an
anomaly), gaps longer than 2x the normal interval, MetroPT windows with raw_rows < 10 (skipped by
detection), unknown extra columns (ignored).

Every reading gets row_id = "R" + its original 1-based data-row number (R1 = first row after the header).
The "label" column is removed here, so nothing after validation can ever see it.
"""

import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backend.app.datasets import DatasetConfig, get_dataset, guess_dataset
from backend.app.schemas import ValidationReport
from backend.app.settings import get_settings

REQUIRED_READING_COLUMNS = ("timestamp", "machine_id")
REQUIRED_NOTE_COLUMNS = ("note_id", "machine_id", "timestamp", "text", "source")
NOTE_SOURCES = ("maintenance", "error_log", "inspection")
EVALUATION_ONLY_COLUMNS = ("label",)
MAX_EXAMPLES_PER_KIND = 20

# Time-zone suffix (Z, +05:30, -0100). Timestamps are wall-clock: the suffix is dropped, not converted.
_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")
_ISO_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$")
_TRUE = {"true", "1", "yes", "y", "t"}
_FALSE = {"false", "0", "no", "n", "f"}


class UploadError(ValueError):
    """A file-level problem. The message is plain English and safe to show to the user."""


@dataclass
class QualityEvent:
    """One data-quality finding, kept structured so later steps can show it on the machine page."""

    kind: str  # empty_cell | unreadable_value | sensor_error | gap | low_raw_rows
    machine_id: str
    message: str
    start: datetime | None = None
    end: datetime | None = None
    sensor: str | None = None
    row_ids: list[str] = field(default_factory=list)


@dataclass
class ValidationOutput:
    report: ValidationReport
    dataset: DatasetConfig
    # row_id, timestamp (datetime64), machine_id, <sensor> (float, NaN = empty), skip_detection (bool)
    readings: pd.DataFrame
    # note_id, machine_id, timestamp (datetime64), text, source, synthetic (bool)
    notes: pd.DataFrame
    quality_events: list[QualityEvent] = field(default_factory=list)


class _Warnings:
    """Collects warnings by kind and caps each kind at MAX_EXAMPLES_PER_KIND lines."""

    def __init__(self) -> None:
        self._groups: dict[str, list[str]] = {}

    def add(self, kind: str, message: str) -> None:
        self._groups.setdefault(kind, []).append(message)

    def count(self, kind: str) -> int:
        return len(self._groups.get(kind, []))

    def render(self) -> list[str]:
        out: list[str] = []
        for kind, messages in self._groups.items():
            out.extend(messages[:MAX_EXAMPLES_PER_KIND])
            extra = len(messages) - MAX_EXAMPLES_PER_KIND
            if extra > 0:
                out.append(f"... and {extra} more warnings of this type ({kind.replace('_', ' ')}).")
        return out


# ---------------------------------------------------------------- file level


def check_upload(filename: str | None, size_bytes: int, max_bytes: int | None = None) -> None:
    """Reject anything that is not a non-empty .csv file within the size limit."""
    limit = get_settings().max_upload_bytes if max_bytes is None else max_bytes
    name = (filename or "").strip()
    if not name.lower().endswith(".csv"):
        shown = name or "no file name"
        raise UploadError(f"Only .csv files are accepted (got '{shown}').")
    if size_bytes <= 0:
        raise UploadError(f"The file '{name}' is empty.")
    if size_bytes > limit:
        raise UploadError(
            f"The file '{name}' is too large ({size_bytes / 1024 / 1024:.1f} MB). "
            f"The limit is {limit / 1024 / 1024:.0f} MB."
        )


def read_csv_bytes(data: bytes, filename: str = "file") -> pd.DataFrame:
    """Parse uploaded CSV bytes. Every cell stays text; empty cells are ""."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UploadError(f"'{filename}' is not UTF-8 text. Save the file as CSV (UTF-8) and try again.") from None
    try:
        return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        raise UploadError(f"'{filename}' is empty or has no header row.") from None
    except pd.errors.ParserError:
        raise UploadError(f"'{filename}' could not be read as a comma-separated CSV file.") from None


def resolve_dataset(columns: list[str], dataset_hint: str | None = None) -> DatasetConfig:
    """Dataset from the hint if given, otherwise the one whose sensor columns overlap most."""
    if dataset_hint and dataset_hint.strip():
        try:
            return get_dataset(dataset_hint.strip())
        except KeyError as exc:
            raise UploadError(str(exc.args[0])) from None
    ds = guess_dataset(columns)
    if ds is None:
        raise UploadError(
            "No sensor columns of a known dataset were found. "
            "Expected e.g. vibration_mm_s, temperature_c, pressure_bar, sound_db, rpm."
        )
    return ds


# ---------------------------------------------------------------- helpers


def _as_text(df: pd.DataFrame) -> pd.DataFrame:
    """Strip column names and cell values; every cell becomes text, missing becomes ""."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    for col in out.columns:
        out[col] = out[col].astype("string").fillna("").str.strip().astype(object)
    return out


def parse_timestamps(values: pd.Series) -> pd.Series:
    """ISO 8601 text -> naive datetime64 (wall clock). Anything else -> NaT."""
    text = values.astype("string").fillna("").str.strip().str.replace(_TZ_SUFFIX, "", regex=True)
    iso_like = text.str.match(_ISO_LIKE).fillna(False).astype(bool)
    parsed = pd.to_datetime(text.where(iso_like, None), format="ISO8601", errors="coerce")
    return parsed.astype("datetime64[ns]")


def _ts(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%dT%H:%M:%S")


def _duration(td: timedelta) -> str:
    minutes = int(round(td.total_seconds() / 60))
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"
    return f"{mins} min"


def _num(value: float) -> str:
    return f"{value:g}"


def _empty_readings(sensor_cols: list[str]) -> pd.DataFrame:
    cols = ["row_id", "timestamp", "machine_id", *sensor_cols, "skip_detection"]
    return pd.DataFrame({c: pd.Series(dtype=object) for c in cols})


def _empty_notes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "note_id": pd.Series(dtype=object),
            "machine_id": pd.Series(dtype=object),
            "timestamp": pd.Series(dtype="datetime64[ns]"),
            "text": pd.Series(dtype=object),
            "source": pd.Series(dtype=object),
            "synthetic": pd.Series(dtype=bool),
        }
    )


# ---------------------------------------------------------------- readings


def validate_readings(
    raw: pd.DataFrame, ds: DatasetConfig
) -> tuple[ValidationReport, pd.DataFrame, list[QualityEvent]]:
    errors: list[str] = []
    warn = _Warnings()
    events: list[QualityEvent] = []

    df = _as_text(raw)
    rows_in = len(df)

    missing = [c for c in REQUIRED_READING_COLUMNS if c not in df.columns]
    if missing:
        errors.append(
            f"Required column missing: {', '.join(missing)}. "
            "The readings file needs a 'timestamp' and a 'machine_id' column."
        )
    sensor_cols = [c for c in ds.sensors if c in df.columns]
    detection_cols = [c for c in ds.detection_sensors if c in df.columns]
    if not detection_cols:
        errors.append(
            f"No sensor columns for dataset '{ds.name}' were found. "
            f"Expected at least one of: {', '.join(ds.detection_sensors)}."
        )
    if rows_in == 0:
        errors.append("The readings file has no data rows.")

    if errors:
        report = ValidationReport(
            ok=False, errors=errors, warnings=[], rows_in=rows_in, rows_kept=0,
            rows_dropped=rows_in, synthetic=ds.synthetic,
        )
        return report, _empty_readings(sensor_cols), events

    known = set(REQUIRED_READING_COLUMNS) | set(ds.sensors) | set(EVALUATION_ONLY_COLUMNS)
    unknown = [c for c in df.columns if c not in known]
    if unknown:
        warn.add("unknown_column", f"Ignored unknown columns: {', '.join(unknown)}.")
    absent = [c for c in ds.detection_sensors if c not in df.columns]
    if absent:
        warn.add("missing_sensor", f"Sensor columns not in the file (not analysed): {', '.join(absent)}.")

    # Keep only what the pipeline may use. "label" (evaluation only) is removed here.
    df = df[list(REQUIRED_READING_COLUMNS) + sensor_cols].copy()
    df.insert(0, "row_id", [f"R{i}" for i in range(1, rows_in + 1)])

    # Rows without a machine_id cannot be assigned to a machine.
    no_machine = df["machine_id"] == ""
    for rid in df.loc[no_machine, "row_id"]:
        warn.add("no_machine_id", f"Row {rid} has no machine_id: row dropped.")
    df = df.loc[~no_machine].copy()

    # Timestamps.
    df["timestamp_text"] = df["timestamp"]
    df["timestamp"] = parse_timestamps(df["timestamp_text"])
    bad_ts = df["timestamp"].isna()
    for rid, mid, text in df.loc[bad_ts, ["row_id", "machine_id", "timestamp_text"]].itertuples(index=False):
        shown = text if text else "(empty)"
        warn.add("bad_timestamp", f"Unreadable timestamp '{shown}' in row {rid} ({mid}): row dropped.")
    df = df.loc[~bad_ts].drop(columns=["timestamp_text"])

    # Exact duplicate rows (same machine, time and values).
    exact_dup = df.duplicated(subset=["machine_id", "timestamp", *sensor_cols], keep="first")
    for rid, mid, ts in df.loc[exact_dup, ["row_id", "machine_id", "timestamp"]].itertuples(index=False):
        warn.add("duplicate_row", f"Duplicate row {rid} ({mid} at {_ts(ts)}): row dropped.")
    df = df.loc[~exact_dup]

    # Same machine + time but different values: keep the first row.
    time_dup = df.duplicated(subset=["machine_id", "timestamp"], keep="first")
    for rid, mid, ts in df.loc[time_dup, ["row_id", "machine_id", "timestamp"]].itertuples(index=False):
        warn.add(
            "duplicate_time",
            f"Row {rid} ({mid} at {_ts(ts)}) repeats an earlier timestamp with different values: "
            "kept the first row, dropped this one.",
        )
    df = df.loc[~time_dup]

    df = df.sort_values(["machine_id", "timestamp"], kind="stable").reset_index(drop=True)

    # Sensor values: empty -> kept empty; text -> unreadable; outside valid range -> SENSOR ERROR.
    for col in sensor_cols:
        spec = ds.sensors[col]
        text = df[col].astype(str)
        values = pd.to_numeric(text.where(text != "", None), errors="coerce").astype(float)
        values = values.where(np.isfinite(values))

        empty = text == ""
        for rid, mid, ts in df.loc[empty, ["row_id", "machine_id", "timestamp"]].itertuples(index=False):
            msg = f"Empty cell: {mid} {col} at {_ts(ts)} ({rid}) - kept as empty."
            warn.add("empty_cell", msg)
            events.append(QualityEvent("empty_cell", mid, msg, ts, ts, col, [rid]))

        unreadable = (~empty) & values.isna()
        for rid, mid, ts, raw_value in df.loc[unreadable, ["row_id", "machine_id", "timestamp", col]].itertuples(
            index=False
        ):
            msg = f"Unreadable value '{raw_value}': {mid} {col} at {_ts(ts)} ({rid}) - set to empty."
            warn.add("unreadable_value", msg)
            events.append(QualityEvent("unreadable_value", mid, msg, ts, ts, col, [rid]))

        impossible = pd.Series(False, index=df.index)
        if spec.valid_min is not None:
            impossible |= values < spec.valid_min
        if spec.valid_max is not None:
            impossible |= values > spec.valid_max
        impossible &= values.notna()
        for rid, mid, ts, value in zip(
            df.loc[impossible, "row_id"], df.loc[impossible, "machine_id"],
            df.loc[impossible, "timestamp"], values[impossible],
        ):
            msg = (
                f"SENSOR ERROR: {mid} {col} = {_num(value)} at {_ts(ts)} ({rid}) is outside the valid range "
                f"({spec.valid_range_text()}) - set to empty, not treated as an anomaly."
            )
            warn.add("sensor_error", msg)
            events.append(QualityEvent("sensor_error", mid, msg, ts, ts, col, [rid]))
        df[col] = values.mask(impossible)

    # Gaps longer than 2x the machine's normal (median) interval.
    if ds.expected_interval is not None:
        for mid, group in df.groupby("machine_id", sort=False):
            times = group["timestamp"]
            diffs = times.diff()
            normal = diffs.median()
            if pd.isna(normal) or normal <= pd.Timedelta(0):
                normal = pd.Timedelta(ds.expected_interval)
            for pos in np.flatnonzero((diffs > 2 * normal).to_numpy()):
                prev_t, next_t = times.iloc[pos - 1], times.iloc[pos]
                rids = [group["row_id"].iloc[pos - 1], group["row_id"].iloc[pos]]
                msg = (
                    f"Data gap: {mid} has no readings between {_ts(prev_t)} and {_ts(next_t)} "
                    f"({_duration(next_t - prev_t)}; normal interval {_duration(normal)})."
                )
                warn.add("gap", msg)
                events.append(QualityEvent("gap", mid, msg, prev_t, next_t, None, rids))

    # MetroPT: too few raw readings in a 5-minute window -> skipped by detection.
    df["skip_detection"] = False
    if ds.min_raw_rows is not None and "raw_rows" in df.columns:
        low = (df["raw_rows"] < ds.min_raw_rows).fillna(False).astype(bool)
        df["skip_detection"] = low
        for rid, mid, ts, n in df.loc[low, ["row_id", "machine_id", "timestamp", "raw_rows"]].itertuples(
            index=False
        ):
            msg = (
                f"Window {mid} at {_ts(ts)} ({rid}) has only {_num(n)} raw readings "
                f"(< {ds.min_raw_rows}): skipped by detection."
            )
            warn.add("low_raw_rows", msg)
            events.append(QualityEvent("low_raw_rows", mid, msg, ts, ts, "raw_rows", [rid]))

    rows_kept = len(df)
    if rows_kept == 0:
        errors.append("No readable rows remain after validation (check the timestamp and machine_id values).")

    report = ValidationReport(
        ok=not errors,
        errors=errors,
        warnings=warn.render(),
        rows_in=rows_in,
        rows_kept=rows_kept,
        rows_dropped=rows_in - rows_kept,
        synthetic=ds.synthetic,
    )
    return report, df[["row_id", "timestamp", "machine_id", *sensor_cols, "skip_detection"]], events


# ---------------------------------------------------------------- notes


def _parse_bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    return None


def validate_notes(
    raw: pd.DataFrame | None, ds: DatasetConfig, machine_ids: set[str]
) -> tuple[pd.DataFrame, list[str]]:
    """Return (clean notes, warnings). Problems with notes never stop the analysis."""
    if raw is None:
        return _empty_notes(), []
    warn = _Warnings()
    df = _as_text(raw)

    missing = [c for c in REQUIRED_NOTE_COLUMNS if c not in df.columns]
    if missing:
        return _empty_notes(), [f"Notes file ignored: required column missing: {', '.join(missing)}."]

    known = set(REQUIRED_NOTE_COLUMNS) | {"synthetic"}
    unknown = [c for c in df.columns if c not in known]
    if unknown:
        warn.add("note_unknown_column", f"Notes: ignored unknown columns: {', '.join(unknown)}.")

    keep: list[dict] = []
    seen: set[str] = set()
    parsed_ts = parse_timestamps(df["timestamp"])
    has_synthetic = "synthetic" in df.columns
    for i, row in enumerate(df.to_dict("records")):
        line = f"notes row {i + 1}"
        note_id, mid, text = row["note_id"], row["machine_id"], row["text"]
        if not note_id or not mid or not text:
            warn.add("note_incomplete", f"Notes: {line} has an empty note_id, machine_id or text: note ignored.")
            continue
        if note_id in seen:
            warn.add("note_duplicate", f"Notes: duplicate note_id {note_id}: kept the first one.")
            continue
        ts = parsed_ts.iloc[i]
        if pd.isna(ts):
            warn.add("note_bad_timestamp", f"Notes: {note_id} has an unreadable timestamp '{row['timestamp']}': ignored.")
            continue
        source = row["source"].lower()
        if source not in NOTE_SOURCES:
            warn.add(
                "note_bad_source",
                f"Notes: {note_id} has source '{row['source']}' (allowed: {', '.join(NOTE_SOURCES)}): ignored.",
            )
            continue
        if mid not in machine_ids:
            warn.add("note_unknown_machine", f"Notes: {note_id} is for machine '{mid}', which has no readings: ignored.")
            continue
        synthetic = _parse_bool(row["synthetic"]) if has_synthetic else None
        if synthetic is None:
            if has_synthetic:
                warn.add(
                    "note_bad_synthetic",
                    f"Notes: {note_id} has synthetic='{row['synthetic']}' - using the dataset value "
                    f"({str(ds.synthetic).lower()}).",
                )
            synthetic = ds.synthetic
        seen.add(note_id)
        keep.append(
            {"note_id": note_id, "machine_id": mid, "timestamp": ts, "text": text, "source": source,
             "synthetic": synthetic}
        )

    if not keep:
        return _empty_notes(), warn.render()
    notes = pd.DataFrame(keep)
    notes["timestamp"] = notes["timestamp"].astype("datetime64[ns]")
    notes = notes.sort_values(["timestamp", "note_id"], kind="stable").reset_index(drop=True)
    return notes, warn.render()


# ---------------------------------------------------------------- entry point


def validate(readings_raw: pd.DataFrame, notes_raw: pd.DataFrame | None, ds: DatasetConfig) -> ValidationOutput:
    report, readings, events = validate_readings(readings_raw, ds)
    if not report.ok:
        return ValidationOutput(report, ds, readings, _empty_notes(), events)
    notes, note_warnings = validate_notes(notes_raw, ds, set(readings["machine_id"].unique()))
    report.warnings.extend(note_warnings)
    return ValidationOutput(report, ds, readings, notes, events)
