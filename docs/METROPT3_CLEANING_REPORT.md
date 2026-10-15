# MetroPT-3 cleaning report (ForgeGuard AI)

Source: UCI MetroPT-3 (dataset 791), MetroPT3(AirCompressor).csv, CC BY 4.0, real data.
Raw file matches the official SHA-256: True

## Cleaning steps

| Step | Result |
|---|---|
| raw rows | 1,516,948 |
| raw columns | 17 |
| C1 index column dropped | 1 |
| C2 unreadable timestamps removed | 0 |
| C3 exact duplicate rows removed | 0 |
| C4 duplicate timestamps removed | 0 |
| C5 missing values found (left empty) | 0 |
| C6 out-of-range analog values set empty | 0 |
| C7 digital values not 0/1 set empty | 0 |
| C8 gaps longer than 1 hour (no data) | 160 |
| rows after cleaning | 1,516,948 |
| empty 5-minute windows dropped (C8) | 10,610 |

Small negative pressures (down to about -0.03 bar) are sensor zero noise and are kept.
Gaps (compressor off / no data) are dropped, never filled with made-up values.

## Output columns (5-minute windows, machine APU-01)

| Column | Meaning |
|---|---|
| timestamp | start of the 5-minute window (ISO 8601) |
| machine_id | APU-01 (the metro train air compressor) |
| tp2_bar ... motor_current_a | average of the 7 analog sensors in the window |
| motor_current_max_a | highest motor current in the window (A) |
| compressor_loading_pct | % of the window the compressor was loading (COMP = 0) |
| compressor_loading_1h_pct | average loading % over the last 60 minutes (past data only) |
| low_pressure_alarm_pct | % of the window the low-pressure signal LPS was active (below 7 bar) |
| raw_rows | number of raw 10-second readings in the window (30 = complete) |
| label | 1 if the window overlaps an official air-leak failure F1-F4; for scoring only, never an agent input |

## Why these features (measured on this data)

| Feature | Normal windows | Failure windows |
|---|---|---|
| compressor_loading_pct | 14.97 | 99.48 |
| compressor_loading_1h_pct | 15.35 | 98.49 |
| low_pressure_alarm_pct | 0.38 | 2.52 |
| motor_current_max_a | 3.24 | 5.7 |
| tp3_bar | 8.99 | 8.28 |

Windows: 50,782 (full), 1,898 (demo 8-16 Jul 2020). Failure windows: 994 {'F1': 288, 'F2': 78, 'F3': 574, 'F4': 54}.
