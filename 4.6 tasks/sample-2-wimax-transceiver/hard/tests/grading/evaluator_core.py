#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "private" / "target_ledger.json"


def sig9(value: float) -> float:
    return float(f"{value:.9g}")


def relative_error(row: dict[str, Any], measurement: float) -> float:
    value = sig9(measurement)
    scale_floor = sig9(float(row["scale_floor"]))
    kind = row["criterion_type"]
    if kind == "valid_range":
        low, high = (sig9(float(item)) for item in row["range"])
        if low <= value <= high:
            return 0.0
        denominator = max(abs(low), abs(high - low), scale_floor)
        return (low - value) / denominator if value < low else (value - high) / denominator
    target = sig9(float(row["target"]))
    denominator = max(abs(target), scale_floor)
    if kind == "central_fixed_point":
        return abs(value - target) / denominator
    if kind == "lower_is_better_fixed_point":
        return max(0.0, (value - target) / denominator)
    if kind == "higher_is_better_fixed_point":
        return max(0.0, (target - value) / denominator)
    raise ValueError(f"unknown criterion type: {kind}")


def criterion_score(error: float, full: float, zero: float) -> float:
    if not math.isfinite(error):
        return 0.0
    if error <= full:
        return 1.0
    if error >= zero:
        return 0.0
    return max(0.0, min(1.0, (zero - error) / (zero - full)))


def grade(
    difficulty: str,
    measurements: dict[str, Any],
    ledger: dict[str, Any],
    gate_violations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if difficulty not in ("mid", "hard", "harder"):
        raise ValueError(f"unknown difficulty: {difficulty}")
    band = ledger["score_bands"][difficulty]
    full = float(band["full_reward_error"])
    zero = float(band["zero_reward_error"])
    rows = []
    weighted_score = 0.0
    total_weight = 0.0
    for criterion in ledger["criteria"]:
        identifier = criterion["id"]
        raw = measurements.get(identifier)
        valid = isinstance(raw, (int, float)) and math.isfinite(float(raw))
        error = relative_error(criterion, float(raw)) if valid else math.inf
        score = criterion_score(error, full, zero) if valid else 0.0
        weight = float(criterion["weights"][difficulty])
        total_weight += weight
        weighted_score += weight * score
        rows.append(
            {
                "id": identifier,
                "description": criterion["description"],
                "unit": criterion["unit"],
                "criterion_type": criterion["criterion_type"],
                "target": criterion.get("target"),
                "range": criterion.get("range"),
                "measurement": sig9(float(raw)) if valid else None,
                "relative_error": sig9(error) if math.isfinite(error) else None,
                "score": sig9(score),
                "weight": weight,
                "status": "PASS" if score == 1.0 else ("FAIL" if score == 0.0 else "PARTIAL"),
            }
        )
    deterministic = weighted_score / total_weight if total_weight else 0.0
    violations = gate_violations or []
    eligible = not violations
    return {
        "difficulty": difficulty,
        "criteria_count": len(rows),
        "reported_criteria_count": len(rows),
        "bands": {"full_reward_error": full, "zero_reward_error": zero},
        "deterministic_score": sig9(deterministic),
        "eligibility_pass": eligible,
        "gate_violations": violations,
        "final_score": sig9(deterministic if eligible else 0.0),
        "production_pass": eligible and all(row["score"] == 1.0 for row in rows),
        "criteria": rows,
    }


def load_measurements(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("measurements", data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("difficulty", choices=("mid", "hard", "harder"))
    parser.add_argument("measurements", type=Path)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    violations: list[dict[str, Any]] = []
    if args.gates:
        gate_data = json.loads(args.gates.read_text(encoding="utf-8"))
        violations = gate_data.get("violations", gate_data)
    result = grade(args.difficulty, load_measurements(args.measurements), ledger, violations)
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
