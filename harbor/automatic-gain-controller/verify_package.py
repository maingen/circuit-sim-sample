#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
BASE_DIGEST = "sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96"
MODEL_SHA = "eb6e698b3425361749de966d8bc3a970a93d9ae8e047e502309bfb2e84e07c5a"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    required = (
        "instruction.md", "task.toml", "environment/Dockerfile",
        "environment/candidate.cir", "environment/docker-compose.yaml",
        "environment/system.lib", "solution/reference-a.cir", "tests/Dockerfile",
        "tests/docker-compose.yaml", "tests/grade.py", "tests/test.sh",
        "tests/test_evaluator.py", "tests/grader/common.py", "tests/grader/tasks.py",
        "tests/grader/scoring.py", "tests/grader/grade.py",
    )
    for relative in required:
        require((PACKAGE / relative).is_file(), f"missing {relative}")
    require(not any(PACKAGE.rglob("__pycache__")), "package contains Python cache files")
    require(hashlib.sha256((PACKAGE / "environment/system.lib").read_bytes()).hexdigest() == MODEL_SHA, "trusted model changed")
    instruction = (PACKAGE / "instruction.md").read_text()
    require("/app/candidate.cir" in instruction and "/app/system.lib" in instruction, "public workflow is incomplete")
    require(".subckt candidate detp detn oa pkd agc agc_pkd_ref agc_ref vcc vss" in instruction, "public interface changed")
    require("`agc_pkd_ref` at 0.8 V" in instruction, "peak-detector reference is not disclosed")
    require("`agc_ref` at 1.2864 V" in instruction, "AGC reference is not disclosed")
    require("`detn` at 3.15 V" in instruction and "`detp` at `detn` plus" in instruction, "detector common mode is not disclosed")
    require(not re.search(r"(?i)reward|scoring|private target|criterion", instruction), "private grader language leaked")
    require("—" not in instruction and "→" not in instruction and "-" + ">" not in instruction, "clarity punctuation failed")
    task = (PACKAGE / "task.toml").read_text()
    require('name = "maingen/tia-agc-controller"' in task, "task name changed")
    require(task.count("@sha256:") == 2, "agent and verifier images must be digest pinned")
    require("REPLACE_" not in task, "image placeholder remains")
    require('network_mode = "no-network"' in task, "verifier network is enabled")
    for relative in ("environment/Dockerfile", "tests/Dockerfile"):
        require(BASE_DIGEST in (PACKAGE / relative).read_text(), f"{relative} baseline changed")
    grader = (PACKAGE / "tests/grader/tasks.py").read_text()
    require("tran " in grader, "production transient grading is missing")
    require("validate_task_structure" in (PACKAGE / "tests/grader/grade.py").read_text(), "task topology gate is missing")
    require((PACKAGE / "environment/candidate.cir").read_bytes() != (PACKAGE / "solution/reference-a.cir").read_bytes(), "starter exposes reference")
    require("reference-a.cir" not in (PACKAGE / "environment/Dockerfile").read_text(), "agent image exposes reference")
    print("tia-agc-controller package checks passed")


if __name__ == "__main__":
    main()
