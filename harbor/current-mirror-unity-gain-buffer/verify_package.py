#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
MODEL_SHA256 = "6696fa66f1edf90d2289370f7b91a629940deb434e78490df58492f33a9d984f"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require((PACKAGE / "instruction.md").is_file(), "instruction.md is missing")
    require(not any(PACKAGE.rglob("prompt.md")), "the package contains a second prompt")
    require((PACKAGE / "environment" / "candidate.cir").is_file(), "starter is missing")
    require((PACKAGE / "environment" / "table-1.5.md").is_file(), "Table 1.5 is missing")
    require((PACKAGE / "tests" / "evaluator.py").is_file(), "private evaluator is missing")
    require(
        (PACKAGE / "tests" / "test_reward_scale.py").is_file(),
        "reward-scale tests are missing",
    )
    require(
        (PACKAGE / "solution" / "prototype-unvalidated.cir").is_file(),
        "authoring prototype is missing",
    )
    require(
        (PACKAGE / "solution" / "reference-a.cir").is_file(),
        "passing reference is missing",
    )
    require(not any(PACKAGE.rglob("__pycache__")), "generated Python cache remains")

    task = (PACKAGE / "task.toml").read_text()
    require('artifacts = ["/app/candidate.cir"]' in task, "artifact contract changed")
    require('name = "maingen/current-mirror-unity-gain-buffer"' in task, "task name changed")
    require('network_mode = "no-network"' in task, "private verifier must have no network")
    require(MODEL_SHA256 in task, "task metadata does not pin the p18 archive")

    for dockerfile in (
        PACKAGE / "environment" / "Dockerfile",
        PACKAGE / "tests" / "Dockerfile",
    ):
        text = dockerfile.read_text()
        require("ngspice-46" in text, f"{dockerfile} does not pin Ngspice 46")
        require(MODEL_SHA256 in text, f"{dockerfile} does not pin the p18 archive")

    agent_stage = (PACKAGE / "environment" / "Dockerfile").read_text()
    for forbidden in (
        "evaluator.py",
        "grade.py",
        "reference-a.cir",
        "prototype-unvalidated.cir",
        "private-cases",
    ):
        require(forbidden not in agent_stage, f"agent image mentions private material: {forbidden}")

    instruction = (PACKAGE / "instruction.md").read_text()
    for required in (
        "/app/candidate.cir",
        ".subckt candidate vinp vinn vout vdd vb1 vb2 vss",
        "TT, FF, and SS",
        "98.9480113766",
        "101.902777538",
        "172.166876271",
        "47.7725720755 degrees",
        "399.573 uA",
    ):
        require(required in instruction, f"instruction is missing: {required}")
    require("prompt.md" not in instruction, "instruction points to a second prompt")
    require("simulate.py" not in instruction, "instruction exposes an official public simulator")

    source = (PACKAGE / "environment" / "candidate.cir").read_bytes()
    prototype = (PACKAGE / "solution" / "prototype-unvalidated.cir").read_bytes()
    reference = (PACKAGE / "solution" / "reference-a.cir").read_bytes()
    require(source != prototype, "starter exposes the authoring prototype")
    require(
        hashlib.sha256(prototype).hexdigest() != hashlib.sha256(source).hexdigest(),
        "starter and authoring prototype collide",
    )
    require(
        hashlib.sha256(reference).hexdigest() != hashlib.sha256(source).hexdigest(),
        "starter and passing reference collide",
    )

    model_visible = instruction + (PACKAGE / "environment" / "table-1.5.md").read_text()
    require("\u2014" not in model_visible and "\u2192" not in model_visible and "->" not in model_visible, "clarity punctuation check failed")
    require(not re.search(r"\bpublic corners?\b", model_visible, re.IGNORECASE), "public-corner language remains")
    print("current-mirror unity-gain buffer package checks passed")


if __name__ == "__main__":
    main()
