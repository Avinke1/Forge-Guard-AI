import { Machine, Anomaly, MaintenanceNote, SensorReading, MachineReport, RunHistoryItem, LlmStatus, SensorConfig } from '../types';

export const SENSOR_THRESHOLDS = {
  vibration_mm_s: { name: 'Vibration', unit: 'mm/s', max: 6.5, min: undefined },
  temperature_c: { name: 'Temperature', unit: '°C', max: 90.0, min: undefined },
  pressure_bar: { name: 'Pressure', unit: 'bar', max: 225.0, min: 120.0 },
  sound_db: { name: 'Sound Level', unit: 'dB', max: 85.0, min: undefined },
  rpm: { name: 'Rotational Speed', unit: 'RPM', max: 1260, min: 1140 },
};

export const MOCK_NOTES: MaintenanceNote[] = [
  {
    id: 'N-14',
    machine_id: 'HP-01',
    timestamp: '2026-10-15 16:30',
    author: 'Dave M. (Technician)',
    content: 'Replaced flexible coupling element during shift handover. Applied lithium-complex grease to drive-end roller bearing housing.',
    tags: ['Coupling', 'Lubrication', 'Handover'],
  },
  {
    id: 'N-15',
    machine_id: 'HP-01',
    timestamp: '2026-10-16 07:45',
    author: 'Sarah K. (Floor Operator)',
    content: 'Acoustic hum detected upon initiating high-volume cycle. Vibration pen indicated elevated trend along motor frame.',
    tags: ['Acoustic', 'Vibration', 'Startup'],
  },
  {
    id: 'N-8',
    machine_id: 'FP-02',
    timestamp: '2026-10-15 13:30',
    author: 'Alex R. (Field Tech)',
    content: 'Coolant circuit inlet filter differential pressure gauge showed restriction. Cleaned pre-strainer; recommended scheduled bypass overhaul.',
    tags: ['Cooling', 'Filter', 'Inspection'],
  },
  {
    id: 'N-17',
    machine_id: 'HP-02',
    timestamp: '2026-10-16 10:45',
    author: 'Leo T. (Shift Supervisor)',
    content: 'Pressure relief valve PRV-202 adjusted after rapid backpressure surge during line ramp. Noted momentary line pulsation.',
    tags: ['Hydraulics', 'Relief Valve', 'Pressure Spike'],
  },
];

export const MOCK_ANOMALIES: Anomaly[] = [
  {
    id: 'A-1',
    machine_id: 'HP-01',
    sensor: 'vibration_mm_s',
    sensorLabel: 'Vibration',
    value: 7.9,
    limit: '> 6.5 mm/s',
    timestamp: '2026-10-16 08:30',
    description: 'Vibration exceeded upper limit reaching 7.9 mm/s, steadily rising from 08:00 baseline.',
    severity: 'HIGH',
  },
  {
    id: 'A-2',
    machine_id: 'HP-01',
    sensor: 'sound_db',
    sensorLabel: 'Sound Level',
    value: 89.4,
    limit: '> 85.0 dB',
    timestamp: '2026-10-16 09:15',
    description: 'Acoustic noise rose to 89.4 dB, concurrent with mechanical vibration escalation.',
    severity: 'HIGH',
  },
  {
    id: 'A-3',
    machine_id: 'FP-02',
    sensor: 'temperature_c',
    sensorLabel: 'Temperature',
    value: 94.8,
    limit: '> 90.0 °C',
    timestamp: '2026-10-15 14:45',
    description: 'Continuous thermal excursion above 90 °C sustained between 14:00 and 16:00.',
    severity: 'HIGH',
  },
  {
    id: 'A-4',
    machine_id: 'HP-02',
    sensor: 'pressure_bar',
    sensorLabel: 'Pressure',
    value: 238.2,
    limit: '> 225.0 bar',
    timestamp: '2026-10-16 11:30',
    description: 'Hydraulic line pressure breached upper threshold peaking at 238.2 bar between 11:00 and 12:00.',
    severity: 'MEDIUM',
  },
];

export const MOCK_MACHINES: Machine[] = [
  {
    id: 'HP-01',
    name: 'Hydraulic press 1',
    type: 'Hydraulic press',
    location: 'Bay 3 - Primary Extrusion Line',
    priority: 'HIGH',
    summary: 'Vibration and sound rising since 16 Oct 08:00',
    rank: 1,
    anomalies: [MOCK_ANOMALIES[0], MOCK_ANOMALIES[1]],
    notes: [MOCK_NOTES[0], MOCK_NOTES[1]],
    warnings: [],
    readingsCount: 288,
    lastReading: '2026-10-16 23:45',
  },
  {
    id: 'FP-02',
    name: 'Forming press 2',
    type: 'Forming press',
    location: 'Bay 1 - Thermal Management Loop',
    priority: 'HIGH',
    summary: 'Temperature above 90 °C, 15 Oct 14:00-16:00',
    rank: 2,
    anomalies: [MOCK_ANOMALIES[2]],
    notes: [MOCK_NOTES[2]],
    warnings: [],
    readingsCount: 288,
    lastReading: '2026-10-16 23:45',
  },
  {
    id: 'HP-02',
    name: 'Hydraulic press 2',
    type: 'Hydraulic press',
    location: 'Bay 4 - Secondary Stamping Press',
    priority: 'MEDIUM',
    summary: 'Pressure above 225 bar, 16 Oct 11:00-12:00',
    rank: 3,
    anomalies: [MOCK_ANOMALIES[3]],
    notes: [MOCK_NOTES[3]],
    warnings: [],
    readingsCount: 288,
    lastReading: '2026-10-16 23:45',
  },
  {
    id: 'DS-02',
    name: 'Drive shaft 2',
    type: 'Drive shaft',
    location: 'Bay 2 - Conveyor Infeed',
    priority: 'LOW',
    summary: 'Data quality issues',
    rank: 4,
    anomalies: [],
    notes: [],
    warnings: ['3 empty cells', 'rpm -50 dropped', 'gap 03:00-03:45'],
    readingsCount: 284,
    lastReading: '2026-10-16 23:45',
  },
  {
    id: 'DS-01',
    name: 'Drive shaft 1',
    type: 'Drive shaft',
    location: 'Bay 2 - Outfeed Gantry',
    priority: 'OK',
    summary: 'One-off spike ignored (9.0 mm/s at 15 Oct 10:15)',
    rank: 5,
    anomalies: [],
    notes: [],
    warnings: [],
    readingsCount: 288,
    lastReading: '2026-10-16 23:45',
  },
  {
    id: 'FP-01',
    name: 'Forming press 1',
    type: 'Forming press',
    location: 'Bay 1 - Auxiliary Recirculation',
    priority: 'OK',
    summary: 'All readings within normal range',
    rank: 6,
    anomalies: [],
    notes: [],
    warnings: [],
    readingsCount: 288,
    lastReading: '2026-10-16 23:45',
  },
];

// Generate consistent 15-minute readings for 14-16 Oct 2026
export function generateMachineReadings(machineId: string): SensorReading[] {
  const readings: SensorReading[] = [];
  const startDate = new Date('2026-10-14T00:00:00Z');
  // 3 days: 14 Oct 00:00 through 16 Oct 23:45 (288 timestamps at 15 min increments)
  const totalSteps = 288;

  for (let i = 0; i < totalSteps; i++) {
    const current = new Date(startDate.getTime() + i * 15 * 60 * 1000);
    const day = current.getUTCDate();
    const hour = current.getUTCHours();
    const minute = current.getUTCMinutes();
    const pad = (n: number) => n.toString().padStart(2, '0');
    const timeStr = `${pad(hour)}:${pad(minute)}`;
    const displayTime = `${day} Oct ${timeStr}`;
    const isoTimestamp = `2026-10-${pad(day)} ${timeStr}`;
    const readingId = `R${100 + i}`;

    let vib = 2.8 + Math.sin(i / 6) * 0.7 + (Math.sin(i * 1.5) * 0.3);
    let temp = 68.0 + Math.sin(i / 10) * 4.5 + (i * 0.04);
    let press = 175.0 + Math.cos(i / 7) * 12.0;
    let sound = 71.0 + Math.sin(i / 8) * 3.5;
    let rpm = 1200 + Math.round(Math.sin(i / 5) * 22);
    let isAnomaly = false;
    let anomalyId: string | undefined = undefined;
    const anomalySensors: string[] = [];

    if (machineId === 'HP-01') {
      // 16 Oct after 08:00 (step 96 to 112)
      if (day === 16 && (hour > 8 || (hour === 8 && minute >= 0))) {
        const factor = Math.min(1, (i - 224) / 16); // 16 Oct 08:00 = step 224
        vib = 6.2 + factor * 1.9 + Math.sin(i) * 0.2;
        sound = 82.0 + factor * 8.2 + Math.sin(i * 2) * 0.5;
        if (vib > 6.5 || sound > 85.0) {
          isAnomaly = true;
          anomalySensors.push(vib > 6.5 ? 'vibration_mm_s' : 'sound_db');
          if (day === 16 && hour === 8 && minute === 30) {
            anomalyId = 'A-1';
          } else if (day === 16 && hour === 9 && minute === 15) {
            anomalyId = 'A-2';
          }
        }
      }
    } else if (machineId === 'FP-02') {
      // 15 Oct 14:00 to 16:00 (steps 56 to 64)
      if (day === 15 && (hour === 14 || hour === 15 || (hour === 16 && minute === 0))) {
        temp = 91.5 + Math.sin(i * 0.9) * 3.5;
        if (temp > 90.0) {
          isAnomaly = true;
          anomalySensors.push('temperature_c');
          if (day === 15 && hour === 14 && minute === 45) {
            anomalyId = 'A-3';
          }
        }
      }
    } else if (machineId === 'HP-02') {
      // 16 Oct 11:00 to 12:00 (steps 108 to 112)
      if (day === 16 && (hour === 11 || (hour === 12 && minute === 0))) {
        press = 227.0 + Math.sin(i * 1.2) * 12.0;
        if (press > 225.0) {
          isAnomaly = true;
          anomalySensors.push('pressure_bar');
          if (day === 16 && hour === 11 && minute === 30) {
            anomalyId = 'A-4';
          }
        }
      }
    } else if (machineId === 'DS-01') {
      // Single spike at 15 Oct 10:15
      if (day === 15 && hour === 10 && minute === 15) {
        vib = 9.0; // Filtered/isolated spike
      }
    } else if (machineId === 'DS-02') {
      // Missing gap 03:00-03:45 on 15 Oct
      if (day === 15 && hour === 3) {
        continue;
      }
      if (i === 40) {
        // Dropped invalid RPM
        rpm = 1195;
      }
    }

    // Keep numbers clean and rounded
    readings.push({
      id: readingId,
      machine_id: machineId,
      timestamp: isoTimestamp,
      displayTime,
      vibration_mm_s: Number(vib.toFixed(2)),
      temperature_c: Number(temp.toFixed(1)),
      pressure_bar: Number(press.toFixed(1)),
      sound_db: Number(sound.toFixed(1)),
      rpm: Math.round(rpm),
      is_anomaly: isAnomaly,
      anomaly_id: anomalyId,
      anomaly_sensors: anomalySensors,
    });
  }

  return readings;
}

export const MOCK_REPORTS: Record<string, MachineReport> = {
  'HP-01': {
    machine_id: 'HP-01',
    header: 'MOCK - not AI output',
    mock: true,
    summary: 'Correlated elevation in high-frequency vibration and acoustic sound profile detected following shift handover on 16 Oct. The symptoms indicate possible mechanical misalignment or premature wear on the recently replaced flexible coupling.',
    findings: [
      {
        id: 'F-1',
        title: 'Coupled Vibration & Acoustic Escalation',
        detail: 'Vibration accelerated from 4.2 mm/s baseline to 7.9 mm/s peak at 08:30, while sound pressure climbed past threshold to 89.4 dB at 09:15.',
        evidence: ['A-1', 'A-2', 'R328'],
      },
      {
        id: 'F-2',
        title: 'Temporal Alignment With Coupling Service',
        detail: 'Handover maintenance note records replacement of coupling bushing and bearing lubrication on 15 Oct 16:30. Acoustic hum subsequently noted during morning stage ramp.',
        evidence: ['N-14', 'N-15'],
      },
    ],
    possibleCauses: [
      'Angular or parallel misalignment during coupling sleeve installation',
      'Coupling elastomer insert pinching or improper axial gap clearance',
      'Lubricant overfill in bearing cavity generating hydrodynamic friction churn',
    ],
    recommendedChecks: [
      'Perform dual-dial laser alignment on motor-to-press drive shaft interface',
      'Inspect flexible coupling element for rubber fretting or abnormal contact wear',
      'Verify grease relief port status on drive-end bearing',
      'Record 1X and 2X shaft rotational harmonic spectrum analysis',
    ],
    missingInformation: [
      'Coupling alignment laser measurement sheet from 15 Oct installation',
      'Lubricant batch and exact mass injected into bearing housing',
    ],
    uncertainty: 'Moderate confidence. Correlation with maintenance timing is high, but spectrum frequency breakdown is needed to definitively distinguish coupling misalignment from internal gear cavitation.',
  },
  'HP-02': {
    machine_id: 'HP-02',
    header: 'MOCK - not AI output',
    mock: true,
    summary: 'Transient over-pressurization recorded during batch cycle surge. Secondary finding citations contain unsupported references that must be discarded.',
    findings: [
      {
        id: 'F-1',
        title: 'Hydraulic Manifold Pressure Spike',
        detail: 'Pressure breached maximum working limit reaching 238.2 bar between 11:00 and 12:00 following feed valve actuation.',
        evidence: ['A-4', 'N-17'],
      },
      {
        id: 'F-2',
        title: 'Cavitation Event Flag',
        detail: 'Alleged cavitation signature detected at high suction pressure.',
        evidence: ['A-99'],
        unsupported: true,
      },
    ],
    possibleCauses: [
      'Proportional relief valve spool sluggish response during load dump',
      'Hydraulic accumulator bladder pre-charge pressure lower than specification',
    ],
    recommendedChecks: [
      'Check PRV-202 relief valve response time and seat leakage',
      'Verify accumulator nitrogen charge pressure via charging kit',
    ],
    missingInformation: [
      'Accumulator pre-charge logbook from previous quarter',
    ],
    uncertainty: 'Low-to-moderate. Primary pressure surge is confirmed by sensor telemetry; secondary cavitation claim is unsupported by analysis telemetry.',
  },
  'FP-02': {
    machine_id: 'FP-02',
    header: 'MOCK - not AI output',
    mock: true,
    summary: '',
    failed: true,
    errorMessage: 'AI service not reachable (mock example of an AI failure).',
    ruleBasedFallback: true,
    ruleBasedSummary: 'FP-02: temperature above the 90 °C limit on 15 Oct 14:00-16:00 (anomaly A-3). Note N-8 was written after this period. Check the cooling circuit first.',
    findings: [
      {
        id: 'F-RB-1',
        title: 'Thermal Limit Exceeded (Rule-Based)',
        detail: 'Sensor temperature_c registered above 90.0 °C threshold between 14:00 and 16:00 on 15 Oct, reaching max 94.8 °C. Triggered by static threshold rule R-TEMP-90.',
        evidence: ['A-3', 'N-8'],
      },
    ],
    possibleCauses: [
      'Coolant circuit flow restriction or clogged heat exchanger pre-strainer',
      'Thermostatic bypass valve stuck in partial closed position',
    ],
    recommendedChecks: [
      'Inspect coolant filter differential pressure and clean bypass filter element',
      'Check thermal imagery of heat exchanger core for localized hot spots',
    ],
    missingInformation: [
      'Coolant flow rate sensor reading (flow meter not installed on loop)',
    ],
    uncertainty: 'Rule-based evaluation based solely on threshold breach and maintenance log tag.',
  },
  'DS-02': {
    machine_id: 'DS-02',
    header: 'MOCK - not AI output',
    mock: true,
    summary: 'Telemetry signals showed data collection gaps and negative values requiring sensor bus cleanup.',
    findings: [
      {
        id: 'F-1',
        title: 'Data Channel Continuity Drop',
        detail: 'Sensor bus dropped frames during 03:00-03:45 interval; negative RPM reading dropped during normalization.',
        evidence: [],
      },
    ],
    possibleCauses: ['Modbus/TCP gateway packet drop during nightly network backup'],
    recommendedChecks: ['Check RS-485 termination resistor and gateway communication logs'],
    missingInformation: ['Gateway network packet error counters'],
    uncertainty: 'Data telemetry quality requires field instrument verification.',
  },
  'DS-01': {
    machine_id: 'DS-01',
    header: 'MOCK - not AI output',
    mock: true,
    summary: 'Machine operation is stable. Isolated vibration peak at 15 Oct 10:15 was determined to be mechanical impact shock rather than progressive degradation.',
    findings: [
      {
        id: 'F-1',
        title: 'Isolated Impact Shock Filtered',
        detail: 'Spike of 9.0 mm/s lasted exactly one reading interval and returned to 2.9 mm/s nominal baseline immediately.',
        evidence: [],
      },
    ],
    possibleCauses: ['External transient impact from gantry crane loading nearby pallet'],
    recommendedChecks: ['No immediate maintenance required. Maintain regular shift monitoring.'],
    missingInformation: [],
    uncertainty: 'High confidence. All subsequent readings remain firmly within nominal envelope.',
  },
  'FP-01': {
    machine_id: 'FP-01',
    header: 'MOCK - not AI output',
    mock: true,
    summary: 'All telemetry channels are within specified operational envelopes. No threshold violations or abnormal drift patterns detected.',
    findings: [
      {
        id: 'F-1',
        title: 'Nominal Envelope Verification',
        detail: 'Continuous vibration, temperature, pressure, acoustic and rotational signals exhibit normal variance across the entire 48-hour monitoring period.',
        evidence: [],
      },
    ],
    possibleCauses: ['Normal operation'],
    recommendedChecks: ['Continue standard scheduled preventative inspection schedule.'],
    missingInformation: [],
    uncertainty: 'High confidence. Nominal baseline confirmed.',
  },
};

export const MOCK_RUNS: RunHistoryItem[] = [
  {
    id: 'MOCK-RUN-2',
    name: 'Synthetic fleet demo',
    timestamp: '2026-10-16 18:30',
    dataset: 'Synthetic fleet',
    datasetId: 'synthetic_fleet',
    real: false,
    machineCount: 6,
    status: 'Completed',
    rowsCount: 1728,
    validRows: 1724,
    droppedRows: 4,
    counts: { HIGH: 2, MEDIUM: 1, LOW: 1, OK: 2 },
  },
  {
    id: 'MOCK-RUN-1',
    name: 'MetroPT-3 demo',
    timestamp: '2026-10-16 18:45',
    dataset: 'MetroPT-3 (UCI, CC BY 4.0)',
    datasetId: 'metropt3',
    real: true,
    machineCount: 1,
    status: 'Completed',
    rowsCount: 145,
    validRows: 145,
    droppedRows: 0,
    counts: { HIGH: 1, MEDIUM: 0, LOW: 0, OK: 0 },
  },
];

// Mock mode has no AI connected - never show a model or hardware here.
export const MOCK_LLM_STATUS: LlmStatus = {
  provider: 'mock',
  model: null,
  hardware: null,
  reachable: false,
  latency: null,
  lastError: null,
};

export const FLEET_SENSORS: SensorConfig[] = [
  { key: 'vibration_mm_s', label: 'Vibration', unit: 'mm/s', warn_high: 6.5, warn_low: null },
  { key: 'temperature_c', label: 'Temperature', unit: '°C', warn_high: 90, warn_low: null },
  { key: 'pressure_bar', label: 'Pressure', unit: 'bar', warn_high: 225, warn_low: 120 },
  { key: 'sound_db', label: 'Sound level', unit: 'dB', warn_high: 85, warn_low: null },
  { key: 'rpm', label: 'Rotational speed', unit: 'rpm', warn_high: 1260, warn_low: 1140 },
];

/* ---------------- MetroPT-3 mock (one real compressor, APU-01) ---------------- */
export const METRO_SENSORS: SensorConfig[] = [
  { key: 'oil_temperature_c', label: 'Oil temperature', unit: '°C', warn_high: null, warn_low: null },
  { key: 'motor_current_a', label: 'Motor current', unit: 'A', warn_high: null, warn_low: null },
  { key: 'compressor_loading_pct', label: 'Compressor loading', unit: '%', warn_high: null, warn_low: null },
  { key: 'tp2_bar', label: 'TP2 pressure', unit: 'bar', warn_high: null, warn_low: null },
];

export const METRO_NOTES: MaintenanceNote[] = [
  {
    id: 'N-5',
    machine_id: 'APU-01',
    timestamp: '2020-07-15 19:00',
    author: 'Maintenance record',
    content: 'Air leak reported - maintenance carried out (source record MPT3-N005)',
    tags: ['after'],
  },
  {
    id: 'N-6',
    machine_id: 'APU-01',
    timestamp: '2020-07-16 00:00',
    author: 'Maintenance record',
    content: 'Maintenance completed (source record MPT3-N006)',
    tags: ['after'],
  },
];

export const METRO_ANOMALIES: Anomaly[] = [
  {
    id: 'A-1',
    machine_id: 'APU-01',
    sensor: 'compressor_loading_pct',
    sensorLabel: 'Compressor loading',
    value: 99.5,
    limit: "Compared with this machine's normal pattern",
    timestamp: '2020-07-15 14:30',
    description: 'Compressor loading and motor current unusual for this machine, 15 Jul 14:30-19:00.',
    severity: 'HIGH',
  },
];

export const METRO_MACHINES: Machine[] = [
  {
    id: 'APU-01',
    name: 'Metro train air compressor',
    type: 'Air production unit',
    location: 'Metro train (MetroPT-3 dataset)',
    priority: 'HIGH',
    summary: 'Compressor loading and motor current unusual on 15 Jul 2020 14:30-19:00',
    rank: 1,
    anomalies: METRO_ANOMALIES,
    notes: METRO_NOTES,
    warnings: [],
    readingsCount: 145,
    lastReading: '2020-07-15 22:00',
    sensorsInvolved: ['compressor_loading_pct', 'motor_current_a'],
  },
];

export function generateMetroReadings(): SensorReading[] {
  const out: SensorReading[] = [];
  const pad = (n: number) => n.toString().padStart(2, '0');
  for (let i = 0; i < 145; i++) {
    const minutes = 10 * 60 + i * 5;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    const unusual = minutes >= 14 * 60 + 30 && minutes < 19 * 60;
    out.push({
      id: `R${2000 + i}`,
      machine_id: 'APU-01',
      timestamp: `2020-07-15 ${pad(h)}:${pad(m)}`,
      displayTime: `15 Jul ${pad(h)}:${pad(m)}`,
      oil_temperature_c: Math.round((62 + Math.sin(i / 9) * 3 + (unusual ? 6 : 0)) * 10) / 10,
      motor_current_a: Math.round((unusual ? 5.7 + Math.sin(i) * 0.15 : 3.2 + Math.sin(i / 4) * 0.4) * 100) / 100,
      compressor_loading_pct: Math.round((unusual ? 99.3 + Math.sin(i) * 0.4 : 15 + Math.sin(i / 3) * 8) * 10) / 10,
      tp2_bar: Math.round((unusual ? 8.1 + Math.sin(i) * 0.3 : 9.2 + Math.sin(i / 5) * 0.5) * 100) / 100,
      is_anomaly: unusual,
      anomaly_id: unusual ? 'A-1' : undefined,
      anomaly_sensors: unusual ? ['compressor_loading_pct', 'motor_current_a'] : [],
    });
  }
  return out;
}

export const METRO_REPORT: MachineReport = {
  machine_id: 'APU-01',
  header: 'MOCK - not AI output',
  mock: true,
  summary:
    'Between 14:30 and 19:00 on 15 Jul 2020 the compressor ran almost fully loaded with higher motor current than its normal pattern. A maintenance record about an air leak follows at 19:00.',
  findings: [
    {
      id: 'F-1',
      title: 'Compressor loading unusual for this machine',
      detail: 'Loading stayed near 99% for 4.5 hours, far above this compressor\'s usual level.',
      evidence: ['A-1', 'R2054'],
    },
    {
      id: 'F-2',
      title: 'Maintenance record right after the unusual period',
      detail: 'An air leak was reported and maintenance carried out at 19:00, when the unusual period ends.',
      evidence: ['N-5', 'N-6'],
    },
  ],
  possibleCauses: ['Air leak in the pneumatic circuit making the compressor work harder'],
  recommendedChecks: ['Check the air circuit for leaks', 'Confirm the maintenance record N-5 was completed'],
  missingInformation: ['Exact location of the leak'],
  uncertainty: 'Medium - based on one machine and its own normal pattern; no fixed limits exist for these sensors.',
};
