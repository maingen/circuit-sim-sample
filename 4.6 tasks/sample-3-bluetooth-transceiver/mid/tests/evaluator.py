from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from fixtures import DERIVED, FIXTURES
from linter import CandidateError, logical_lines, lint, parse_candidate, verify_trusted_pdk
from score import score_measurements


HERE = Path(__file__).resolve().parent
TARGET_LEDGER = Path(os.environ.get("TARGET_LEDGER", HERE / "target_ledger.json"))
PDK_INCLUDE = Path(os.environ.get("SKY130_INCLUDE", "/opt/sky130-pdk/models/sky130_27v_tt.spice"))
PDK_ALLOWLIST = Path(os.environ.get("SKY130_ALLOWLIST", HERE / "sky130_allowlist.json"))
FIXTURE_TIMEOUT = int(os.environ.get("FIXTURE_TIMEOUT_SECONDS", "1800"))
FATAL = re.compile(
    r"fatal|unknown subckt|could not find|can't find|error on line|simulation interrupted|"
    r"timestep too small|measure\s+.*failed|failed!",
    re.I,
)
MEASURE = re.compile(
    r"(?im)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)"
)


def candidate_params(path: Path) -> list[str]:
    source = path.read_text(encoding="utf-8")
    return [line for _, line in logical_lines(source) if line.casefold().startswith(".param")]


def select_elements(
    elements: list[Any], manifest: dict[str, Any], blocks: list[str] | str
) -> list[Any]:
    if blocks == "ALL":
        return elements
    wanted = set()
    for block in blocks:
        wanted.update(str(name).casefold() for name in manifest["blocks"][block]["elements"])
    return [element for element in elements if element.name.casefold() in wanted]


def run_process(command: list[str], cwd: Path, timeout: int) -> tuple[int, bool, str, str, float]:
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    return process.returncode, timed_out, stdout, stderr, time.monotonic() - started


def render_deck(
    params: list[str], elements: list[Any], body: str, raw_path: Path | None = None
) -> str:
    body_lines = body.strip().splitlines()
    if not body_lines or body_lines[-1].strip().casefold() != ".end":
        raise ValueError("private fixture body must end with .end")
    body_lines = body_lines[:-1]
    saved = set()
    for match in re.finditer(r"(?i)\bv\(\s*([^(),\s]+)\s*(?:,\s*([^(),\s]+)\s*)?\)", body):
        saved.add(f"v({match.group(1)})")
        if match.group(2):
            saved.add(f"v({match.group(2)})")
    for match in re.finditer(r"(?i)\bi\(\s*([^(),\s]+)\s*\)", body):
        saved.add(f"i({match.group(1)})")
    lines = [
        "* Private sample-3 candidate characterization deck.",
        f'.include "{PDK_INCLUDE}"',
        *params,
        *(element.raw for element in elements),
        *body_lines,
        *( [".save " + " ".join(sorted(saved))] if saved else [] ),
        ".control",
        "set filetype=ascii",
        "run",
        *( [f"write {raw_path} all"] if raw_path is not None else [] ),
        "quit",
        ".endc",
        ".end",
        "",
    ]
    return "\n".join(lines)


def run_fixture(
    name: str,
    fixture: dict[str, Any],
    params: list[str],
    elements: list[Any],
    manifest: dict[str, Any],
    artifact_dir: Path,
) -> tuple[dict[str, float], dict[str, Any]]:
    fixture_dir = artifact_dir / name
    fixture_dir.mkdir(parents=True, exist_ok=False)
    selected = select_elements(elements, manifest, fixture["blocks"])
    deck_path = fixture_dir / "deck.cir"
    log_path = fixture_dir / "ngspice.log"
    raw_path = fixture_dir / "simulation.raw"
    deck = render_deck(params, selected, fixture["body"], raw_path)
    deck_path.write_text(deck, encoding="utf-8")
    returncode, timed_out, stdout, stderr, elapsed = run_process(
        ["ngspice", "-b", "-o", str(log_path), str(deck_path)],
        PDK_INCLUDE.parents[1],
        FIXTURE_TIMEOUT,
    )
    (fixture_dir / "process.stdout.log").write_text(stdout, encoding="utf-8")
    (fixture_dir / "process.stderr.log").write_text(stderr, encoding="utf-8")
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    parsed = {label.casefold(): float(value) for label, value in MEASURE.findall(log)}
    values = {}
    missing = []
    for criterion_id, label in fixture["measurements"].items():
        value = parsed.get(label.casefold())
        if value is None or not math.isfinite(value):
            missing.append(label)
        else:
            values[criterion_id] = value
    failures = []
    if returncode != 0:
        failures.append(f"ngspice exit {returncode}")
    if timed_out:
        failures.append("timeout")
    if not log:
        failures.append("missing log")
    if not raw_path.is_file() or raw_path.stat().st_size == 0:
        failures.append("missing raw data")
    if FATAL.search(log):
        failures.append("fatal simulator diagnostic")
    if missing:
        failures.append(f"missing measurements: {', '.join(sorted(missing))}")
    report = {
        "fixture": name,
        "blocks": fixture["blocks"],
        "selected_element_count": len(selected),
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 6),
        "measurements": values,
        "raw_data": {
            "path": str(raw_path),
            "size_bytes": raw_path.stat().st_size if raw_path.is_file() else 0,
            "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest() if raw_path.is_file() else None,
        },
        "failures": failures,
        "passed": not failures,
    }
    (fixture_dir / "fixture_result.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return values, report


class SafeExpression(ast.NodeVisitor):
    ALLOWED_BINARY = (ast.Add, ast.Sub, ast.Mult, ast.Div)
    ALLOWED_UNARY = (ast.UAdd, ast.USub)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> float:
        if not isinstance(node.value, (int, float)):
            raise ValueError("non-numeric constant")
        return float(node.value)

    def visit_Name(self, node: ast.Name) -> float:
        if node.id not in self.values:
            raise KeyError(node.id)
        return float(self.values[node.id])

    def visit_BinOp(self, node: ast.BinOp) -> float:
        if not isinstance(node.op, self.ALLOWED_BINARY):
            raise ValueError("forbidden binary operator")
        left = self.visit(node.left)
        right = self.visit(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right

    def visit_UnaryOp(self, node: ast.UnaryOp) -> float:
        if not isinstance(node.op, self.ALLOWED_UNARY):
            raise ValueError("forbidden unary operator")
        value = self.visit(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value

    def visit_Call(self, node: ast.Call) -> float:
        if not isinstance(node.func, ast.Name) or node.func.id not in {"abs", "log10"}:
            raise ValueError("forbidden function")
        if len(node.args) != 1 or node.keywords:
            raise ValueError("invalid function call")
        value = self.visit(node.args[0])
        return abs(value) if node.func.id == "abs" else math.log10(value)

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"forbidden expression node: {type(node).__name__}")

    def evaluate(self, expression: str, values: dict[str, float]) -> float:
        self.values = values
        return float(self.visit(ast.parse(expression, mode="eval")))


def derive_measurements(values: dict[str, float]) -> None:
    evaluator = SafeExpression()
    pending = dict(DERIVED)
    while pending:
        progressed = False
        for identifier, expression in list(pending.items()):
            try:
                value = evaluator.evaluate(expression, values)
            except KeyError:
                continue
            values[identifier] = value
            del pending[identifier]
            progressed = True
        if not progressed:
            break


def grade_submission(
    candidate: Path,
    architecture: Path,
    artifact_dir: Path,
    difficulty: str,
    starter_sha256: str | None = None,
) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=False)
    try:
        pdk_verification = verify_trusted_pdk(PDK_INCLUDE.parents[1], PDK_ALLOWLIST)
    except (OSError, ValueError, json.JSONDecodeError, CandidateError) as exc:
        ledger = json.loads(TARGET_LEDGER.read_text(encoding="utf-8"))
        return score_measurements(
            difficulty,
            ledger["criteria"],
            {},
            [{"code": "PDK_INTEGRITY", "detail": str(exc), "mandatory": True}],
        ) | {"pdk_verification": {"passed": False, "detail": str(exc)}, "fixture_reports": []}
    lint_result = lint(candidate, architecture, starter_sha256)
    (artifact_dir / "lint.json").write_text(
        json.dumps(lint_result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    ledger = json.loads(TARGET_LEDGER.read_text(encoding="utf-8"))
    criteria = ledger["criteria"]
    if not lint_result["eligible"]:
        return score_measurements(
            difficulty, criteria, {}, lint_result.get("mandatory_findings", [])
        ) | {"lint": lint_result, "pdk_verification": pdk_verification, "fixture_reports": []}

    elements, _, _ = parse_candidate(candidate)
    manifest = json.loads(architecture.read_text(encoding="utf-8"))
    params = candidate_params(candidate)
    measurements: dict[str, float] = {}
    fixture_reports = []
    gate_findings = []
    for name, fixture in FIXTURES.items():
        values, report = run_fixture(
            name, fixture, params, elements, manifest, artifact_dir
        )
        measurements.update(values)
        fixture_reports.append(report)
        if not report["passed"]:
            gate_findings.append(
                {
                    "code": "REQUIRED_SIMULATION_FAILURE",
                    "fixture": name,
                    "detail": report["failures"],
                    "mandatory": True,
                }
            )
    derive_measurements(measurements)
    criterion_by_id = {item["id"]: item for item in criteria}
    for identifier, criterion in criterion_by_id.items():
        if criterion.get("transform") == "absolute" and identifier in measurements:
            measurements[identifier] = abs(measurements[identifier])
    missing = sorted(set(criterion_by_id) - set(measurements))
    if missing:
        gate_findings.append(
            {
                "code": "REQUIRED_MEASUREMENT_MISSING",
                "detail": missing,
                "mandatory": True,
            }
        )
    score = score_measurements(difficulty, criteria, measurements, gate_findings)
    score.update(
        {
            "lint": lint_result,
            "measurements": measurements,
            "fixture_reports": fixture_reports,
            "target_ledger_replay_id": ledger["reference_replay_id"],
            "pdk_verification": pdk_verification,
        }
    )
    return score


def grade_trusted_reference(measurements_path: Path, difficulty: str) -> dict[str, Any]:
    ledger = json.loads(TARGET_LEDGER.read_text(encoding="utf-8"))
    measurements = json.loads(measurements_path.read_text(encoding="utf-8"))
    criteria = ledger["criteria"]
    return score_measurements(difficulty, criteria, measurements, [])
