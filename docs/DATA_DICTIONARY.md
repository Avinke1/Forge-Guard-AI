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

## 3. MetroPT-3 notes

*File:* data/processed/metropt3/notes.csv

| Column | Description |
|---|---|
| note_id | Identifier for a source note. |
| timestamp_start | Start timestamp recorded for the note. |
| timestamp_end | End timestamp recorded for the note; may be empty. |
| note_type | Note classification, such as failure_report or maintenance_record. |
| component | Component associated with the note. |
| note_text | Text describing the reported event or maintenance information. |
| source | Source attribution recorded in the notes dataset. |
| source_url | URL recorded for the source. |

## 4. MetroPT-3 fault events

*File:* data/processed/metropt3/fault_events.csv

This file uses the same columns as notes.csv, but contains only rows classified as failure_report.

| Column | Description |
|---|---|
| note_id | Identifier for the source failure note. |
| timestamp_start | Start timestamp recorded for the failure report. |
| timestamp_end | End timestamp recorded for the failure report; may be empty. |
| note_type | Failure-report classification. |
| component | Component associated with the report. |
| note_text | Description of the reported failure. |
| source | Source attribution recorded in the notes dataset. |
| source_url | URL recorded for the source. |

*Important:* These are note-derived event records, not a direct conversion of the raw MetroPT-3 sensor measurements. The raw sensor file remains under team-lead ownership.

## Data interpretation cautions

- Do not present artificial AI4I timestamps or machine IDs as original observations.
- AI4I is synthetic data, not real-world industrial sensor data.
- Derived AI4I fields must be distinguished from original source columns.
- An empty timestamp_end in a note does not establish an event duration.
- Project-defined alert thresholds are not manufacturer-certified safety limits.
- Do not infer missing fault details or maintenance outcomes from incomplete notes.
