"""Step 4 - RANK (CLAUDE.md section 5.4). PROPOSED formula agreed in STEP 2 (decision 2).

anomaly severity = clamp(0..1) of 0.6 * magnitude + 0.4 * duration + 0.1 if a linked note supports it
  magnitude: limit  -> fraction beyond the limit / 0.10 (10 % beyond the limit = full), capped at 1
             zscore -> |z| / 6, capped at 1
  duration:  hours / 4 (4 h or longer = full), capped at 1
machine score = max anomaly severity + 0.05 per additional sensor with an anomaly (bonus max 0.1), capped at 1
priority: HIGH >= 0.7 · MEDIUM >= 0.4 · LOW > 0 or only data-quality warnings · OK = no anomalies
queue order: score (high first), ties -> earlier first anomaly, then priority, then machine_id
"""

from datetime import datetime

LIMIT_FULL_SCALE = 0.10
Z_FULL_SCALE = 6.0
DURATION_FULL_HOURS = 4.0
WEIGHT_MAGNITUDE = 0.6
WEIGHT_DURATION = 0.4
NOTE_SUPPORT_BONUS = 0.1
EXTRA_SENSOR_BONUS = 0.05
MAX_EXTRA_SENSOR_BONUS = 0.1
HIGH_THRESHOLD = 0.7
MEDIUM_THRESHOLD = 0.4
PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "OK": 3}
# Context kinds that count as data-quality warnings (an ignored one-off spike does not).
QUALITY_KINDS = {"empty_cell", "unreadable_value", "sensor_error", "gap", "low_raw_rows"}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def magnitude(method: str, magnitude_ratio: float) -> float:
    if method == "limit":
        return clamp(magnitude_ratio / LIMIT_FULL_SCALE)
    return clamp(magnitude_ratio / Z_FULL_SCALE)


def anomaly_severity(method: str, magnitude_ratio: float, duration_hours: float, supported: bool) -> float:
    score = WEIGHT_MAGNITUDE * magnitude(method, magnitude_ratio)
    score += WEIGHT_DURATION * clamp(duration_hours / DURATION_FULL_HOURS)
    if supported:
        score += NOTE_SUPPORT_BONUS
    return round(clamp(score), 3)


def machine_score(severities_by_sensor: dict[str, float]) -> float:
    if not severities_by_sensor:
        return 0.0
    bonus = min(MAX_EXTRA_SENSOR_BONUS, EXTRA_SENSOR_BONUS * (len(severities_by_sensor) - 1))
    return round(clamp(max(severities_by_sensor.values()) + bonus), 3)


def priority(score: float, has_anomalies: bool, has_quality_warnings: bool) -> str:
    if has_anomalies:
        if score >= HIGH_THRESHOLD:
            return "HIGH"
        if score >= MEDIUM_THRESHOLD:
            return "MEDIUM"
        return "LOW"
    return "LOW" if has_quality_warnings else "OK"


def queue_key(score: float, first_start: datetime | None, prio: str, machine_id: str) -> tuple:
    return (-score, first_start or datetime.max, PRIORITY_ORDER[prio], machine_id)
