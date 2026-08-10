#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

from evaluator import (
    GAIN_TARGET,
    LOADED_RATIO_MAXIMUM,
    LOADED_RATIO_MINIMUM,
    central_reward,
    grade_submission,
    higher_is_better_reward,
    interval_reward,
    lower_is_better_reward,
    parse_candidate,
)


REFERENCE = Path(os.environ.get("EESIM_REFERENCE", "/tests/reference-a.cir"))


def close(actual: float, expected: float) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise AssertionError(f"expected {expected}, got {actual}")


def rejected(source: str) -> None:
    try:
        parse_candidate(source)
    except ValueError:
        return
    raise AssertionError("parser accepted a prohibited or malformed candidate")


def main() -> None:
    close(central_reward(GAIN_TARGET, GAIN_TARGET), 1.0)
    close(central_reward(1.25 * GAIN_TARGET, GAIN_TARGET), 1.0)
    close(central_reward(1.5 * GAIN_TARGET, GAIN_TARGET), 2.0 / 3.0)
    close(central_reward(2.0 * GAIN_TARGET, GAIN_TARGET), 0.0)
    close(lower_is_better_reward(0.5, 1.0), 1.0)
    close(lower_is_better_reward(1.5, 1.0), 2.0 / 3.0)
    close(higher_is_better_reward(2.0, 1.0), 1.0)
    close(higher_is_better_reward(0.5, 1.0), 2.0 / 3.0)
    close(interval_reward(0.98, LOADED_RATIO_MINIMUM, LOADED_RATIO_MAXIMUM), 1.0)
    close(interval_reward(0.485, LOADED_RATIO_MINIMUM, LOADED_RATIO_MAXIMUM), 2.0 / 3.0)

    source = REFERENCE.read_text(encoding="utf-8")
    parse_candidate(source)
    for invalid in (
        source.replace("IREF vdd vg5 DC 200u", "IREF vdd vg5 DC 199u"),
        source.replace("NMOS4 L=0.2u", "FAKE L=0.2u", 1),
        source.replace("M2 vd2 0 vd5 0", "M2 vd2 in vd5 0"),
        source.replace("M6 vdd vd2 out 0", "M6 out vd2 vdd 0"),
        source.replace("RFEEDBACK_A out feedback_open 92k", "RFEEDBACK_A out feedback_open 91k"),
        source.replace("RFEEDBACK_B feedback_open 0 8k", "RFEEDBACK_B feedback_open 0 9k"),
        source.replace(".ends candidate", "RLEAK feedback_open in 1g\n.ends candidate"),
        source.replace(".ends candidate", ".include secret.lib\n.ends candidate"),
        source.replace(".ends candidate", "EGAIN out 0 in 0 100\n.ends candidate"),
        source.replace(".ends candidate", ".model NMOS4 NMOS\n.ends candidate"),
        source + "XTRICK in out secret\n",
    ):
        rejected(invalid)

    with tempfile.TemporaryDirectory() as directory:
        result = grade_submission(REFERENCE, Path(directory))
    if result["final_reward"] != 1.0 or not result["production_pass"] or not result["artifact_evaluable"]:
        raise AssertionError(result)
    measurements = result["measurements"]
    ratio = float(measurements["loaded_to_unloaded_gain_ratio"])
    if not (LOADED_RATIO_MINIMUM <= ratio <= LOADED_RATIO_MAXIMUM):
        raise AssertionError(f"reference loaded-to-unloaded ratio is outside the public interval: {ratio}")

    # A weak but structurally legal amplifier must remain evaluable and fail
    # its electrical requirements instead of being misclassified as invalid.
    with tempfile.TemporaryDirectory() as directory:
        mutant = Path(directory) / "candidate.cir"
        mutant.write_text(source.replace("M=14.32", "M=3", 1), encoding="utf-8")
        result = grade_submission(mutant, Path(directory) / "artifacts")
    if not result["artifact_evaluable"] or result["production_pass"]:
        raise AssertionError("weak legal amplifier was not classified as an evaluable production failure")

    # Pre-existing simulator-looking files cannot rescue an invalid artifact.
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "ac.dat").write_text("frequency v(out)\n1e7 1 0\n", encoding="utf-8")
        bad = root / "candidate.cir"
        bad.write_text(source.replace(".subckt candidate", ".subckt wrong"), encoding="utf-8")
        result = grade_submission(bad, root)
    if result["artifact_evaluable"] or result["final_reward"] != 0.0:
        raise AssertionError("stale artifacts influenced an invalid submission")
    print("Open-feedback CMOS amplifier evaluator tests passed")


if __name__ == "__main__":
    main()
