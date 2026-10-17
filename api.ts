/**
 * ALL backend calls live in this file.
 * Mock mode (VITE_USE_MOCK not "false"): returns deterministic mock data from src/mock/.
 * Live mode: talks to the ForgeGuard FastAPI backend (contract: docs/API.md in the repo root).
 * The frontend never analyses data and never calls an AI service itself.
 */
import {
  Machine,
  SensorReading,
  MachineReport,
  RunHistoryItem,
  LlmStatus,
  ValidationReport,
  EvidenceDetail,
  SensorConfig,
  AnalyzeResult,
  PriorityLevel,
} from './types';
import {
  MOCK_MACHINES,
  MOCK_REPORTS,
  MOCK_RUNS,
  MOCK_LLM_STATUS,
  MOCK_ANOMALIES,
  MOCK_NOTES,
  generateMachineReadings,
  FLEET_SENSORS,
  METRO_SENSORS,
  METRO_MACHINES,
  METRO_NOTES,
  METRO_ANOMALIES,
  METRO_REPORT,
  generateMetroReadings,
} from './mock/data';

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export type DatasetId = 'synthetic_fleet' | 'metropt3';

const delay = (ms = 300) => new Promise((resolve) => setTimeout(resolve, ms));

/* ------------------------------------------------------------------ */
/* Current run (kept in sessionStorage so a page refresh keeps it)     */
/* ------------------------------------------------------------------ */
const RUN_KEY = 'forgeguard_current_run';
interface CurrentRun {
  runId: string;
  datasetId: string;
  datasetName: string;
  real: boolean;
}
let runCache: ApiAnalysisResult | null = null;

function saveCurrentRun(run: CurrentRun | null) {
  try {
    if (run) sessionStorage.setItem(RUN_KEY, JSON.stringify(run));
    else sessionStorage.removeItem(RUN_KEY);
  } catch {
    /* storage may be blocked - ignore */
  }
}

export function getCurrentRun(): CurrentRun | null {
  try {
    const raw = sessionStorage.getItem(RUN_KEY);
    if (raw) return JSON.parse(raw) as CurrentRun;
  } catch {
    /* ignore */
  }
  // Mock mode always has the synthetic fleet available
  return USE_MOCK
    ? { runId: 'MOCK-RUN-2', datasetId: 'synthetic_fleet', datasetName: 'Synthetic fleet', real: false }
    : null;
}

function mockDataset(): DatasetId {
  return getCurrentRun()?.datasetId === 'metropt3' ? 'metropt3' : 'synthetic_fleet';
}

/* ------------------------------------------------------------------ */
/* HTTP helpers                                                        */
/* ------------------------------------------------------------------ */
async function request<T>(path: string, init?: RequestInit, timeoutMs = 30000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE_URL}${path}`, { ...init, signal: ctrl.signal });
    if (!res.ok) {
      let msg = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.error) msg = body.error;
        else if (body?.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
      } catch {
        /* no JSON body */
      }
      throw new Error(msg);
    }
    return (await res.json()) as T;
  } catch (e: any) {
    if (e?.name === 'AbortError') throw new Error('The backend did not answer in time.');
    if (e instanceof TypeError) throw new Error('Backend not reachable. Check VITE_API_BASE_URL and that the backend is running.');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

/* ------------------------------------------------------------------ */
/* Backend JSON (docs/API.md, backend/app/schemas.py) - raw shapes     */
/* ------------------------------------------------------------------ */
interface ApiSensor {
  label: string;
  unit: string;
  warn_high: number | null;
  warn_low: number | null;
  kind?: 'analog' | 'derived' | 'quality';
}

interface ApiNote {
  note_id: string;
  machine_id: string;
  timestamp: string;
  text: string;
  source: 'maintenance' | 'error_log' | 'inspection';
  synthetic: boolean;
}

interface ApiAnomaly {
  anomaly_id: string;
  machine_id: string;
  sensor: string;
  start: string;
  end: string;
  peak: number;
  unit: string;
  method: 'limit' | 'zscore';
  reason: string;
  row_ids: string[];
  severity: number;
  linked_notes: { note_id: string; relation: 'before' | 'during' | 'after' }[];
}

interface ApiMachineCase {
  machine_id: string;
  priority: PriorityLevel;
  score: number;
  anomalies: ApiAnomaly[];
  notes: ApiNote[];
  evidence_ids: string[];
  context: { kind: string; message: string; start: string | null; end: string | null; sensor: string | null }[];
}

interface ApiAnalysisResult {
  run_id: string;
  dataset: { id: string; name: string; synthetic: boolean; attribution: string };
  validation: {
    ok: boolean;
    errors: string[];
    warnings: string[];
    rows_in: number;
    rows_kept: number;
    rows_dropped: number;
    synthetic: boolean;
  };
  sensors: Record<string, ApiSensor>;
  readings: ({ row_id: string; timestamp: string; machine_id: string } & Record<string, number | string | null>)[];
  notes: ApiNote[];
  cases: ApiMachineCase[]; // already in queue order - never re-sorted here
}

type ApiSection = 'findings' | 'possible_causes' | 'recommended_checks';

interface ApiInspectionReport {
  machine_id: string;
  explanation: {
    machine_id: string;
    summary: string;
    findings: { statement: string; evidence: string[] }[];
    possible_causes: { cause: string; evidence: string[] }[];
    recommended_checks: { action: string; reason: string; evidence: string[] }[];
    missing_information: string[];
    uncertainty: string;
  } | null;
  unsupported: { section: ApiSection; index: number }[];
  grounding_rate: number | null;
  provenance: {
    provider: 'amd_token_factory' | 'gemini' | 'mock' | 'saved';
    model: string;
    hardware_label: string;
    latency_ms: number | null;
    created_at: string;
    cached: boolean;
  } | null;
  error: string | null;
  fallback_summary: string | null;
}

interface ApiRunSummary {
  run_id: string;
  created_at: string;
  dataset_id: string;
  dataset_name: string;
  real: boolean;
  machines: number;
  counts: Record<PriorityLevel, number>;
}

interface ApiLlmStatus {
  provider: string;
  model: string;
  hardware_label: string;
  reachable: boolean;
  last_latency_ms: number | null;
  error: string | null;
}

/* ------------------------------------------------------------------ */
/* Mapping backend JSON -> UI types (display only, no analysis)        */
/* ------------------------------------------------------------------ */
const pad = (n: number) => n.toString().padStart(2, '0');
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-10-16T08:00:00" -> "16 Oct 08:00" (string parsing, no timezone shift) */
export function formatTs(ts: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(ts || '');
  if (!m) return ts;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[4]}:${m[5]}`;
}
const shortTs = (ts: string) => (ts || '').replace('T', ' ').slice(0, 16);

const METHOD_TEXT: Record<ApiAnomaly['method'], string> = {
  limit: 'Outside the configured limit',
  zscore: "Unusual for this machine's normal pattern",
};

const SOURCE_TEXT: Record<ApiNote['source'], string> = {
  maintenance: 'Maintenance note',
  error_log: 'Error log',
  inspection: 'Inspection note',
};

function limitText(sensor: ApiSensor | undefined): string {
  if (!sensor) return '-';
  const parts: string[] = [];
  if (sensor.warn_low != null) parts.push(`min ${sensor.warn_low}`);
  if (sensor.warn_high != null) parts.push(`max ${sensor.warn_high}`);
  return parts.length ? `${parts.join(' / ')} ${sensor.unit}` : "No fixed limit - compared with this machine's normal pattern";
}

function readingsOf(run: ApiAnalysisResult, machineId: string) {
  return run.readings.filter((r) => r.machine_id === machineId);
}

function toMachine(run: ApiAnalysisResult, c: ApiMachineCase, index: number): Machine {
  const readings = readingsOf(run, c.machine_id);
  const last = readings.length ? readings[readings.length - 1].timestamp : '';
  // note_id -> "during A-2" etc. (from anomaly.linked_notes; only these notes are evidence)
  const links: Record<string, string[]> = {};
  for (const a of c.anomalies) {
    for (const ln of a.linked_notes || []) (links[ln.note_id] ||= []).push(`${ln.relation} ${a.anomaly_id}`);
  }
  const evidence = new Set(c.evidence_ids);
  return {
    id: c.machine_id,
    name: c.machine_id,
    type: run.dataset.name,
    location: run.dataset.attribution,
    priority: c.priority,
    summary: c.anomalies[0]?.reason || c.context[0]?.message || 'No unusual readings were found.',
    rank: index + 1,
    sensorsInvolved: [...new Set(c.anomalies.map((a) => a.sensor))],
    anomalies: c.anomalies.map((a) => ({
      id: a.anomaly_id,
      machine_id: a.machine_id,
      sensor: a.sensor,
      sensorLabel: run.sensors[a.sensor]?.label || a.sensor,
      value: `${a.peak} ${a.unit}`.trim(),
      limit: limitText(run.sensors[a.sensor]),
      timestamp: `${shortTs(a.start)} - ${shortTs(a.end).slice(11)}`,
      description: `${METHOD_TEXT[a.method] || a.method}: ${a.reason}${
        a.linked_notes?.length ? ` Linked notes: ${a.linked_notes.map((n) => `${n.note_id} (${n.relation})`).join(', ')}.` : ''
      }`,
      severity: c.priority,
    })),
    notes: c.notes.map((n) => ({
      id: n.note_id,
      machine_id: n.machine_id,
      timestamp: shortTs(n.timestamp),
      author: links[n.note_id]
        ? `${SOURCE_TEXT[n.source] || n.source} (${links[n.note_id].join(', ')})`
        : `${SOURCE_TEXT[n.source] || n.source} (background, not linked to an unusual reading)`,
      content: n.text,
      tags: evidence.has(n.note_id) ? (links[n.note_id] || ['evidence']) : ['background'],
    })),
    // MachineCase.context = data-quality warnings / ignored spikes: context only, never evidence
    warnings: c.context.map((x) => x.message),
    readingsCount: readings.length,
    lastReading: shortTs(last),
  };
}

function toReadings(run: ApiAnalysisResult, machineId: string): SensorReading[] {
  const c = run.cases.find((x) => x.machine_id === machineId);
  const hitsByRow: Record<string, ApiAnomaly[]> = {};
  for (const a of c?.anomalies || []) for (const id of a.row_ids) (hitsByRow[id] ||= []).push(a);
  return readingsOf(run, machineId).map((r) => {
    const hits = hitsByRow[r.row_id] || [];
    return {
      ...r,
      id: r.row_id,
      machine_id: machineId,
      timestamp: shortTs(r.timestamp),
      displayTime: formatTs(r.timestamp),
      is_anomaly: hits.length > 0,
      anomaly_id: hits[0]?.anomaly_id,
      anomaly_sensors: hits.map((a) => a.sensor),
    } as SensorReading;
  });
}

function toValidation(run: ApiAnalysisResult): ValidationReport {
  const v = run.validation;
  return {
    totalRows: v.rows_in,
    keptRows: v.rows_kept,
    droppedRows: v.rows_dropped,
    details: [...(v.errors || []).map((e) => `Error: ${e}`), ...(v.warnings || [])],
  };
}

const NOT_SUPPORTED = ' [not supported by evidence]';
const cite = (ids: string[]) => (ids.length ? ` (evidence: ${ids.join(', ')})` : '');

/** Badge text from provenance.provider ONLY (docs/API.md "UI rules") */
function headerFor(p: NonNullable<ApiInspectionReport['provenance']>): string {
  const base = p.provider === 'mock' ? 'MOCK - not AI output' : p.provider === 'saved' ? 'saved' : 'AI explanation';
  return p.cached ? `${base} (cached)` : base;
}

function toReport(machineId: string, r: ApiInspectionReport): MachineReport {
  const ex = r.explanation;
  const p = r.provenance;
  const bad = (section: ApiSection, i: number) => (r.unsupported || []).some((u) => u.section === section && u.index === i);
  if (!ex || !p) {
    // No AI explanation: show error + fallback_summary in the page's error alert, never an AI box
    throw new Error([r.error || 'No AI explanation.', r.fallback_summary].filter(Boolean).join(' '));
  }
  return {
    machine_id: r.machine_id || machineId,
    header: headerFor(p),
    mock: p.provider === 'mock',
    provider: p.provider,
    model: p.model, // shown exactly as returned
    hardware: p.hardware_label,
    latencyMs: p.latency_ms,
    summary: ex.summary || '',
    findings: ex.findings.map((f, i) => ({
      id: `F-${i + 1}`,
      title: `Finding ${i + 1}`,
      detail: f.statement,
      evidence: f.evidence || [],
      unsupported: bad('findings', i),
    })),
    possibleCauses: ex.possible_causes.map(
      (c, i) => `${c.cause}${cite(c.evidence || [])}${bad('possible_causes', i) ? NOT_SUPPORTED : ''}`
    ),
    recommendedChecks: ex.recommended_checks.map(
      (c, i) => `${c.action}${c.reason ? ` - ${c.reason}` : ''}${cite(c.evidence || [])}${
        bad('recommended_checks', i) ? NOT_SUPPORTED : ''
      }`
    ),
    missingInformation: ex.missing_information || [],
    uncertainty: ex.uncertainty || '',
    failed: !!r.error,
    errorMessage: r.error || undefined,
    ruleBasedFallback: false,
    ruleBasedSummary: undefined,
  };
}

async function liveRun(): Promise<ApiAnalysisResult | null> {
  const cur = getCurrentRun();
  if (!cur) return null;
  if (runCache && runCache.run_id === cur.runId) return runCache;
  runCache = await request<ApiAnalysisResult>(`/api/runs/${encodeURIComponent(cur.runId)}`);
  return runCache;
}

function rememberRun(run: ApiAnalysisResult): AnalyzeResult {
  runCache = run;
  const cur = {
    runId: run.run_id,
    datasetId: run.dataset.id,
    datasetName: run.dataset.name,
    real: !run.dataset.synthetic,
  };
  saveCurrentRun(cur);
  return { runId: cur.runId, datasetId: cur.datasetId, datasetName: cur.datasetName, validation: toValidation(run) };
}

/* ------------------------------------------------------------------ */
/* Public API used by the pages                                        */
/* ------------------------------------------------------------------ */
const MOCK_VALIDATION: Record<DatasetId, ValidationReport> = {
  synthetic_fleet: {
    totalRows: 1728,
    keptRows: 1724,
    droppedRows: 4,
    details: ['DS-02: 3 empty cells', 'DS-02: rpm -50 at 15 Oct 20:00 dropped as impossible', 'DS-02: gap 15 Oct 03:00-03:45'],
  },
  metropt3: { totalRows: 145, keptRows: 145, droppedRows: 0, details: ['MetroPT-3 demo window 15 Jul 2020 10:00-22:00'] },
};

/** Demo buttons: POST /api/analyze/demo/{dataset_id} */
export async function runDemo(datasetId: DatasetId): Promise<AnalyzeResult> {
  if (USE_MOCK) {
    await delay(500);
    const name = datasetId === 'metropt3' ? 'MetroPT-3' : 'Synthetic fleet';
    const cur = { runId: datasetId === 'metropt3' ? 'MOCK-RUN-1' : 'MOCK-RUN-2', datasetId, datasetName: name, real: datasetId === 'metropt3' };
    saveCurrentRun(cur);
    return { runId: cur.runId, datasetId, datasetName: name, validation: MOCK_VALIDATION[datasetId] };
  }
  const run = await request<ApiAnalysisResult>(`/api/analyze/demo/${datasetId}`, { method: 'POST' }, 60000);
  return rememberRun(run);
}

/** Upload: POST /api/analyze (multipart: readings, notes?) */
export async function uploadReadings(readingsFile: File, notesFile?: File): Promise<AnalyzeResult> {
  if (USE_MOCK) {
    await delay(600);
    const cur = { runId: 'MOCK-RUN-2', datasetId: 'synthetic_fleet', datasetName: 'Synthetic fleet', real: false };
    saveCurrentRun(cur);
    return {
      ...cur,
      validation: {
        ...MOCK_VALIDATION.synthetic_fleet,
        details: [`Mock mode: ${readingsFile.name}${notesFile ? ' + ' + notesFile.name : ''} not sent to a backend`, ...MOCK_VALIDATION.synthetic_fleet.details],
      },
    };
  }
  const form = new FormData();
  form.append('readings', readingsFile);
  if (notesFile) form.append('notes', notesFile);
  const run = await request<ApiAnalysisResult>('/api/analyze', { method: 'POST', body: form }, 60000);
  return rememberRun(run);
}

export async function getMachines(): Promise<Machine[]> {
  if (USE_MOCK) {
    await delay(150);
    return mockDataset() === 'metropt3' ? [...METRO_MACHINES] : [...MOCK_MACHINES];
  }
  const run = await liveRun();
  if (!run) return [];
  return run.cases.map((c, i) => toMachine(run, c, i)); // backend order = queue order
}

export async function getMachineById(id: string): Promise<Machine | null> {
  const all = await getMachines();
  return all.find((m) => m.id.toUpperCase() === id.toUpperCase()) || null;
}

export async function getMachineReadings(id: string): Promise<SensorReading[]> {
  if (USE_MOCK) {
    await delay(150);
    return mockDataset() === 'metropt3' ? generateMetroReadings() : generateMachineReadings(id.toUpperCase());
  }
  const run = await liveRun();
  return run ? toReadings(run, id) : [];
}

/** Sensor list + limits for the charts (from the backend, never typed in for live data) */
export async function getSensors(): Promise<SensorConfig[]> {
  if (USE_MOCK) return mockDataset() === 'metropt3' ? METRO_SENSORS : FLEET_SENSORS;
  const run = await liveRun();
  if (!run) return [];
  // kind "quality" (MetroPT raw_rows) is a data-quality count, not a sensor - never charted
  return Object.entries(run.sensors)
    .filter(([, s]) => s.kind !== 'quality')
    .map(([key, s]) => ({ key, label: s.label, unit: s.unit, warn_high: s.warn_high, warn_low: s.warn_low }));
}

/**
 * "Generate AI explanation": POST /api/runs/{run_id}/explain/{machine_id}
 * Timeout 120000 ms (120 s): one real AMD explanation takes about 25 s (seen 12-36 s, recently 35-52 s),
 * and when the AI reply is invalid (bad JSON, empty findings) the backend makes ONE repair call, so a
 * slow pair of calls can approach 100 s. docs/API.md asks for at least 90 s; 120 s adds headroom so we
 * never abort a request the backend is still finishing (which would waste the team's shared AMD limit).
 */
const EXPLAIN_TIMEOUT_MS = 120000;

export async function explainMachine(id: string): Promise<MachineReport> {
  if (USE_MOCK) {
    await delay(900);
    if (mockDataset() === 'metropt3') return METRO_REPORT;
    const report = MOCK_REPORTS[id.toUpperCase()];
    if (report) return report;
    return {
      machine_id: id,
      header: 'MOCK - not AI output',
      mock: true,
      summary: 'No mock report for this machine.',
      findings: [],
      possibleCauses: [],
      recommendedChecks: [],
      missingInformation: [],
      uncertainty: '-',
    };
  }
  const cur = getCurrentRun();
  if (!cur) throw new Error('No analysis run yet. Run a demo or upload data first.');
  const r = await request<ApiInspectionReport>(
    `/api/runs/${encodeURIComponent(cur.runId)}/explain/${encodeURIComponent(id)}`,
    { method: 'POST' },
    EXPLAIN_TIMEOUT_MS
  );
  return toReport(id, r);
}

/** Evidence drawer: looks the ID up in the current run's data (no analysis) */
export async function getEvidenceDetail(machineId: string, evidenceId: string): Promise<EvidenceDetail> {
  const cleanId = evidenceId.trim();
  const unsupported: EvidenceDetail = {
    id: cleanId,
    type: 'unsupported',
    title: `Evidence ${cleanId}`,
    subtitle: 'Not found in this analysis - this claim is unsupported',
    isUnsupported: true,
    data: {},
  };

  const [machine, readings, sensors] = await Promise.all([
    getMachineById(machineId),
    getMachineReadings(machineId),
    getSensors(),
  ]);
  const anomalies = machine?.anomalies || [];
  const notes = machine?.notes || [];
  const lc = cleanId.toLowerCase();

  // In mock mode notes/anomalies can be looked up across the whole mock fleet
  const anomalyPool = USE_MOCK ? (mockDataset() === 'metropt3' ? METRO_ANOMALIES : MOCK_ANOMALIES) : anomalies;
  const notePool = USE_MOCK ? (mockDataset() === 'metropt3' ? METRO_NOTES : MOCK_NOTES) : notes;

  const anomaly = anomalyPool.find((a) => a.id.toLowerCase() === lc && a.machine_id === machineId);
  if (anomaly) {
    return {
      id: anomaly.id,
      type: 'anomaly',
      title: `Unusual reading ${anomaly.id}`,
      subtitle: anomaly.description,
      timestamp: anomaly.timestamp,
      data: { Machine: anomaly.machine_id, Sensor: anomaly.sensorLabel, Peak: `${anomaly.value}`, Limit: anomaly.limit },
    };
  }

  const note = notePool.find((n) => n.id.toLowerCase() === lc && n.machine_id === machineId);
  if (note) {
    return {
      id: note.id,
      type: 'note',
      title: `Maintenance note ${note.id}`,
      subtitle: note.author,
      timestamp: note.timestamp,
      data: { Machine: note.machine_id, Relation: note.tags.join(', ') },
      noteText: note.content,
    };
  }

  const reading = readings.find((r) => r.id.toLowerCase() === lc);
  if (reading) {
    const data: Record<string, string | number> = {};
    for (const s of sensors) {
      const v = reading[s.key];
      data[`${s.label} (${s.unit})`] = v == null || v === '' ? 'empty' : (v as number);
    }
    return {
      id: reading.id,
      type: 'reading',
      title: `Reading ${reading.id}`,
      subtitle: `Recorded ${reading.displayTime}`,
      timestamp: reading.timestamp,
      data,
    };
  }

  return unsupported;
}

/** History: GET /api/runs (kept in backend memory: newest 20, lost on restart - no database) */
export async function getRuns(): Promise<RunHistoryItem[]> {
  if (USE_MOCK) {
    await delay(150);
    return [...MOCK_RUNS];
  }
  const rows = await request<ApiRunSummary[]>('/api/runs');
  return rows.map((r) => ({
    id: r.run_id,
    name: r.dataset_name || r.dataset_id,
    timestamp: shortTs(r.created_at),
    dataset: r.dataset_name || r.dataset_id,
    datasetId: r.dataset_id,
    real: r.real,
    machineCount: r.machines,
    status: 'Completed',
    counts: r.counts,
  }));
}

/** History "Open": GET /api/runs/{run_id} and make it the current run */
export async function openRun(item: RunHistoryItem): Promise<void> {
  if (USE_MOCK) {
    saveCurrentRun({
      runId: item.id,
      datasetId: item.datasetId || 'synthetic_fleet',
      datasetName: item.dataset,
      real: !!item.real,
    });
    return;
  }
  const run = await request<ApiAnalysisResult>(`/api/runs/${encodeURIComponent(item.id)}`);
  rememberRun(run);
}

/** AI status: GET /api/llm/status - shown exactly as the backend reports it */
export async function getLlmStatus(): Promise<LlmStatus> {
  if (USE_MOCK) {
    await delay(150);
    return { ...MOCK_LLM_STATUS };
  }
  const s = await request<ApiLlmStatus>('/api/llm/status', undefined, 15000);
  return {
    provider: s.provider ?? null,
    model: s.model ?? null,
    hardware: s.hardware_label ?? null,
    reachable: !!s.reachable,
    latency: s.last_latency_ms ?? null,
    lastError: s.error ?? null,
  };
}

/**
 * AMD badge: true only when the backend reports provider "amd_token_factory" (real AI on AMD).
 * "mock" and "saved" get their own header text instead; "gemini" is never AMD.
 */
export function isAmd(provider?: string | null, reachable?: boolean): boolean {
  return provider === 'amd_token_factory' && reachable !== false;
}
