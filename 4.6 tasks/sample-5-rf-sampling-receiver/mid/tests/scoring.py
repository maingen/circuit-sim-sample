#!/usr/bin/env python3
"""Deterministic nine-significant-digit benchmark scoring."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


BANDS = {
    "mid": (0.25, 0.50),
    "hard": (0.05, 0.25),
    "harder": (0.01, 0.10),
}


def sig9(value: float) -> float:
    if not math.isfinite(value) or value == 0.0:
        return value
    return float(f"{value:.9g}")


def adverse_error(criterion: dict[str, Any], measured: float) -> float:
    kind = criterion["criterion_type"]
    m = sig9(float(measured))
    floor = sig9(float(criterion["scale_floor"]))
    if kind == "central":
        target = sig9(float(criterion["target"]))
        return abs(m - target) / max(abs(target), floor)
    if kind == "lower":
        target = sig9(float(criterion["target"]))
        return max(0.0, (m - target) / max(abs(target), floor))
    if kind == "higher":
        target = sig9(float(criterion["target"]))
        return max(0.0, (target - m) / max(abs(target), floor))
    if kind == "range":
        low = sig9(float(criterion["low"]))
        high = sig9(float(criterion["high"]))
        denominator = max(abs(low), abs(high - low), floor)
        if m < low:
            return (low - m) / denominator
        if m > high:
            return (m - high) / denominator
        return 0.0
    raise ValueError(f"unknown criterion type {kind}")


def criterion_score(error: float, full: float, zero: float) -> float:
    if not math.isfinite(error):
        return 0.0
    if error <= full:
        return 1.0
    if error >= zero:
        return 0.0
    return max(0.0, min(1.0, (zero - error) / (zero - full)))


def score_measurements(
    ledger: dict[str, Any], measurements: dict[str, Any], difficulty: str, gates: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    if difficulty not in BANDS:
        raise ValueError(f"unknown difficulty {difficulty}")
    full, zero = BANDS[difficulty]
    rows: list[dict[str, Any]] = []
    weighted = 0.0
    total_weight = 0.0
    for criterion in ledger["criteria"]:
        name = criterion["id"]
        weight = float(criterion.get("mid_weight", 1.0)) if difficulty == "mid" else 1.0
        total_weight += weight
        raw = measurements.get(name)
        missing = raw is None
        try:
            measured = sig9(float(raw))
            finite = math.isfinite(measured)
        except (TypeError, ValueError):
            measured = None
            finite = False
        if missing or not finite:
            error = None
            reward = 0.0
        else:
            error = adverse_error(criterion, measured)
            reward = criterion_score(error, full, zero)
        weighted += weight * reward
        rows.append({
            "id": name,
            "description": criterion["description"],
            "criterion_type": criterion["criterion_type"],
            "unit": criterion["unit"],
            "target": criterion.get("target"),
            "low": criterion.get("low"),
            "high": criterion.get("high"),
            "measured": measured,
            "adverse_error": error,
            "full_credit_error": full,
            "zero_credit_error": zero,
            "weight": weight,
            "score": reward,
            "status": "PASS" if reward == 1.0 else ("FAIL" if reward == 0.0 else "PARTIAL"),
        })
    gate_rows = list(gates or [])
    gate_pass = all(bool(item.get("pass")) for item in gate_rows)
    raw_score = weighted / total_weight if total_weight else 0.0
    return {
        "difficulty": difficulty,
        "raw_deterministic_score": raw_score,
        "final_deterministic_score": raw_score if gate_pass else 0.0,
        "mandatory_gates_pass": gate_pass,
        "gates": gate_rows,
        "criteria": rows,
    }


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

