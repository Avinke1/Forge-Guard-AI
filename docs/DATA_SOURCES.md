# ForgeGuard AI - Data Sources

## 1. AI4I 2020 Predictive Maintenance Dataset

- *Provider:* UCI Machine Learning Repository
- *Dataset page:* https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset
- *License:* CC BY 4.0
- *Nature:* Synthetic predictive-maintenance data, not real field measurements.
- *Raw file:* data/raw/ai4i/ai4i2020.csv
- *Knowledge document:* knowledge/ai4i_failure_modes.md

The raw dataset contains 10,000 records and 14 columns. Raw temperature
features are in Kelvin. The app-format conversion uses Celsius and adds
artificial timestamps and machine IDs; these are derived fields, not original
source observations.

## 2. MetroPT-3 Dataset

- *Provider:* UCI Machine Learning Repository
- *Dataset page:* https://archive.ics.uci.edu/dataset/791/metropt+3+dataset
- *Dataset DOI:* https://doi.org/10.24432/C5VW3R
- *Dataset download ZIP:* https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip
- *License:* CC BY 4.0
- *Notes source:* knowledge/metropt3_notes_source.csv
- *Knowledge document:* knowledge/metropt3_knowledge.md

The MetroPT-3 sensor file is owned by the team lead. Member 4 should not
modify the raw sensor file.

## 3. MetroPT-3 research papers

- *Scientific Data paper:* https://doi.org/10.1038/s41597-022-01877-3
- *DSAA paper:* https://doi.org/10.1109/DSAA53316.2021.9564181

Verify paper titles and author details against the linked publications before
adding a formal bibliography.

## 4. Data handling and provenance

- Keep raw source files unchanged.
- Store transformations and derived outputs separately from raw data.
- Do not present artificial timestamps or machine IDs as source-provided
  observations.
- Preserve source URLs and licensing details when sharing derived datasets.
- Project-defined synthetic-fleet thresholds are not manufacturer-certified
  safety limits.
