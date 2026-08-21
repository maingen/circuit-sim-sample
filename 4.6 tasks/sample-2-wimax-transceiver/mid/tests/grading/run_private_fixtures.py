#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from contract import BLOCK_PORTS, REQUIRED_FILES
from evaluator_core import grade
from extract_measurements import extract_measurements
from lint_candidate import lint_submission, logical_lines


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "private" / "fixtures"
DEFAULT_LEDGER = ROOT / "private" / "target_ledger.json"
DEFAULT_PDK = Path("/opt/sky130/sky130_tt_1v8.spice")
BAD_LOG = re.compile(r"(?i)(fatal error|simulation interrupted|could not find a valid modelname|measure .* failed|no such vector)")


def replace_ground_nodes(line: str, wrappers: set[str]) -> str:
    tokens = line.split()
    if not tokens or tokens[0].startswith("."):
        return line
    prefix = tokens[0][0].upper()
    node_indexes: list[int] = []
    if prefix in {"R", "L", "C"}:
        node_indexes = [1, 2]
    elif prefix in {"M"}:
        node_indexes = [1, 2, 3, 4]
    elif prefix == "Q":
        node_indexes = list(range(1, max(1, len(tokens) - 1)))
    elif prefix == "X":
        model_index = next((index for index, token in enumerate(tokens[1:], 1) if token in wrappers), None)
        if model_index is None:
            raise ValueError(f"cannot locate allowed X wrapper in {line}")
        node_indexes = list(range(1, model_index))
    for index in node_indexes:
        if tokens[index] == "0":
            tokens[index] = "vss_candidate"
    return " ".join(tokens)


def build_wrappers(submission: Path, rows: list[dict[str, str]], destination: Path, allowed_wrappers: set[str]) -> None:
    chunks = ["* Private wrapper hierarchy around flattened candidate fragments."]
    for row in rows:
        wrapper = row["wrapper"]
        block = row["block"]
        path = submission / REQUIRED_FILES[block]
        ports = ["vss_candidate" if port == "0" else port for port in BLOCK_PORTS[block]]
        chunks.append(f".subckt {wrapper} {' '.join(ports)}")
        for _, line in logical_lines(path.read_text(encoding="utf-8")):
            chunks.append(replace_ground_nodes(line, allowed_wrappers))
        chunks.append(f".ends {wrapper}")
    destination.write_text("\n".join(chunks) + "\n", encoding="utf-8")


def run_ngspice(deck: Path, log: Path, cwd: Path, timeout: int) -> dict[str, Any]:
    deck = deck.resolve()
    log = log.resolve()
    cwd = cwd.resolve()
    try:
        completed = subprocess.run(
            ["ngspice", "-b", "-o", str(log), str(deck)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        text = log.read_text(errors="replace") if log.is_file() else ""
        bad = BAD_LOG.search(text)
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "error_signature": bad.group(0) if bad else None,
            "passed": completed.returncode == 0 and bad is None and log.is_file(),
        }
    except subprocess.TimeoutExpired as exc:
        return {"returncode": None, "passed": False, "timeout": timeout, "error": str(exc)}


def grade_submission(
    submission: Path,
    output: Path,
    difficulty: str,
    fixtures: Path = DEFAULT_FIXTURES,
    ledger_path: Path = DEFAULT_LEDGER,
    pdk_wrapper: Path = DEFAULT_PDK,
    trusted_reference_calibration: bool = False,
) -> dict[str, Any]:
    submission = submission.resolve()
    output = output.resolve()
    fixtures = fixtures.resolve()
    ledger_path = ledger_path.resolve()
    pdk_wrapper = pdk_wrapper.resolve()
    output.mkdir(parents=True, exist_ok=True)
    run_root = output / "simulation-artifacts"
    logs = run_root / "logs"
    raw = run_root / "raw"
    decks = run_root / "decks"
    wrappers_dir = run_root / "wrappers"
    for directory in (logs, raw, decks, wrappers_dir):
        directory.mkdir(parents=True, exist_ok=True)

    lint = lint_submission(submission)
    (output / "lint.json").write_text(json.dumps(lint, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate_violations = list(lint["violations"])
    fixture_results: dict[str, Any] = {}

    if not pdk_wrapper.is_file():
        gate_violations.append({"code": "PDK_MISSING", "detail": str(pdk_wrapper)})
    else:
        smoke_template = (fixtures / "sky130_smoke.sp").read_text(encoding="utf-8")
        smoke_deck = decks / "sky130_smoke.sp"
        smoke_deck.write_text(
            smoke_template.replace("/opt/sky130/sky130_tt_1v8.spice", str(pdk_wrapper.resolve())),
            encoding="utf-8",
        )
        fixture_results["sky130_smoke.sp"] = run_ngspice(smoke_deck, logs / "sky130_smoke.log", run_root, 120)
        if not fixture_results["sky130_smoke.sp"]["passed"]:
            gate_violations.append({"code": "PDK_SMOKE_FAILURE", "detail": fixture_results["sky130_smoke.sp"]})

    if lint["eligible"] and pdk_wrapper.is_file():
        plan = json.loads((fixtures / "fixture_plan.json").read_text(encoding="utf-8"))
        allowlist = json.loads((ROOT / "grading" / "strict_sky130_allowlist.json").read_text(encoding="utf-8"))
        allowed_wrappers = set(allowlist["allowed_single_transistor_x_wrappers"])
        for name, row in plan["fixtures"].items():
            wrapper_path = wrappers_dir / f"{Path(name).stem}_wrappers.spice"
            build_wrappers(submission, row["wrappers"], wrapper_path, allowed_wrappers)
            template = (fixtures / row["template"]).read_text(encoding="utf-8")
            deck_text = template.replace("@@WRAPPERS@@", str(wrapper_path.resolve()))
            deck_text = deck_text.replace("/opt/sky130/sky130_tt_1v8.spice", str(pdk_wrapper.resolve()))
            deck_path = decks / name
            deck_path.write_text(deck_text, encoding="utf-8")
            fixture_results[name] = run_ngspice(
                deck_path,
                logs / name.replace(".sp", ".log"),
                run_root,
                int(row["timeout_seconds"]),
            )
        failed = [name for name, row in fixture_results.items() if not row["passed"]]
        if failed:
            gate_violations.append({"code": "REQUIRED_SIMULATION_FAILURE", "detail": failed})

    measurements, extraction_errors = extract_measurements(run_root)
    (output / "measurements.json").write_text(
        json.dumps({"measurements": measurements, "extraction_errors": extraction_errors}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for identifier, limit in [
        ("pa_thin_oxide_drain_max_v", 1.98),
        ("pa_extended_drain_max_v", 10.5),
        ("tx_core_pa_drain_max_v", 10.5),
        ("system_pa_drain_max_v", 10.5),
    ]:
        value = measurements.get(identifier)
        if (
            isinstance(value, (int, float))
            and float(value) > limit
            and not (trusted_reference_calibration and identifier == "pa_thin_oxide_drain_max_v")
        ):
            gate_violations.append(
                {"code": "DYNAMIC_OVERSTRESS", "metric": identifier, "measurement": value, "limit": limit}
            )

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    result = grade(difficulty, measurements, ledger, gate_violations)
    result.update(
        {
            "artifact_evaluable": bool(measurements),
            "lint": lint,
            "fixture_results": fixture_results,
            "extraction_errors": extraction_errors,
            "trusted_reference_calibration": trusted_reference_calibration,
            "trusted_reference_safety_exception": (
                {
                    "metric": "pa_thin_oxide_drain_max_v",
                    "limit_v": 1.98,
                    "reason": "The frozen reference itself violates this candidate safety gate; the exception is calibration-only.",
                }
                if trusted_reference_calibration
                else None
            ),
        }
    )
    (output / "fixture_results.json").write_text(json.dumps(fixture_results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "grade.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("difficulty", choices=("mid", "hard", "harder"))
    parser.add_argument("submission", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--pdk-wrapper", type=Path, default=DEFAULT_PDK)
    parser.add_argument(
        "--trusted-reference-calibration",
        action="store_true",
        help="Waive only the frozen reference's documented thin-oxide PA overstress gate.",
    )
    args = parser.parse_args()
    result = grade_submission(
        args.submission,
        args.output,
        args.difficulty,
        args.fixtures,
        args.ledger,
        args.pdk_wrapper,
        args.trusted_reference_calibration,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
