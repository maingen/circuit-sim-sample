#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path

from evaluator import (
    GAIN_TARGET,
    central_reward,
    grade_submission,
    higher_is_better_reward,
    lower_is_better_reward,
    parse_candidate,
)


REFERENCE = Path(os.environ.get("EESIM_REFERENCE", "/tests/reference-a.cir"))


def close(actual: float, expected: float) -> None:
    if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12):
        raise AssertionError(f"expected {expected}, got {actual}")


def main() -> None:
    close(central_reward(GAIN_TARGET, GAIN_TARGET), 1.0)
    close(central_reward(1.25 * GAIN_TARGET, GAIN_TARGET), 1.0)
    close(central_reward(1.5 * GAIN_TARGET, GAIN_TARGET), 2.0 / 3.0)
    close(central_reward(2.0 * GAIN_TARGET, GAIN_TARGET), 0.0)
    close(lower_is_better_reward(0.5, 1.0), 1.0)
    close(lower_is_better_reward(1.5, 1.0), 2.0 / 3.0)
    close(higher_is_better_reward(2.0, 1.0), 1.0)
    close(higher_is_better_reward(0.5, 1.0), 2.0 / 3.0)

    source = REFERENCE.read_text(encoding="utf-8")
    parse_candidate(source)
    series_output_resistors = source.replace(
        "M6 out vd2 vdd vdd",
        "M6 upper_drain vd2 vdd vdd",
    ).replace(
        "M7 out vg5 vss 0",
        "M7 lower_drain vg5 vss 0",
    ).replace(
        ".ends candidate",
        "RUPPER upper_drain out 385\nRLOWER lower_drain out 355\n.ends candidate",
    )
    parse_candidate(series_output_resistors)
    invalid_sources = (
        source.replace("IREF vdd vg5 DC 200u", "IREF vdd vg5 DC 100u"),
        source.replace("PMOS4 L=0.2u", "FAKE L=0.2u", 1),
        source.replace("M2 vd2 inp vd5 0", "M2 vd2 inn vd5 0"),
        source.replace("M6 out vd2 vdd vdd", "M6 out vg5 vdd vdd"),
        source.replace("M6 out vd2 vdd vdd", "M6 upper_drain vd2 vdd vdd"),
        source.replace(".ends candidate", ".include secret.lib\n.ends candidate"),
        source.replace(".ends candidate", "EGAIN out 0 inp inn 100\n.ends candidate"),
    )
    for invalid in invalid_sources:
        try:
            parse_candidate(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("parser accepted a prohibited or malformed candidate")

    with tempfile.TemporaryDirectory() as directory:
        result = grade_submission(REFERENCE, Path(directory))
    if result["final_reward"] != 1.0 or not result["production_pass"]:
        raise AssertionError(result)
    measurements = result["measurements"]
    if not (1.7 < float(measurements["output_swing_peak_to_peak_v"]) < 1.9):
        raise AssertionError("reference overload swing is not plausible")
    if not (0.0 < float(measurements["thd_percent"]) < 50.0):
        raise AssertionError("reference transient THD is not plausible")
    print("Two-stage CMOS op amp evaluator tests passed")


if __name__ == "__main__":
    main()
