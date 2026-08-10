#!/usr/bin/env python3
from pathlib import Path
from tempfile import TemporaryDirectory

from grader.common import CandidateError, parse_candidate
from grader.grade import aggregate_scores


with TemporaryDirectory() as directory:
    path = Path(directory) / "candidate.cir"
    path.write_text(".subckt candidate wrong ports\n.ends candidate\n")
    try:
        parse_candidate(path, ("expected",))
    except CandidateError:
        pass
    else:
        raise AssertionError("malformed candidate was accepted")
assert aggregate_scores("agc_controller_tl_run_01", {"passing": 1.0, "gross": 0.0}) == 0.0
assert aggregate_scores("agc_controller_tl_run_01", {"passing": 1.0, "near": 0.25}) == 0.625
print("verifier parser smoke test passed")
