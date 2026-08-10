#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
MODEL_SHA256 = "02094fb8acf1927012eda6dc59941cbf236ef8f7544bd39e166b3e202f2bb8ec"
BASE_DIGEST = "sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    required = (
        "instruction.md", "task.toml", "environment/Dockerfile",
        "environment/candidate.cir", "environment/docker-compose.yaml",
        "environment/cmos018.lib", "solution/reference-a.cir",
        "tests/Dockerfile", "tests/docker-compose.yaml", "tests/evaluator.py",
        "tests/grade.py", "tests/test.sh", "tests/test_evaluator.py",
    )
    for relative in required:
        require((PACKAGE / relative).is_file(), f"missing required file: {relative}")
    model = PACKAGE / "environment/cmos018.lib"
    require(hashlib.sha256(model.read_bytes()).hexdigest() == MODEL_SHA256, "model hash mismatch")
    instruction = (PACKAGE / "instruction.md").read_text(encoding="utf-8")
    for text in ("minus 0.8840 V", "minus 0.5246 V", "minus 0.1803 V", "3079 V/V", "6.252 MHz", "1.775 V", "35.30 percent", "final 5 ms", "harmonics through the fifth", "200 uA"):
        require(text in instruction, f"instruction is missing required contract text: {text}")
    for leaked in ("Scoring type", "Production measurements", "## Reward", "central target", "lower-is-better", "higher-is-better", "criterion reward"):
        require(leaked not in instruction, f"instruction leaks private grading language: {leaked}")
    for precise in ("0.883971454", "0.524603301", "3079.283070", "6252390.225", "1.775361339", "35.3017015"):
        require(precise not in instruction, f"instruction leaks an overprecise target: {precise}")
    reference = (PACKAGE / "solution/reference-a.cir").read_bytes()
    starter = (PACKAGE / "environment/candidate.cir").read_bytes()
    require(reference != starter, "starter exposes the passing reference")
    for relative in ("environment/Dockerfile", "tests/Dockerfile"):
        dockerfile = (PACKAGE / relative).read_text(encoding="utf-8")
        require(BASE_DIGEST in dockerfile, f"{relative} does not pin the shared baseline")
    require("solution/reference-a.cir" not in (PACKAGE / "environment/Dockerfile").read_text(), "agent image leaks the reference")
    evaluator = (PACKAGE / "tests/evaluator.py").read_text(encoding="utf-8")
    require("tran {TRANSIENT_STEP_SECONDS} {TRANSIENT_STOP_SECONDS} {TRANSIENT_START_SECONDS}" in evaluator, "production grader does not run transient analysis")
    require("range(1, 6)" in evaluator, "transient THD does not use the first five harmonics")
    require("require_topology(elements)" in evaluator, "required topology is not enforced")
    environment = os.environ.copy()
    environment.update({
        "EESIM_CMOS_MODEL": str(model),
        "EESIM_REFERENCE": str(PACKAGE / "solution/reference-a.cir"),
        "PYTHONPATH": str(PACKAGE / "tests"),
    })
    with tempfile.TemporaryDirectory() as directory:
        completed = subprocess.run([sys.executable, str(PACKAGE / "tests/test_evaluator.py")], cwd=directory, env=environment, capture_output=True, text=True, timeout=180, check=False)
    require(completed.returncode == 0, completed.stdout + completed.stderr)
    print("Two-stage CMOS op amp Harbor package verification passed")


if __name__ == "__main__":
    main()
