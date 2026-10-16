import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "knowledge" / "fault_action_table.csv"

GUIDANCE = "general guidance, not manufacturer-verified"

with SOURCE.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    if not reader.fieldnames:
        raise ValueError("CSV header is missing")

    original_columns = reader.fieldnames
    if "guidance" in original_columns:
        raise ValueError("guidance already exists; stop and inspect")

    rows = list(reader)

if len(rows) != 11:
    raise ValueError(f"Expected 11 existing rows; found {len(rows)}")

for row in rows:
    row["guidance"] = GUIDANCE

output_columns = original_columns + ["guidance"]

with OUTPUT.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=output_columns)
    writer.writeheader()
    writer.writerows(rows)

print("Original rows preserved:", len(rows))
print("Original columns:", len(original_columns))
print("Output columns:", len(output_columns))
print("Guidance value:", GUIDANCE)
print("Output:", OUTPUT)
print("STRUCTURAL CHECK: PASS")