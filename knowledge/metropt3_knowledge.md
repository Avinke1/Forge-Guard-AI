# ForgeGuard AI — MetroPT-3 Knowledge Notes

## Dataset provenance

- Dataset: MetroPT-3
- Provider: UCI Machine Learning Repository
- Dataset page: https://archive.ics.uci.edu/dataset/791/metropt+3+dataset
- Dataset DOI: https://doi.org/10.24432/C5VW3R
- License: CC BY 4.0
- Raw sensor file: MetroPT3(AirCompressor).csv
- Ownership: The raw sensor file is managed by the team lead. Member 4 must not modify it.

## Reported failure and maintenance notes

The project's source notes contain four failure reports and two maintenance records. The dates and times below are copied from the source records.

| Note ID | Start timestamp | End timestamp | Record type | Summary |
|---|---|---|---|---|
| MPT3-N001 | 2020-04-18 00:00:00 | 2020-04-18 23:59:00 | Failure report | Reported air leak; detailed location is not specified in the source note. |
| MPT3-N002 | 2020-05-29 23:30:00 | 2020-05-30 06:00:00 | Failure report | Reported air leak; detailed location is not specified in the source note. |
| MPT3-N003 | 2020-06-05 10:00:00 | 2020-06-07 14:30:00 | Failure report | Reported air leak; detailed location is not specified in the source note. |
| MPT3-N004 | 2020-06-08 16:00:00 | Not specified | Maintenance record | Maintenance recorded after the reported 5–7 June air leak. |
| MPT3-N005 | 2020-07-15 14:30:00 | 2020-07-15 19:00:00 | Failure report | Reported air leak; detailed location is not specified in the source note. |
| MPT3-N006 | 2020-07-16 00:00:00 | Not specified | Maintenance record | Maintenance recorded after the reported 15 July air leak. |

The source notes classify the reported air-leak events as high stress in the UCI failure information. Do not infer a specific physical leak location or additional failure details that the source does not provide.

### Maintenance date requiring review

The project's earlier notes mention maintenance on 30 April in connection with failure F2. That date precedes the 29–30 May report associated with MPT3-N002. Treat the relationship as *TO CHECK* with the team lead; do not silently change the source record.

## Sensor interpretation notes

The following values are project-provided interpretation notes. Confirm their applicability to the actual sensor columns and units before using them in automated decisions.

- Motor current: approximately 0 A when off, 4 A when offloaded, 7 A under load, and 9 A during starting.
- LPS: described in the project notes as active below 7 bar.
- MPG: described as starting the compressor below 8.2 bar.
- Oil-level signal: an active signal is described as indicating low oil.

These are working interpretation notes, not independently verified manufacturer specifications. Do not treat them as certified safety limits.

## Data handling cautions

- Keep raw source data unchanged.
- Distinguish source observations from derived values and project assumptions.
- Do not infer missing event durations, maintenance outcomes, or sensor meanings.
- Confirm sensor names, units, thresholds, and event alignment with the team lead before integrating them into the application.

## Research references

- MetroPT-3 dataset: https://doi.org/10.24432/C5VW3R
- Scientific Data paper: https://doi.org/10.1038/s41597-022-01877-3
- DSAA paper: https://doi.org/10.1109/DSAA53316.2021.9564181

