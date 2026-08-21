#!/usr/bin/env python3
from __future__ import annotations

import math
import json

from evaluator import (
    CandidateError,
    REFERENCE_CRITERIA,
    REFERENCE_RESULT_PATH,
    TEST_CRITERION_KEYS,
    central_reward,
    maximum_reward,
    minimum_reward,
    parse_candidate,
    rescore_cached_result,
    result_from_criteria,
    unavailable_criteria,
    fixture,
)


def main() -> None:
    owned_keys = [
        key for keys in TEST_CRITERION_KEYS.values() for key in keys
    ]
    assert len(owned_keys) == 28
    assert len(set(owned_keys)) == 28
    assert set(owned_keys) == set(REFERENCE_CRITERIA)

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

    primitive_text = (
        "XDEVICE inp gate 0 0 sg13_hv_nmos w=1u l=.45u ng=1\n"
        "RPORTS inn finalp 1k"
    )
    compatible = parse_candidate(
        "* Strict-grader parser check\n"
        ".options ngbehavior=ltpsa\n"
        f"{primitive_text}\n"
        ".end\n"
    )
    assert ".options" not in compatible.simulation_core.casefold()
    compatible_deck = fixture(compatible)
    assert "R_TB_BUF_LOAD outp outn 100" in compatible_deck
    assert compatible_deck.index("R_TB_BUF_LOAD outp outn 100") < compatible_deck.index("XDEVICE")

    colliding = parse_candidate(
        f"{primitive_text}\nR_TB_BUF_LOAD outp outn 1k\n.end\n"
    )
    collision_safe_deck = fixture(colliding)
    assert "R_TB_BUF_LOAD outp outn 1k" in collision_safe_deck
    assert "R_TB_BUF_LOAD_1 outp outn 100" in collision_safe_deck
    assert collision_safe_deck.index("R_TB_BUF_LOAD_1 outp outn 100") < collision_safe_deck.index("XDEVICE")

    try:
        parse_candidate(
            "* Strict-grader parser check\n"
            ".options reltol=0.1\n"
            f"{primitive_text}\n"
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
    assert rescored_reference["criteria_observed"] == 28

    partial_criteria = unavailable_criteria("peak-detector", "fixture timeout")
    partial = result_from_criteria(
        partial_criteria,
        [],
        [{"test": "peak-detector", "error": "fixture timeout"}],
    )
    assert partial["outcome"] == "simulation_failed"
    assert partial["artifact_evaluable"] is False
    assert partial["production_pass"] is False
    assert partial["criteria_observed"] == 0
    assert partial["criteria_reported"] == 3
    assert all(item["reward"] == 0.0 for item in partial["criteria"])
    assert all(
        item["measurement_status"] == "simulation_failed"
        for item in partial["criteria"]
    )
    print("TIA reward scale checks passed")


if __name__ == "__main__":
    main()
