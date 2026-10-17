export type PriorityLevel = 'HIGH' | 'MEDIUM' | 'LOW' | 'OK';

export interface SensorConfig {
  key: string;
  label: string;
  unit: string;
  warn_high: number | null;
  warn_low: number | null;
}

export interface Anomaly {
  id: string;
  machine_id: string;
  sensor: string;
  sensorLabel: string;
  value: number | string;
  limit: string;
  timestamp: string;
  description: string;
  severity: PriorityLevel;
}

export interface MaintenanceNote {
  id: string;
  machine_id: string;
  timestamp: string;
  author: string;
  content: string;
  tags: string[];
}

export interface SensorReading {
  id: string;
  machine_id: string;
  timestamp: string;
  displayTime: string;
  is_anomaly?: boolean;
  anomaly_id?: string;
  anomaly_sensors?: string[];
  [sensorKey: string]: string | number | boolean | string[] | null | undefined;
}

export interface Machine {
  id: string;
  name: string;
  type: string;
  location: string;
  priority: PriorityLevel;
  summary: string;
  rank: number;
  anomalies: Anomaly[];
  notes: MaintenanceNote[];
  warnings: string[];
  readingsCount: number;
  lastReading: string;
  sensorsInvolved?: string[];
}

export interface Finding {
  id: string;
  title: string;
  detail: string;
  evidence: string[];
  unsupported?: boolean;
}

export interface MachineReport {
  machine_id: string;
  header: string;
  summary: string;
  findings: Finding[];
  possibleCauses: string[];
  recommendedChecks: string[];
  missingInformation: string[];
  uncertainty: string;
  failed?: boolean;
  errorMessage?: string;
  ruleBasedFallback?: boolean;
  ruleBasedSummary?: string;
  mock?: boolean;
  provider?: string | null;
  model?: string | null;
  hardware?: string | null;
  latencyMs?: number | null;
}

export interface RunHistoryItem {
  id: string;
  name: string;
  timestamp: string;
  dataset: string;
  datasetId?: string;
  real?: boolean;
  machineCount: number;
  status: string;
  rowsCount?: number;
  validRows?: number;
  droppedRows?: number;
  counts?: Partial<Record<PriorityLevel, number>>;
}

export interface LlmStatus {
  provider: string | null;
  model: string | null;
  hardware: string | null;
  reachable: boolean;
  latency: number | null;
  lastError?: string | null;
}

export interface ValidationReport {
  totalRows: number;
  keptRows: number;
  droppedRows: number;
  details: string[];
}

export interface AnalyzeResult {
  runId: string;
  datasetId: string;
  datasetName: string;
  validation: ValidationReport;
}

export interface EvidenceDetail {
  id: string;
  type: 'anomaly' | 'reading' | 'note' | 'unsupported';
  title: string;
  subtitle?: string;
  timestamp?: string;
  data: Record<string, string | number>;
  noteText?: string;
  isUnsupported?: boolean;
}

/* ---------- Backend contract (section 6) - raw JSON shapes ---------- */
export interface ApiRunResult {
  run_id: string;
  dataset_id: string;
  dataset_name?: string;
  real?: boolean;
  validation: { rows_in: number; rows_kept: number; rows_dropped: number; errors: string[]; warnings: string[] };
  sensors: Record<string, { label: string; unit: string; warn_high: number | null; warn_low: number | null }>;
  queue: {
    rank: number;
    machine_id: string;
    name: string;
    priority: PriorityLevel;
    top_reason: string;
    sensors: string[];
    notes_count: number;
    ai_status: string;
  }[];
  machines: Record<
    string,
    {
      readings: ({ row_id: string; timestamp: string } & Record<string, number | string | null>)[];
      anomalies: { id: string; sensor: string; start: string; end: string; peak: number; rule: string }[];
      notes: { id: string; timestamp: string; text: string; relation: string }[];
      data_warnings: string[];
    }
  >;
}

export interface ApiAIReport {
  status: 'ok' | 'error';
  error?: string | null;
  mock?: boolean;
  provider?: string | null;
  model?: string | null;
  hardware?: string | null;
  latency_ms?: number | null;
  summary: string;
  findings: { text: string; evidence: string[]; supported: boolean }[];
  possible_causes: string[];
  recommended_checks: string[];
  missing_information: string[];
  uncertainty: string;
  rule_based_summary?: string | null;
}
