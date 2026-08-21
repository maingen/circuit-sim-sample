from __future__ import annotations

import math
from typing import Any


BANDS = {
    "mid": (0.25, 0.50),
    "hard": (0.05, 0.25),
    "harder": (0.01, 0.10),
}


def normalized(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("measurement is not finite")
    return float(f"{value:.9g}")


def adverse_error(measurement: float, criterion: dict[str, Any]) -> float:
    measurement = normalized(measurement)
    floor = float(criterion["scale_floor"])
    kind = criterion["criterion_type"]
    if kind == "central_fixed_point":
        target = normalized(float(criterion["target"]))
        return abs(measurement - target) / max(abs(target), floor)
    if kind == "lower_is_better_fixed_point":
        target = normalized(float(criterion["target"]))
        return max(0.0, measurement - target) / max(abs(target), floor)
    if kind == "higher_is_better_fixed_point":
        target = normalized(float(criterion["target"]))
        return max(0.0, target - measurement) / max(abs(target), floor)
    if kind == "valid_range":
        lower = normalized(float(criterion["lower"]))
        upper = normalized(float(criterion["upper"]))
        denominator = max(abs(lower), abs(upper - lower), floor)
        if measurement < lower:
            return (lower - measurement) / denominator
        if measurement > upper:
            return (measurement - upper) / denominator
        return 0.0
    raise ValueError(f"unsupported criterion type: {kind}")


def criterion_score(measurement: float | None, criterion: dict[str, Any], difficulty: str) -> float:
    if measurement is None:
        return 0.0
    try:
        error = adverse_error(float(measurement), criterion)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    full, zero = BANDS[difficulty]
    if error <= full:
        return 1.0
    if error >= zero:
        return 0.0
    return max(0.0, min(1.0, (zero - error) / (zero - full)))


def grade(measurements: dict[str, float | None], ledger: dict[str, Any], difficulty: str) -> dict[str, Any]:
    rows = []
    weighted = 0.0
    weight_total = 0.0
    for criterion in ledger["criteria"]:
        weight = float(criterion["mid_weight"] if difficulty == "mid" else 1.0)
        value = measurements.get(criterion["id"])
        score = criterion_score(value, criterion, difficulty)
        rows.append(
            {
                "id": criterion["id"],
                "measurement": value,
                "score": score,
                "weight": weight,
                "criterion_type": criterion["criterion_type"],
            }
        )
        weighted += weight * score
        weight_total += weight
    return {
        "difficulty": difficulty,
        "score": weighted / weight_total if weight_total else 0.0,
        "criteria": rows,
    }
