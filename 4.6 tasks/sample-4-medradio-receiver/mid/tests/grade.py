#!/usr/bin/env python3
from __future__ import annotations
import json
import os
from pathlib import Path
from evaluator import grade_submission

def main() -> None:
    logs = Path(os.environ.get("HARBOR_VERIFIER_LOGS", "/logs/verifier"))
    root = Path(os.environ.get("CANDIDATE_ROOT", "/app"))
    logs.mkdir(parents=True, exist_ok=True)
    result = grade_submission(root, logs / "simulation-artifacts", "mid")
    (logs / "details.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    reward = {
        "reward": float(result["final_reward"]),
        "production_pass": 1.0 if result["production_pass"] else 0.0,
        "artifact_evaluable": 1.0 if result["artifact_evaluable"] else 0.0,
    }
    (logs / "reward.json").write_text(json.dumps(reward, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))

if __name__ == "__main__":
    main()
