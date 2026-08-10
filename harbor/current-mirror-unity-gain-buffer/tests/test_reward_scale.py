#!/usr/bin/env python3
from __future__ import annotations

import math

from evaluator import (
    CandidateError,
    LIMITS,
    REFERENCE_SCALE,
    metric_score,
    parse_candidate,
    reward_boundaries,
    reward_collapse_trigger,
)


def main() -> None:
    for name, scale in REFERENCE_SCALE.items():
        best = float(scale["best"])
        worst = float(scale["worst"])
        zero_credit, circuit_collapse = reward_boundaries(name)
        midpoint = (zero_credit + worst) / 2.0

        assert LIMITS[name] == worst
        assert metric_score(name, best) == 1.0
        assert metric_score(name, worst) == 1.0
        assert math.isclose(metric_score(name, midpoint), 0.5, abs_tol=1e-12)
        assert math.isclose(metric_score(name, zero_credit), 0.0, abs_tol=1e-12)

        metrics = {
            metric: float(reference["worst"])
            for metric, reference in REFERENCE_SCALE.items()
        }
        metrics[name] = circuit_collapse
        assert reward_collapse_trigger(metrics) == name

    ordinary_names = """.subckt candidate vinp vinn vout vdd vb1 vb2 vss
M1 d1 vinp ntail vss nmos w=50u l=0.4u
M2 vout vinn ntail vss nmos w=100u l=0.4u
M3 d1 d1 vdd vdd pmos w=40u l=0.4u
M4 vout d1 vdd vdd pmos w=80u l=0.4u
IBIAS ntail vss 340u
.ends candidate
"""
    parse_candidate(ordinary_names)

    wrong_ratio = ordinary_names.replace("w=80u", "w=79u")
    try:
        parse_candidate(wrong_ratio)
    except CandidateError as exc:
        assert "K=2 MOS mirror pair" in str(exc)
    else:
        raise AssertionError("a circuit without a K=2 mirror pair was accepted")

    source_degenerated = """.subckt candidate vinp vinn vout vdd vb1 vb2 vss
M1 d1 vinp ntail vss nmos w=50u l=0.4u
M2 vout vinn ntail vss nmos w=50u l=0.4u
RS3 s3 vdd 800
RS5 s5 vdd 400
MP3 d1 d1 s3 vdd pmos w=40u l=0.4u
MP5 vout d1 s5 vdd pmos w=80u l=0.4u
IBIAS ntail vss 340u
.ends candidate
"""
    parse_candidate(source_degenerated)

    print("reward scale checks passed")


if __name__ == "__main__":
    main()
