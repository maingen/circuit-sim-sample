#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import py_compile
import sys
import tempfile
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
BASE_DIGEST = "sha256:0b123316ec4533fa9a61333d125c344f1be3efd1a94051a056f8c4e8ec249c96"
IHP_REVISION = "22f2a25f1734796de3debbbf29cf697cbbc54081"
OPENVAF_REVISION = "3369a83f9c626f6d298f9f881379f561ce432e27"
VERIFIER_DIGEST = "sha256:4bd8cdac41adff270d8c90d51ce7363a847c1d5cbd5d8d55d5ce39f6e3a8d1d0"
REFERENCE_SHA = "4ad6aa32b45816ba7fa30b5113d66b0fef1cdd2c9828baa6cbaeca582719b87d"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    required = (
        "task.toml", "instruction.md", "environment/Dockerfile",
        "environment/docker-compose.yaml", "environment/candidate.cir",
        "tests/Dockerfile", "tests/docker-compose.yaml", "tests/evaluator.py",
        "tests/grade.py", "tests/test.sh", "tests/test_reward_scale.py",
        "tests/reference_calibration.json", "solution/reference.cir",
        "solution/reference-generic-baseline.cir", "solution/convert_reference_to_ihp.py",
    )
    for relative in required:
        require((PACKAGE / relative).is_file(), f"missing {relative}")
    require(not any(PACKAGE.rglob("__pycache__")), "package contains Python cache files")

    reference = (PACKAGE / "solution/reference.cir").read_bytes()
    require(hashlib.sha256(reference).hexdigest() == REFERENCE_SHA, "reference circuit changed")
    reference_text = reference.decode("utf-8")
    require(reference_text.rstrip().casefold().endswith(".end"), "reference omits .end")
    for model in ("npn13G2", "npn13G2v", "sg13_hv_nmos", "sg13_hv_pmos"):
        require(model in reference_text, f"reference does not exercise {model}")
    require("sky130" not in reference_text.casefold(), "reference still contains SKY130 devices")
    require("R_XBUF_LOAD" not in reference_text, "reference embeds the fixture-owned output load")
    require(
        "EESIMBENCH_FIXTURE_OUTPUT_LOAD" not in reference_text,
        "reference contains a private output-load insertion marker",
    )

    calibration = json.loads((PACKAGE / "tests/reference_calibration.json").read_text())
    criteria = calibration.get("criteria", [])
    keys = {(item["test"], item["name"]) for item in criteria}
    require(len(criteria) == 28 and len(keys) == 28, "reference calibration must contain 28 unique requirements")
    require(calibration.get("source_circuit") == "solution/reference.cir", "calibration names the wrong reference")
    require(calibration.get("pdk_revision") == IHP_REVISION, "calibration PDK revision differs")

    task = (PACKAGE / "task.toml").read_text()
    require('artifacts = ["/app/candidate.cir"]' in task, "artifact contract is wrong")
    require('version = "0.2.2"' in task, "task version is not the corrected Path 3 revision")
    require(IHP_REVISION in task, "task metadata omits the pinned IHP revision")
    require(VERIFIER_DIGEST in task, "task metadata omits the corrected verifier digest")
    require('network_mode = "no-network"' in task, "verifier network must be disabled")

    verifier_compose = (PACKAGE / "tests/docker-compose.yaml").read_text()
    require(VERIFIER_DIGEST in verifier_compose, "Compose does not pin the corrected verifier")

    for dockerfile in (PACKAGE / "environment/Dockerfile", PACKAGE / "tests/Dockerfile"):
        text = dockerfile.read_text()
        require(BASE_DIGEST in text, f"{dockerfile} does not pin the Ngspice 46 baseline")
        require(IHP_REVISION in text and OPENVAF_REVISION in text, f"{dockerfile} does not pin the model toolchain")
        require("git.code.sf.net/p/ngspice" not in text, f"{dockerfile} compiles Ngspice instead of using the baseline")

    agent_image = (PACKAGE / "environment/Dockerfile").read_text()
    for forbidden in ("evaluator.py", "reference_calibration.json", "reference.cir", "solution/"):
        require(forbidden not in agent_image, f"agent image leaks private material: {forbidden}")

    instruction = (PACKAGE / "instruction.md").read_text()
    for required_text in (
        "/app/candidate.cir", "IHP Open PDK SG13G2", "All other node names",
        "73.94 dB-ohm", "33.54 GHz", "596.7 mVpp", "143.6 mV",
    ):
        require(required_text in instruction, f"instruction omits {required_text!r}")
    require("250,000" not in instruction and "250000" not in instruction, "instruction exposes the package-size guard")

    sys.path.insert(0, str(PACKAGE / "tests"))
    from evaluator import fixture, parse_candidate  # noqa: PLC0415

    parsed = parse_candidate(reference_text)
    require(not parsed.structural_failures, "; ".join(parsed.structural_failures))
    reference_deck = fixture(parsed)
    require(
        "R_TB_BUF_LOAD outp outn 100" in reference_deck,
        "fixture did not inject the reference output load through the ordinary candidate path",
    )
    require(
        reference_deck.index("R_TB_BUF_LOAD outp outn 100")
        < reference_deck.index("RIFBTOP vcc ifbias 700"),
        "fixture load is not inserted before candidate elements",
    )
    starter_path = PACKAGE / "environment/candidate.cir"
    starter_deck = fixture(parse_candidate(starter_path.read_text()))
    require(
        "R_TB_BUF_LOAD outp outn 100" in starter_deck,
        "private fixture does not supply ordinary candidates with the disclosed output load",
    )
    require(starter_path.read_bytes() != reference, "starter exposes the reference")

    with tempfile.TemporaryDirectory(prefix="tia-harbor-compile-") as temporary:
        out = Path(temporary)
        for script in (
            PACKAGE / "tests/evaluator.py", PACKAGE / "tests/grade.py",
            PACKAGE / "tests/test_reward_scale.py", PACKAGE / "solution/convert_reference_to_ihp.py",
        ):
            py_compile.compile(str(script), cfile=str(out / (script.stem + ".pyc")), doraise=True)

    print(f"Path 3 TIA package checks passed; reference_sha256={REFERENCE_SHA}")


if __name__ == "__main__":
    main()
