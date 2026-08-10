#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import py_compile
import tempfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
BASE_DIGEST = "sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96"
REFERENCE_SHA = "9c7e6e1a5fdd4526539460b22916542411d97f2b6f07ebc8d70773d6b2a5ddc7"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    required = (
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "environment/docker-compose.yaml",
        "environment/candidate.cir",
        "tests/Dockerfile",
        "tests/docker-compose.yaml",
        "tests/evaluator.py",
        "tests/grade.py",
        "tests/test.sh",
        "tests/test_reward_scale.py",
        "tests/reference_calibration.json",
        "solution/reference.cir",
    )
    for relative in required:
        require((PACKAGE / relative).is_file(), f"missing {relative}")
    require(not any(PACKAGE.rglob("__pycache__")), "package contains Python cache files")

    packaged_reference = (PACKAGE / "solution/reference.cir").read_bytes()
    require(
        hashlib.sha256(packaged_reference).hexdigest() == REFERENCE_SHA,
        "reference circuit changed",
    )
    reference_text = packaged_reference.decode("utf-8")
    require(reference_text.rstrip().casefold().endswith(".end"), "reference circuit omits .end")
    require(
        "M_CANCEL_P" in reference_text and "M_CANCEL_N" in reference_text,
        "reference circuit omits cancellation devices",
    )

    calibration = json.loads((PACKAGE / "tests/reference_calibration.json").read_text())
    criteria = calibration.get("criteria", [])
    keys = {(item["test"], item["name"]) for item in criteria}
    require(len(criteria) == 68 and len(keys) == 68, "reference calibration is incomplete")
    require(
        calibration.get("source_circuit") == "solution/reference.cir",
        "reference calibration names the wrong circuit",
    )

    task = (PACKAGE / "task.toml").read_text()
    require('artifacts = ["/app/candidate.cir"]' in task, "artifact contract is wrong")
    require('name = "maingen/transistor-level-tia"' in task, "task name is wrong")
    require('status = "validated-reference"' in task, "task status must reflect reference validation")
    require('network_mode = "no-network"' in task, "verifier network must be disabled")

    for dockerfile in (PACKAGE / "environment/Dockerfile", PACKAGE / "tests/Dockerfile"):
        text = dockerfile.read_text()
        require(BASE_DIGEST in text, f"{dockerfile} does not pin the shared Ngspice image")

    verifier_image = (PACKAGE / "tests/Dockerfile").read_text()
    require(
        "tests/reference_calibration.json /tests/" in verifier_image,
        "verifier image omits the private reference calibration",
    )

    agent_image = (PACKAGE / "environment/Dockerfile").read_text()
    for forbidden in ("evaluator.py", "grading.txt", "reference.cir", "solution/"):
        require(forbidden not in agent_image, f"agent image leaks private material: {forbidden}")

    instruction = (PACKAGE / "instruction.md").read_text()
    require("/app/candidate.cir" in instruction, "instruction omits submission path")
    require("M_CANCEL_P" in instruction and "M_CANCEL_N" in instruction, "instruction omits grader-visible device names")
    require("built-in or macromodel op-amps" in instruction, "instruction omits transistor-level restriction")
    require(
        (PACKAGE / "environment/candidate.cir").read_bytes() != packaged_reference,
        "starter circuit exposes the reference",
    )

    with tempfile.TemporaryDirectory(prefix="tia-harbor-compile-") as temporary:
        compile_root = Path(temporary)
        for script in (PACKAGE / "tests/evaluator.py", PACKAGE / "tests/grade.py", PACKAGE / "tests/test_reward_scale.py"):
            py_compile.compile(str(script), cfile=str(compile_root / (script.stem + ".pyc")), doraise=True)

    print(f"transistor-level TIA Harbor package checks passed; reference_sha256={REFERENCE_SHA}")


if __name__ == "__main__":
    main()
