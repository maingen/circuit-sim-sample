#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
MODEL_SHA256 = "6cb4327c4fa5d00af4eff9805e6a22689ac75939e3d173f0ae1b44dd4a522a99"
BASE_DIGEST = "sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    required = (
        "instruction.md", "task.toml", "environment/Dockerfile",
        "environment/candidate.cir", "environment/docker-compose.yaml",
        "environment/cmos018-s112b.lib", "solution/reference-a.cir",
        "tests/Dockerfile", "tests/docker-compose.yaml", "tests/evaluator.py",
        "tests/grade.py", "tests/test.sh", "tests/test_evaluator.py",
    )
    for relative in required:
        require((PACKAGE / relative).is_file(), f"missing required file: {relative}")
    model = PACKAGE / "environment/cmos018-s112b.lib"
    require(hashlib.sha256(model.read_bytes()).hexdigest() == MODEL_SHA256, "model hash mismatch")

    instruction = (PACKAGE / "instruction.md").read_text(encoding="utf-8")
    for text in (
        "45.56 V/V", "10 MHz", "82.72 MHz", "47.51 V/V", "0.004032 percent",
        "92 kOhm", "8 kOhm", "feedback factor of", "0.08", "97 and 100 percent",
        "200 uA", "final 5 ms", "harmonics through the fifth",
        ".subckt candidate in out vdd vss", "Ngspice 46",
    ):
        require(text in instruction, f"instruction is missing required contract text: {text}")
    for leaked in (
        "Scoring type", "Production measurements", "## Reward", "central target",
        "lower-is-better", "higher-is-better", "criterion reward", "scalar", "multiplicative",
    ):
        require(leaked.casefold() not in instruction.casefold(), f"instruction leaks private grading language: {leaked}")
    for precise in ("45.563989081", "82728255.013", "47.510692006", "0.004031312244"):
        require(precise not in instruction, f"instruction leaks an overprecise target: {precise}")

    reference = (PACKAGE / "solution/reference-a.cir").read_bytes()
    starter = (PACKAGE / "environment/candidate.cir").read_bytes()
    require(reference != starter, "starter exposes the passing reference")
    agent_dockerfile = (PACKAGE / "environment/Dockerfile").read_text(encoding="utf-8")
    require("solution/reference-a.cir" not in agent_dockerfile, "agent image leaks the reference")
    for relative in ("environment/Dockerfile", "tests/Dockerfile"):
        require(BASE_DIGEST in (PACKAGE / relative).read_text(encoding="utf-8"), f"{relative} does not pin the shared baseline")

    evaluator = (PACKAGE / "tests/evaluator.py").read_text(encoding="utf-8")
    require("tran {TRANSIENT_STEP_SECONDS} {TRANSIENT_STOP_SECONDS} {TRANSIENT_START_SECONDS}" in evaluator, "production grader does not run transient analysis")
    require("range(1, 6)" in evaluator, "transient THD does not cover harmonics through the fifth")
    require("require_topology(elements)" in evaluator, "required topology is not enforced")
    require("LOADED_RATIO_MINIMUM = 0.97" in evaluator, "loaded-gain comparison is not enforced")
    require("the feedback divider midpoint must remain open" in evaluator, "open feedback topology is not enforced")
    require("production_pass = final_reward == 1.0" in evaluator, "production pass is not exact reward 1.0")

    environment = os.environ.copy()
    environment.update({
        "EESIM_CMOS_MODEL": str(model),
        "EESIM_REFERENCE": str(PACKAGE / "solution/reference-a.cir"),
        "PYTHONPATH": str(PACKAGE / "tests"),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    with tempfile.TemporaryDirectory() as directory:
        completed = subprocess.run(
            [sys.executable, str(PACKAGE / "tests/test_evaluator.py")],
            cwd=directory, env=environment, capture_output=True, text=True,
            timeout=180, check=False,
        )
    require(completed.returncode == 0, completed.stdout + completed.stderr)
    print("Open-feedback CMOS amplifier Harbor package verification passed")


if __name__ == "__main__":
    main()
