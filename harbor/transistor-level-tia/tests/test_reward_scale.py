#!/usr/bin/env python3
from __future__ import annotations

import math
import json

from evaluator import (
    CandidateError,
    MODEL_CARDS,
    REFERENCE_RESULT_PATH,
    central_reward,
    maximum_reward,
    minimum_reward,
    parse_candidate,
    rescore_cached_result,
)


def main() -> None:
    for function in (central_reward,):
        assert function(10.0, 10.0, 10.0) == (0.0, 1.0)
        assert function(10.5, 10.0, 10.0) == (0.05, 1.0)
        assert function(12.0, 10.0, 10.0) == (0.2, 0.0)
        error, reward = function(11.25, 10.0, 10.0)
        assert math.isclose(error, 0.125)
        assert math.isclose(reward, 0.5)

    assert maximum_reward(10.0, 10.0) == (0.0, 1.0)
    assert maximum_reward(10.5, 10.0) == (0.05, 1.0)
    assert maximum_reward(12.0, 10.0) == (0.2, 0.0)
    assert math.isclose(maximum_reward(11.25, 10.0)[1], 0.5)
    assert maximum_reward(1.0, 10.0)[1] == 1.0

    assert minimum_reward(10.0, 10.0) == (0.0, 1.0)
    assert minimum_reward(9.5, 10.0) == (0.05, 1.0)
    assert minimum_reward(8.0, 10.0) == (0.2, 0.0)
    assert math.isclose(minimum_reward(8.75, 10.0)[1], 0.5)
    assert minimum_reward(20.0, 10.0)[1] == 1.0

    model_text = "\n".join(MODEL_CARDS)
    compatible = parse_candidate(
        "* Strict-grader parser check\n"
        ".options ngbehavior=ltpsa\n"
        f"{model_text}\n"
        ".end\n"
    )
    assert ".options" not in compatible.simulation_core.casefold()

    try:
        parse_candidate(
            "* Strict-grader parser check\n"
            ".options reltol=0.1\n"
            f"{model_text}\n"
            ".end\n"
        )
    except CandidateError:
        pass
    else:
        raise AssertionError("arbitrary candidate .options directives must remain forbidden")

    calibration = json.loads(REFERENCE_RESULT_PATH.read_text(encoding="utf-8"))
    cached_reference = {
        "criteria": [
            {**criterion, "target": criterion["value"]}
            for criterion in calibration["criteria"]
        ],
        "structural_failures": [],
        "simulation_failures": [],
    }
    rescored_reference = rescore_cached_result(cached_reference)
    assert rescored_reference["final_reward"] == 1.0
    assert rescored_reference["production_pass"] is True
    assert rescored_reference["criteria_observed"] == 68
    print("TIA reward scale checks passed")


if __name__ == "__main__":
    main()
