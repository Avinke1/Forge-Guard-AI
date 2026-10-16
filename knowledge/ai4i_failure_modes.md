# AI4I 2020 failure-mode knowledge

## What it is
The UCI AI4I 2020 Predictive Maintenance Dataset is synthetic, with 10,000 records and 14 columns. It models industrial/milling-machine conditions. Temperature columns are in Kelvin in the raw dataset. Convert Kelvin to Celsius only in a derived app-format dataset; do not overwrite the raw source.

## Failure flags
- **TWF — Tool Wear Failure:** tool wear reaches a randomly selected threshold in the 200–240 minute range; the source notes some cases are replaced and others fail.
- **HDF — Heat Dissipation Failure:** the air/process temperature difference is below 8.6 K and rotational speed is below 1,380 rpm.
- **PWF — Power Failure:** torque × rotational speed (converted to angular velocity) implies power below 3,500 W or above 9,000 W.
- **OSF — Overstrain Failure:** tool wear × torque exceeds a product-type-specific threshold: 11,000 min·Nm for L, 12,000 for M, 13,000 for H.
- **RNF — Random Failure:** a low-probability random failure flag; the source reports only a small number of cases.

`Machine failure` is the overall target; the five subtype flags are separate labels. UCI notes that the failure modes are independent and that not all machine failures are transparent from the main label alone.

## Implementation cautions
- AI4I is synthetic, not real field data.
- Raw temperature features are Kelvin; Celsius = Kelvin − 273.15.
- Do not fabricate timestamps and present them as source data. If the app contract needs timestamps, document that any added timestamps are synthetic/artificial.
- License: CC BY 4.0. Cite “AI4I 2020 Predictive Maintenance Dataset,” UCI Machine Learning Repository, DOI 10.24432/C5HS5C.
## Verified dataset counts and quirks

The converted AI4I 2020 dataset contains 10,000 rows and 339 rows where
Machine failure is 1.

Failure-mode flag counts:
- TWF (Tool Wear Failure): 46
- HDF (Heat Dissipation Failure): 115
- PWF (Power Failure): 95
- OSF (Overstrain Failure): 98
- RNF (Random Failure): 19

These subtype counts are independent and must not be summed as though each
failure row has exactly one subtype.

Data-quality quirks observed during conversion:
- 9 rows have Machine failure = 1 but no failure-mode flag set.
- 18 rows have a failure-mode flag set while Machine failure is 0.
- 24 rows have multiple failure-mode flags set.

The app-format conversion adds artificial timestamps and machine IDs.
These are not source-provided AI4I observations and must not be represented
as original dataset values.
