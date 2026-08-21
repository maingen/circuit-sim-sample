#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from evaluator import grade_submission


def main() -> None:
    logs = Path(os.environ.get("HARBOR_VERIFIER_LOGS", "/logs/verifier"))
    candidate = Path(os.environ.get("CANDIDATE_PATH", "/app/candidate.cir"))
    architecture = Path(os.environ.get("ARCHITECTURE_PATH", "/app/architecture.json"))
    difficulty = os.environ["BENCHMARK_DIFFICULTY"]
    starter_sha256 = os.environ.get("STARTER_SHA256")
    logs.mkdir(parents=True, exist_ok=True)
    artifact_dir = logs / "simulation-artifacts"
    try:
        result = grade_submission(
            candidate, architecture, artifact_dir, difficulty, starter_sha256
        )
    except Exception as exc:
        result = {
            "difficulty": difficulty,
            "artifact_evaluable": False,
            "production_pass": False,
            "raw_deterministic_score": 0.0,
            "final_deterministic_score": 0.0,
            "mandatory_gate_pass": False,
            "gate_findings": [
                {"code": "EVALUATOR_EXCEPTION", "detail": str(exc), "mandatory": True}
            ],
            "criteria": [],
        }
    (logs / "details.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    reward = {
        "reward": float(result["final_deterministic_score"]),
        "production_pass": 1.0 if result["production_pass"] else 0.0,
        "artifact_evaluable": 1.0 if result["artifact_evaluable"] else 0.0,
    }
    (logs / "reward.json").write_text(
        json.dumps(reward, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
