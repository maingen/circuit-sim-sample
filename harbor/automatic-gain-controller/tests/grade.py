#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from grader.grade import evaluate_submission


def main() -> None:
    candidate = Path(os.environ.get("CANDIDATE_PATH", "/app/candidate.cir"))
    artifacts = Path(os.environ.get("SIMULATION_ARTIFACT_DIR", "/logs/verifier/simulation-artifacts"))
    result = evaluate_submission("agc_controller_tl_run_01", candidate, artifacts)
    output = Path(os.environ.get("GRADE_OUTPUT", "/logs/verifier/details.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (output.parent / "reward.json").write_text(json.dumps({
        "reward": float(result["final_reward"]),
        "production_pass": 1.0 if result["production_pass"] else 0.0,
        "artifact_evaluable": 1.0 if result["artifact_evaluable"] else 0.0,
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
