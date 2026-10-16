"""Pydantic models for the API contract (CLAUDE.md section 6 - FROZEN).

Shared between Member 1 and Member 2. Change only after agreeing with Member 3 (frontend).

Fields marked EXTENSION are additive (they have defaults), so a frontend built against the
frozen contract keeps working. They were agreed in STEP 1:
  - SensorInfo.kind              "analog" | "derived" | "quality" (raw_rows is quality, never charted as a sensor)
  - Anomaly.machine_id           listed in section 5.2
  - Anomaly.linked_notes         note_id + relation ("before" | "during" | "after") from section 5.3
  - MachineCase.context          data-quality warnings and ignored one-off spikes, with nearby notes,
                                 shown on the machine page as context - NOT evidence
  - Provenance.provider          also "amd_token_factory" (STEP 3: Member 2's AMD Token Factory client)
Timestamps are naive ISO 8601 wall-clock times (e.g. 2026-10-14T08:00:00), never with a time zone.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["HIGH", "MEDIUM", "LOW", "OK"]
DetectionMethod = Literal["limit", "zscore"]
NoteSource = Literal["maintenance", "error_log", "inspection"]
ProviderName = Literal["amd_token_factory", "amd_vllm", "gemini", "mock", "saved"]
SensorKind = Literal["analog", "derived", "quality"]
NoteRelation = Literal["before", "during", "after"]
ExplanationSection = Literal["findings", "possible_causes", "recommended_checks"]
ContextKind = Literal["empty_cell", "unreadable_value", "sensor_error", "gap", "low_raw_rows", "transient_ignored"]


# ---------------------------------------------------------------- generic


class ErrorResponse(BaseModel):
    error: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


# ---------------------------------------------------------------- datasets


class DatasetRef(BaseModel):
    id: str
    name: str
    synthetic: bool
    attribution: str


class DatasetInfo(DatasetRef):
    description: str


class SensorInfo(BaseModel):
    label: str
    unit: str
    warn_high: float | None = None
    warn_low: float | None = None
    kind: SensorKind = "analog"  # EXTENSION


# ---------------------------------------------------------------- step 1: validation


class ValidationReport(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rows_in: int = 0
    rows_kept: int = 0
    rows_dropped: int = 0
    synthetic: bool


class Reading(BaseModel):
    """One sensor reading row. Sensor columns are extra keys: <sensor>: number | null."""

    model_config = ConfigDict(extra="allow")

    row_id: str
    timestamp: datetime
    machine_id: str


class Note(BaseModel):
    note_id: str
    machine_id: str
    timestamp: datetime
    text: str
    source: NoteSource
    synthetic: bool


# ---------------------------------------------------------------- steps 2-4: detect, match, rank


class LinkedNote(BaseModel):  # EXTENSION
    note_id: str
    relation: NoteRelation


class Anomaly(BaseModel):
    anomaly_id: str
    machine_id: str  # EXTENSION
    sensor: str
    start: datetime
    end: datetime
    peak: float
    unit: str
    method: DetectionMethod
    reason: str
    row_ids: list[str]
    severity: float = Field(ge=0.0, le=1.0)
    linked_notes: list[LinkedNote] = Field(default_factory=list)  # EXTENSION


class ContextItem(BaseModel):  # EXTENSION - shown on the machine page, never used as evidence
    kind: ContextKind
    message: str
    start: datetime | None = None
    end: datetime | None = None
    sensor: str | None = None
    row_ids: list[str] = Field(default_factory=list)
    note_ids: list[str] = Field(default_factory=list)


class MachineCase(BaseModel):
    machine_id: str
    priority: Priority
    score: float
    anomalies: list[Anomaly] = Field(default_factory=list)
    notes: list[Note] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    context: list[ContextItem] = Field(default_factory=list)  # EXTENSION


class AnalysisResult(BaseModel):
    run_id: str
    dataset: DatasetRef
    validation: ValidationReport
    sensors: dict[str, SensorInfo]
    readings: list[Reading]
    notes: list[Note]
    cases: list[MachineCase]


# ---------------------------------------------------------------- steps 5-6: explain, verify (Member 2)


class Finding(BaseModel):
    statement: str
    evidence: list[str] = Field(default_factory=list)


class PossibleCause(BaseModel):
    cause: str
    evidence: list[str] = Field(default_factory=list)


class RecommendedCheck(BaseModel):
    action: str
    reason: str
    evidence: list[str] = Field(default_factory=list)


class AIExplanation(BaseModel):
    machine_id: str
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    possible_causes: list[PossibleCause] = Field(default_factory=list)
    recommended_checks: list[RecommendedCheck] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    uncertainty: str = ""


class Provenance(BaseModel):
    provider: ProviderName
    model: str
    hardware_label: str
    latency_ms: float | None = None
    created_at: datetime
    cached: bool = False


class UnsupportedItem(BaseModel):
    section: ExplanationSection
    index: int


class InspectionReport(BaseModel):
    machine_id: str
    explanation: AIExplanation | None = None
    unsupported: list[UnsupportedItem] = Field(default_factory=list)
    grounding_rate: float | None = None
    provenance: Provenance | None = None
    error: str | None = None
    fallback_summary: str | None = None


class LLMStatus(BaseModel):
    provider: str
    model: str
    hardware_label: str
    reachable: bool
    last_latency_ms: float | None = None
    error: str | None = None
