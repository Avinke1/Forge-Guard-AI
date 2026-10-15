# ForgeGuard AI — Data Dictionary

## 1. AI4I processed readings

*File:* data/processed/ai4i/readings.csv

| Column | Description |
|---|---|
| timestamp | Artificial timestamp assigned during conversion; not source-provided. |
| machine_id | Artificial machine identifier derived from the AI4I product type; not a real source machine ID. |
| air_temperature_c | Air temperature converted from the source Kelvin value to degrees Celsius. |
| process_temperature_c | Process temperature converted from the source Kelvin value to degrees Celsius. |
| rpm | Rotational speed in revolutions per minute. |
| torque_nm | Torque in newton-metres. |
| tool_wear_min | Tool wear in minutes. |
| label | Machine failure label: 1 indicates failure; 0 indicates no failure. |

*Source note:* AI4I 2020 is a synthetic predictive-maintenance dataset. Its readings are not real-world field measurements. The converted timestamps and machine IDs are artificial derived fields.

## 2. AI4I metadata

*File:* data/processed/ai4i/meta.csv

| Column | Description |
|---|---|
| timestamp | Artificial timestamp assigned during conversion. |
| machine_id | Artificial machine identifier assigned during conversion. |
| udi | Original AI4I unique data identifier. |
| product_id | Original AI4I product identifier. |
| type | Original product type category. |
| machine_failure | Original machine failure indicator. |
| twf | Tool Wear Failure indicator. |
| hdf | Heat Dissipation Failure indicator. |
| pwf | Power Failure indicator. |
| osf | Overstrain Failure indicator. |
| rnf | Random Failure indicator. |
| temp_diff_c | Derived difference between process and air temperature, in degrees Celsius. |
| power_w | Derived power value in watts, calculated from rotational speed and torque. |
| wear_torque_min_nm | Derived tool-wear and torque combination; units follow the source fields and conversion formula. |

The failure-mode indicators are separate flags. They must not be assumed to be mutually exclusive.

## 3. MetroPT-3 processed readings

*Files:* `data/processed/metropt3/readings_full_5min.csv` (50,782 windows),
`data/processed/metropt3/readings.csv` (1,898 demonstration windows).

Both contain a timestamp for the start of a five-minute bin, the constant real-equipment
identifier `APU-01` (assigned in this project), seven analog averages, five derived/quality fields,
and a source-reported event-window evaluation label.

| Column | Unit / meaning |
|---|---|
| timestamp | Five-minute window start, ISO 8601; source timestamp aggregated |
| machine_id | `APU-01`, project ID for the single source compressor |
| tp2_bar | TP2 compressor pressure mean, bar |
| tp3_bar | TP3 pneumatic-panel pressure mean, bar |
| h1_bar | H1 pressure sensor mean, bar |
| dv_pressure_bar | DV_pressure air-dryer discharge pressure mean, bar |
| reservoirs_bar | Reservoirs pressure mean, bar |
| oil_temperature_c | Oil temperature mean, °C |
| motor_current_a | Motor current mean, A |
| motor_current_max_a | Maximum source motor current in the window, A |
| compressor_loading_pct | Percentage of COMP=0 raw samples in window, per team source interpretation |
| compressor_loading_1h_pct | Past 60-minute rolling mean of available five-minute loading percentages |
| low_pressure_alarm_pct | Percentage of LPS=1 raw samples in window |
| raw_rows | Number of original samples contributing to that window |
| label | 1 if time window overlaps one of four reported air-leak intervals, otherwise 0; EVALUATION ONLY |

Cautions: some windows have fewer than 30 samples; missing time windows are dropped, not
interpolated. `label=0` means not within a *reported* event window, not proven healthy.
Do not use `label` as a predictive input. Synthetic-fleet thresholds do NOT apply here.

## 4. MetroPT-3 source notes

*File:* `knowledge/metropt3_notes_source.csv` (six original project source summaries).

| Column | Meaning |
|---|---|
| note_id | Stable source record identifier `MPT3-N001` to `MPT3-N006` |
| timestamp_start | Reported interval start or point-in-time maintenance time |
| timestamp_end | Reported interval end; empty for point-in-time maintenance |
| note_type | `failure_report` or `maintenance_record` |
| component | Component named in the source record |
| note_text | Source-derived description; not an original technician narrative |
| source | Source-document attribution |
| source_url | Link to the dataset source |

## 5. MetroPT-3 agent notes

*File:* `data/processed/metropt3/notes.csv` (six records).

| Column | Meaning |
|---|---|
| note_id | App ID `N-1` through `N-6`; `MPT3-N00x` preserved within the text |
| machine_id | `APU-01` |
| timestamp | ISO 8601: failure-window END for failure reports, point time for maintenance |
| text | Source-derived description with original event period, source record ID and source URL |
| source | Enum `maintenance` required by agent contract; not a claim of a verbatim technician log |
| synthetic | `false`: records are derived from cited source information, not invented events |

## 6. MetroPT-3 fault events

*File:* `data/processed/metropt3/fault_events.csv` (four records).

| Column | Meaning |
|---|---|
| event_id | F1, F2, F3, F4 in chronological order |
| machine_id | `APU-01` |
| failure | Reported failure type `Air leak` |
| severity | Reported high-stress context (`High stress`) |
| start | ISO 8601 interval start |
| end | ISO 8601 interval end |
| maintenance_report_as_written | Team source-table maintenance annotation; F2 April-vs-May inconsistency marked TO CHECK |

These are reported *intervals*, not individually verified fault-positive sensor readings.
Do not infer unreported fault types, exact repair details, or preventative intervention outcomes.

## 7. Sensor configuration provenance

- `config/sensors.json` is the approved **synthetic-fleet** threshold configuration only.
- `config/metropt3_sensors.json` lists MetroPT sensor names and units **without invented limits**.
- The backend must select configuration by dataset. Neither is evidence that a physical
  industrial shutdown threshold is validated.

## General interpretation cautions

- AI4I is synthetic. Its timestamps and machine IDs are artificially created for ForgeGuard.
- MetroPT-3 is one real compressor with limited reported air-leak events.
- The MetroPT notes are summaries of published source records, not verbatim work orders.
- Preserve source URLs and uncertainty; do not convert missing evidence into a diagnosis.
