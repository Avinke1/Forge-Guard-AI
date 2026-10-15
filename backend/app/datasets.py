"""Dataset registry: id, name, synthetic flag, attribution, files and sensor configuration.

The JSON files in config/ are read-only (they are covered by docs/SHA256SUMS.txt). Anything they
do not contain is filled in HERE, in code, and is labelled PROPOSED:
  - display labels and display units for MetroPT-3 sensors (config only has "unit" and "kind")
  - warn_high / warn_low = None for MetroPT-3 (no fixed limits: compare with the machine's own past)
  - valid_min / valid_max = physically impossible values -> SENSOR ERROR in validation, never an anomaly
  - kind for the synthetic fleet (all "analog")
  - the AI4I sensor config (evaluation only, not listed by the API)
"""

import json
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

import pandas as pd

from backend.app.schemas import DatasetInfo, DatasetRef, SensorInfo
from backend.app.settings import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "config"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Display units for units written as words in config/metropt3_sensors.json.
_DISPLAY_UNITS = {"degC": "°C", "percent": "%"}


@dataclass(frozen=True)
class SensorSpec:
    name: str
    label: str
    unit: str
    kind: str = "analog"  # analog | derived | quality
    warn_high: float | None = None
    warn_low: float | None = None
    valid_min: float | None = None  # below -> SENSOR ERROR (set to empty)
    valid_max: float | None = None  # above -> SENSOR ERROR (set to empty)

    def info(self) -> SensorInfo:
        return SensorInfo(
            label=self.label,
            unit=self.unit,
            warn_high=self.warn_high,
            warn_low=self.warn_low,
            kind=self.kind,  # type: ignore[arg-type]
        )

    def valid_range_text(self) -> str:
        if self.valid_min is not None and self.valid_max is not None:
            return f"{_fmt(self.valid_min)} to {_fmt(self.valid_max)} {self.unit}"
        if self.valid_min is not None:
            return f">= {_fmt(self.valid_min)} {self.unit}"
        if self.valid_max is not None:
            return f"<= {_fmt(self.valid_max)} {self.unit}"
        return "any value"


@dataclass(frozen=True)
class DatasetConfig:
    id: str
    name: str
    synthetic: bool
    attribution: str
    description: str
    readings_path: Path
    notes_path: Path | None
    sensors: dict[str, SensorSpec]
    listed: bool = True  # shown by GET /api/datasets
    expected_interval: timedelta | None = None  # None -> no gap check (e.g. AI4I artificial timestamps)
    min_raw_rows: int | None = None  # windows with raw_rows below this are skipped by detection
    zscore_window: int = 32  # START VALUE, tuned in STEP 4 with scripts/evaluate.py
    zscore_threshold: float = 3.0
    min_consecutive: int = 2  # transient rule
    full_readings_path: Path | None = None  # evaluation only (MetroPT-3 Feb-Sep 2020)
    extra_paths: dict[str, Path] = field(default_factory=dict)

    @property
    def detection_sensors(self) -> list[str]:
        """Sensors that detection may use (never quality columns such as raw_rows)."""
        return [n for n, s in self.sensors.items() if s.kind != "quality"]

    @property
    def quality_columns(self) -> list[str]:
        return [n for n, s in self.sensors.items() if s.kind == "quality"]

    def ref(self) -> DatasetRef:
        return DatasetRef(id=self.id, name=self.name, synthetic=self.synthetic, attribution=self.attribution)

    def info(self) -> DatasetInfo:
        return DatasetInfo(
            id=self.id,
            name=self.name,
            synthetic=self.synthetic,
            attribution=self.attribution,
            description=self.description,
        )

    def sensor_infos(self) -> dict[str, SensorInfo]:
        return {name: spec.info() for name, spec in self.sensors.items()}


def _fmt(value: float) -> str:
    return f"{value:g}"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _num_or_none(value) -> float | None:
    return None if value is None else float(value)


# ---------------------------------------------------------------- synthetic fleet

# PROPOSED valid ranges: these quantities cannot be negative. Temperature has no lower bound.
_SYNTHETIC_VALID_MIN = {"vibration_mm_s": 0.0, "pressure_bar": 0.0, "sound_db": 0.0, "rpm": 0.0}


def _synthetic_fleet() -> DatasetConfig:
    cfg = _load_json(CONFIG_DIR / "sensors.json")
    sensors = {
        name: SensorSpec(
            name=name,
            label=s["label"],
            unit=s["unit"],
            kind=s.get("kind", "analog"),
            warn_high=_num_or_none(s.get("warn_high")),
            warn_low=_num_or_none(s.get("warn_low")),
            valid_min=_SYNTHETIC_VALID_MIN.get(name),
        )
        for name, s in cfg["sensors"].items()
    }
    base = PROCESSED_DIR / "synthetic_fleet"
    return DatasetConfig(
        id="synthetic_fleet",
        name="Synthetic factory fleet (6 machines)",
        synthetic=True,
        attribution="SYNTHETIC demo data - not real plant measurements",
        description=(
            "Six synthetic machines (2 forging presses, 2 hydraulic pumps, 2 drive shafts), one reading "
            "every 15 minutes, 14-16 Oct 2026, with maintenance notes. Limits are illustrative, not calibrated."
        ),
        readings_path=base / "readings.csv",
        notes_path=base / "notes.csv",
        sensors=sensors,
        expected_interval=timedelta(minutes=15),
        zscore_window=32,
        extra_paths={"machines": base / "machines.csv"},
    )


# ---------------------------------------------------------------- MetroPT-3

# PROPOSED display labels (names from docs/DATA_DICTIONARY.md section 3).
_METROPT_LABELS = {
    "tp2_bar": "TP2 compressor pressure",
    "tp3_bar": "TP3 pneumatic panel pressure",
    "h1_bar": "H1 pressure",
    "dv_pressure_bar": "Air dryer discharge pressure (DV)",
    "reservoirs_bar": "Reservoirs pressure",
    "oil_temperature_c": "Oil temperature",
    "motor_current_a": "Motor current",
    "motor_current_max_a": "Motor current (max in window)",
    "compressor_loading_pct": "Compressor loading",
    "compressor_loading_1h_pct": "Compressor loading (1 h average)",
    "low_pressure_alarm_pct": "Low pressure alarm (share of window)",
    "raw_rows": "Raw readings in window",
}

# PROPOSED valid ranges. Small negative pressures (~ -0.03 bar, measured min -0.031) are sensor zero
# noise and normal, so pressures only become a SENSOR ERROR below -1 bar.
_PCT = (0.0, 100.0)
_METROPT_VALID = {
    "tp2_bar": (-1.0, None),
    "tp3_bar": (-1.0, None),
    "h1_bar": (-1.0, None),
    "dv_pressure_bar": (-1.0, None),
    "reservoirs_bar": (-1.0, None),
    "motor_current_a": (0.0, None),
    "motor_current_max_a": (0.0, None),
    "compressor_loading_pct": _PCT,
    "compressor_loading_1h_pct": _PCT,
    "low_pressure_alarm_pct": _PCT,
    "raw_rows": (0.0, None),
}


def _metropt3() -> DatasetConfig:
    cfg = _load_json(CONFIG_DIR / "metropt3_sensors.json")
    sensors: dict[str, SensorSpec] = {}
    for name, s in cfg["sensors"].items():
        unit = s.get("unit", "")
        vmin, vmax = _METROPT_VALID.get(name, (None, None))
        sensors[name] = SensorSpec(
            name=name,
            label=s.get("label") or _METROPT_LABELS.get(name, name),
            unit=_DISPLAY_UNITS.get(unit, unit),
            kind=s.get("kind", "analog"),
            warn_high=_num_or_none(s.get("warn_high")),
            warn_low=_num_or_none(s.get("warn_low")),
            valid_min=vmin,
            valid_max=vmax,
        )
    base = PROCESSED_DIR / "metropt3"
    return DatasetConfig(
        id="metropt3",
        name="MetroPT-3 air compressor APU-01 (real data)",
        synthetic=False,
        attribution="Real data: MetroPT-3 dataset (UCI Machine Learning Repository, CC BY 4.0)",
        description=(
            "Real sensor data from one metro-train air compressor, 5-minute averages, demo slice "
            "8-16 Jul 2020 including a reported air leak. No fixed limits: each sensor is compared "
            "with this machine's own recent normal pattern."
        ),
        readings_path=base / "readings.csv",
        notes_path=base / "notes.csv",
        sensors=sensors,
        expected_interval=timedelta(minutes=5),
        min_raw_rows=10,
        zscore_window=288,
        full_readings_path=base / "readings_full_5min.csv",
        extra_paths={"fault_events": base / "fault_events.csv"},  # ANSWER KEY - evaluation only
    )


# ---------------------------------------------------------------- AI4I (evaluation only)


def _ai4i() -> DatasetConfig:
    specs = [
        ("air_temperature_c", "Air temperature", "°C", None),
        ("process_temperature_c", "Process temperature", "°C", None),
        ("rpm", "Rotational speed", "rpm", 0.0),
        ("torque_nm", "Torque", "Nm", 0.0),
        ("tool_wear_min", "Tool wear", "min", 0.0),
    ]
    sensors = {n: SensorSpec(name=n, label=lbl, unit=u, valid_min=vmin) for n, lbl, u, vmin in specs}
    base = PROCESSED_DIR / "ai4i"
    return DatasetConfig(
        id="ai4i",
        name="AI4I 2020 (synthetic, evaluation only)",
        synthetic=True,
        attribution="SYNTHETIC: AI4I 2020 Predictive Maintenance Dataset (UCI Machine Learning Repository, CC BY 4.0)",
        description="Synthetic independent samples; timestamps and machine IDs are artificial. Evaluation only.",
        readings_path=base / "readings.csv",
        notes_path=None,
        sensors=sensors,
        listed=False,
        expected_interval=None,
        extra_paths={"meta": base / "meta.csv"},  # explanation-only columns, never for scoring
    )


# ---------------------------------------------------------------- registry API

_REGISTRY: dict[str, DatasetConfig] | None = None


def registry() -> dict[str, DatasetConfig]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = {d.id: d for d in (_synthetic_fleet(), _metropt3(), _ai4i())}
    return _REGISTRY


def get_dataset(dataset_id: str) -> DatasetConfig:
    try:
        return registry()[dataset_id]
    except KeyError:
        known = ", ".join(d.id for d in listed_datasets())
        raise KeyError(f"Unknown dataset '{dataset_id}'. Known datasets: {known}.") from None


def listed_datasets() -> list[DatasetConfig]:
    return [d for d in registry().values() if d.listed]


def guess_dataset(columns: list[str]) -> DatasetConfig | None:
    """Pick the dataset whose detection sensors overlap most with the given columns (registry order breaks ties)."""
    cols = {c.strip() for c in columns}
    best, best_overlap = None, 0
    for ds in registry().values():
        overlap = len(cols & set(ds.detection_sensors))
        if overlap > best_overlap:
            best, best_overlap = ds, overlap
    return best


def read_csv_as_text(path: Path) -> pd.DataFrame:
    """Read a CSV keeping every cell as text, empty cells as "" (validation does all parsing)."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def load_demo_frames(dataset_id: str) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Raw (unvalidated) readings and notes for a demo dataset."""
    ds = get_dataset(dataset_id)
    readings = read_csv_as_text(ds.readings_path)
    notes = read_csv_as_text(ds.notes_path) if ds.notes_path is not None else None
    return readings, notes
