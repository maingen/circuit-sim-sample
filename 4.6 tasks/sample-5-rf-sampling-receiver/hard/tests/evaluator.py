#!/usr/bin/env python3
"""Private NGspice evaluator for the sample 5 reconstruction benchmark."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from lint_candidate import lint_submission
from scoring import load_json, score_measurements


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1] if HERE.name == "common" else HERE
DEFAULT_FIXTURES = PACKAGE / "private" / "fixtures"
DEFAULT_LEDGER = PACKAGE / "private" / "targets" / "target_ledger.json"
DEFAULT_REFERENCE = PACKAGE / "private" / "targets" / "reference_measurements.json"
DEFAULT_PDK = PACKAGE.parent / "sky130-rf-sampling-receiver" / "pdk" / "sky130-ngspice-models" / "libs.tech" / "ngspice" / "sky130.lib.spice"
METRIC_PATTERN = re.compile(r"(?im)^\s*([a-z][a-z0-9_]+)\s*=\s*([-+0-9.eE]+)")


def clean_candidate_source(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if line.strip().casefold() != ".end"]
    return "\n".join(kept) + "\n"


def assemble_deck(candidate: Path, fixture: Path, pdk_library: Path) -> str:
    return (
        f"Sample 5 private fixture {fixture.stem}\n"
        f'.lib "{pdk_library}" tt\n'
        + clean_candidate_source(candidate)
        + "\n"
        + fixture.read_text(encoding="utf-8")
    )


def parse_log_metrics(text: str, wanted: list[str]) -> dict[str, float]:
    found: dict[str, float] = {}
    wanted_set = {item.casefold() for item in wanted}
    for name, raw in METRIC_PATTERN.findall(text):
        if name.casefold() in wanted_set:
            try:
                value = float(raw)
            except ValueError:
                continue
            if math.isfinite(value):
                found[name.casefold()] = value
    return found


def load_wrdata(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for raw in path.read_text(errors="ignore").splitlines():
        if not raw.strip():
            continue
        try:
            values = [float(item) for item in raw.split()]
        except ValueError:
            continue
        if values:
            rows.append(values)
    if not rows:
        raise ValueError(f"no numeric data in {path}")
    return rows


def select_wrdata_values(rows: list[list[float]], vector_count: int) -> list[list[float]]:
    width = min(len(row) for row in rows)
    if width >= vector_count * 2:
        indices = [2 * i + 1 for i in range(vector_count)]
    elif width >= vector_count:
        indices = list(range(vector_count))
    else:
        raise ValueError(f"wrdata has {width} columns, expected at least {vector_count}")
    return [[row[index] for index in indices] for row in rows]


def interpolate(t: list[float], y: list[float], x: float, cursor: int) -> tuple[float, int]:
    while cursor + 1 < len(t) and t[cursor + 1] < x:
        cursor += 1
    if cursor + 1 >= len(t):
        return y[-1], len(t) - 2
    span = t[cursor + 1] - t[cursor]
    fraction = 0.0 if span == 0 else (x - t[cursor]) / span
    return y[cursor] + fraction * (y[cursor + 1] - y[cursor]), cursor


def solve4(matrix: list[list[float]], vector: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for pivot in range(4):
        best = max(range(pivot, 4), key=lambda row: abs(augmented[row][pivot]))
        if abs(augmented[best][pivot]) < 1e-24:
            raise ValueError("singular fit")
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        scale = augmented[pivot][pivot]
        augmented[pivot] = [value / scale for value in augmented[pivot]]
        for row in range(4):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[pivot])]
    return [augmented[row][4] for row in range(4)]


def fit_wave(times: list[float], values: list[float]) -> tuple[float, float, float]:
    center = sum(times) / len(times)
    basis = [
        [math.cos(2 * math.pi * 1e6 * t), math.sin(2 * math.pi * 1e6 * t), 1.0, (t - center) / 1e-6]
        for t in times
    ]
    gram = [[sum(row[i] * row[j] for row in basis) for j in range(4)] for i in range(4)]
    rhs = [sum(row[i] * value for row, value in zip(basis, values)) for i in range(4)]
    coefficients = solve4(gram, rhs)
    amplitude = math.hypot(coefficients[0], coefficients[1])
    phase = math.degrees(math.atan2(-coefficients[1], coefficients[0]))
    return amplitude, phase, coefficients[2]


def iq_metrics(path: Path, prefix: str, start: float) -> dict[str, float]:
    rows = select_wrdata_values(load_wrdata(path), 4)
    t = [row[0] for row in rows]
    i_wave = [row[1] for row in rows]
    q_wave = [row[2] for row in rows]
    adc = [row[3] for row in rows]
    edge_times = [t[index + 1] + 8e-9 for index in range(len(t) - 1) if adc[index] < 0.9 <= adc[index + 1]]
    samples = [value for value in edge_times if start <= value <= min(1.2e-6, t[-1])]
    if len(samples) < 20:
        raise ValueError(f"only {len(samples)} ADC-edge samples")
    cursor_i = 0
    cursor_q = 0
    i_values: list[float] = []
    q_values: list[float] = []
    for sample in samples:
        value, cursor_i = interpolate(t, i_wave, sample, cursor_i)
        i_values.append(value)
        value, cursor_q = interpolate(t, q_wave, sample, cursor_q)
        q_values.append(value)
    i_amp, i_phase, _ = fit_wave(samples, i_values)
    q_amp, q_phase, _ = fit_wave(samples, q_values)
    phase_delta = (q_phase - i_phase + 180.0) % 360.0 - 180.0
    result = {
        f"{prefix}_i_amplitude_v": i_amp,
        f"{prefix}_q_amplitude_v": q_amp,
        f"{prefix}_iq_phase_delta_deg": phase_delta,
        f"{prefix}_iq_amplitude_imbalance_db": 20.0 * math.log10(q_amp / i_amp),
    }
    if prefix == "rfsd":
        result["rfsd_i_conversion_gain_db"] = 20.0 * math.log10(i_amp / 0.2)
        result["rfsd_q_conversion_gain_db"] = 20.0 * math.log10(q_amp / 0.2)
    return result


def rf_metrics(path: Path) -> dict[str, float]:
    rows = load_wrdata(path)
    frequency = [row[0] for row in rows]
    gain = [row[-1] for row in rows]
    peak = max(range(len(gain)), key=lambda index: gain[index])
    threshold = gain[peak] - 3.0
    low = peak
    high = peak
    while low > 0 and gain[low - 1] >= threshold:
        low -= 1
    while high + 1 < len(gain) and gain[high + 1] >= threshold:
        high += 1
    return {
        "rf_frontend_peak_frequency_hz": frequency[peak],
        "rf_frontend_bandwidth_hz": frequency[high] - frequency[low],
    }


def run_fixture(
    submission: Path,
    fixture_path: Path,
    config: dict[str, Any],
    run_root: Path,
    pdk_library: Path,
    ngspice: str,
) -> tuple[dict[str, float], dict[str, Any]]:
    stem = fixture_path.stem
    run_dir = (run_root / stem).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    deck = run_dir / "deck.cir"
    deck.write_text(assemble_deck(submission / config["artifact"], fixture_path, pdk_library), encoding="utf-8")
    log = run_dir / "ngspice.log"
    timeout = 7200 if stem in {"rfsd_core", "full_receiver"} else 1800
    try:
        completed = subprocess.run(
            [ngspice, "-b", "-o", str(log), str(deck)],
            cwd=run_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        status = completed.returncode
        stderr = completed.stderr[-4000:]
    except subprocess.TimeoutExpired as exc:
        status = 124
        stderr = f"timeout after {timeout}s: {exc}"
    text = log.read_text(errors="ignore") if log.exists() else ""
    success = status == 0 and "FIXTURE_COMPLETE" in text and not re.search(r"(?im)(^|\s)error:|failed!", text)
    measured = parse_log_metrics(text, config["metrics"]) if success else {}
    try:
        if success and stem == "rf_frontend":
            measured.update(rf_metrics(run_dir / "rf_frontend.dat"))
        elif success and stem == "rfsd_core":
            measured.update(iq_metrics(run_dir / "iq.dat", "rfsd", 0.30e-6))
        elif success and stem == "full_receiver":
            measured.update(iq_metrics(run_dir / "iq.dat", "full", 0.30e-6))
    except Exception as exc:
        success = False
        stderr = (stderr + f"\npostprocess failure: {exc}").strip()
    return measured, {
        "fixture": fixture_path.name,
        "artifact": config["artifact"],
        "returncode": status,
        "success": success,
        "stderr_tail": stderr,
        "log": str(log),
        "metrics_found": sorted(measured),
    }


def evaluate_submission(
    submission: Path,
    difficulty: str,
    output: Path,
    fixtures_dir: Path = DEFAULT_FIXTURES,
    ledger_path: Path = DEFAULT_LEDGER,
    pdk_library: Path = DEFAULT_PDK,
    ngspice: str = "/opt/homebrew/bin/ngspice",
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    lint = lint_submission(submission)
    (output / "lint.json").write_text(json.dumps(lint, indent=2, sort_keys=True) + "\n")
    manifest = load_json(fixtures_dir / "manifest.json")
    measurements: dict[str, float] = {}
    runs: list[dict[str, Any]] = []
    if lint["eligible"]:
        run_root = output / "simulation-artifacts"
        for fixture_name, config in manifest.items():
            found, run = run_fixture(submission, fixtures_dir / fixture_name, config, run_root, pdk_library, ngspice)
            measurements.update(found)
            runs.append(run)
    all_runs_pass = len(runs) == len(manifest) and all(item["success"] for item in runs)
    gates = [
        {"id": "static_eligibility", "pass": bool(lint["eligible"]), "evidence": "lint.json"},
        {"id": "all_private_simulations", "pass": all_runs_pass, "evidence": "simulation-artifacts"},
        {"id": "all_required_metrics", "pass": all(name in measurements for config in manifest.values() for name in config["metrics"]), "evidence": "measurements.json"},
    ]
    ledger = load_json(ledger_path)
    scored = score_measurements(ledger, measurements, difficulty, gates)
    result = {**scored, "measurements": measurements, "lint": lint, "simulation_runs": runs}
    (output / "measurements.json").write_text(json.dumps(measurements, indent=2, sort_keys=True) + "\n")
    (output / "details.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def reference_self_test(difficulty: str, output: Path, ledger_path: Path, reference_path: Path) -> dict[str, Any]:
    ledger = load_json(ledger_path)
    measurements = load_json(reference_path)
    gates = [
        {"id": "reference_replay_success", "pass": True, "evidence": "private/reference_replay"},
        {"id": "reference_provenance", "pass": True, "evidence": "private/hashes/reference-files.json"},
    ]
    result = score_measurements(ledger, measurements, difficulty, gates)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path, nargs="?")
    parser.add_argument("--difficulty", choices=["mid", "hard", "harder"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--reference-measurements", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--pdk-library", type=Path, default=Path(os.environ.get("SKY130_LIB", DEFAULT_PDK)))
    parser.add_argument("--ngspice", default=os.environ.get("NGSPICE_BIN", "/opt/homebrew/bin/ngspice"))
    parser.add_argument("--reference-self-test", action="store_true")
    args = parser.parse_args()
    if args.reference_self_test:
        result = reference_self_test(args.difficulty, args.output, args.ledger, args.reference_measurements)
    else:
        if args.submission is None:
            parser.error("submission is required unless --reference-self-test is used")
        result = evaluate_submission(args.submission, args.difficulty, args.output, args.fixtures, args.ledger, args.pdk_library, args.ngspice)
    print(json.dumps({
        "difficulty": args.difficulty,
        "raw_deterministic_score": result["raw_deterministic_score"],
        "final_deterministic_score": result["final_deterministic_score"],
        "mandatory_gates_pass": result["mandatory_gates_pass"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
