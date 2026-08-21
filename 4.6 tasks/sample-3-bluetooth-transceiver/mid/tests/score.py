from __future__ import annotations

import math
from typing import Any


BANDS = {
    "mid": (0.25, 0.50),
    "hard": (0.05, 0.25),
    "harder": (0.01, 0.10),
}


def round_significant(value: float, digits: int = 9) -> float:
    if not math.isfinite(value) or value == 0.0:
        return value
    return round(value, digits - int(math.floor(math.log10(abs(value)))) - 1)


def adverse_error(criterion: dict[str, Any], measured: float) -> float:
    measured = round_significant(float(measured))
    scale_floor = round_significant(float(criterion["scale_floor"]))
    kind = str(criterion["criterion_type"])
    if kind == "central_fixed_point":
        target = round_significant(float(criterion["target"]))
        return abs(measured - target) / max(abs(target), scale_floor)
    if kind == "lower_is_better_fixed_point":
        target = round_significant(float(criterion["target"]))
        return max(0.0, (measured - target) / max(abs(target), scale_floor))
    if kind == "higher_is_better_fixed_point":
        target = round_significant(float(criterion["target"]))
        return max(0.0, (target - measured) / max(abs(target), scale_floor))
    if kind == "valid_range":
        lower = round_significant(float(criterion["lower"]))
        upper = round_significant(float(criterion["upper"]))
        if lower <= measured <= upper:
            return 0.0
        if measured < lower:
            denominator = max(abs(lower), abs(upper - lower), scale_floor)
            return (lower - measured) / denominator
        denominator = max(abs(upper), abs(upper - lower), scale_floor)
        return (measured - upper) / denominator
    raise ValueError(f"unsupported criterion type: {kind}")


def criterion_score(error: float, full_error: float, zero_error: float) -> float:
    if not math.isfinite(error) or error >= zero_error:
        return 0.0
    if error <= full_error:
        return 1.0
    return max(0.0, min(1.0, (zero_error - error) / (zero_error - full_error)))


def score_measurements(
    difficulty: str,
    criteria: list[dict[str, Any]],
    measurements: dict[str, float],
    gate_findings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if difficulty not in BANDS:
        raise ValueError(f"unsupported difficulty: {difficulty}")
    full_error, zero_error = BANDS[difficulty]
    reports = []
    weighted_sum = 0.0
    weight_sum = 0.0
    for criterion in criteria:
        criterion_id = str(criterion["id"])
        if difficulty == "mid":
            weight = 1.0 if criterion.get("essential", False) else 0.5
        else:
            weight = 1.0
        raw = measurements.get(criterion_id)
        finite = raw is not None and math.isfinite(float(raw))
        if finite:
            measured = round_significant(float(raw))
            error = adverse_error(criterion, measured)
            reward = criterion_score(error, full_error, zero_error)
            status = "PASS" if reward == 1.0 else "PARTIAL" if reward > 0.0 else "FAIL"
        else:
            measured = None
            error = None
            reward = 0.0
            status = "MISSING_OR_NONFINITE"
        weighted_sum += weight * reward
        weight_sum += weight
        reports.append(
            {
                "id": criterion_id,
                "description": criterion["description"],
                "criterion_type": criterion["criterion_type"],
                "unit": criterion["unit"],
                "target": criterion.get("target"),
                "lower": criterion.get("lower"),
                "upper": criterion.get("upper"),
                "scale_floor": criterion["scale_floor"],
                "measured": measured,
                "adverse_error": error,
                "weight": weight,
                "criterion_reward": reward,
                "weighted_contribution": weight * reward,
                "status": status,
            }
        )
    raw_score = weighted_sum / weight_sum if weight_sum else 0.0
    gates = gate_findings or []
    gate_failed = any(bool(item.get("mandatory", True)) for item in gates)
    final_score = 0.0 if gate_failed else raw_score
    return {
        "difficulty": difficulty,
        "full_reward_error": full_error,
        "zero_reward_error": zero_error,
        "criteria": reports,
        "raw_deterministic_score": raw_score,
        "gate_findings": gates,
        "mandatory_gate_pass": not gate_failed,
        "final_deterministic_score": final_score,
        "artifact_evaluable": not gate_failed,
        "production_pass": math.isclose(final_score, 1.0, abs_tol=1e-12),
    }
