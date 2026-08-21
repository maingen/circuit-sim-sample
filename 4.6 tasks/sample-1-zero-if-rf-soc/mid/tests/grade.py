#!/usr/bin/env python3
import json
import os
from pathlib import Path
from evaluator import grade_submission

logs = Path(os.environ.get("HARBOR_VERIFIER_LOGS", "/logs/verifier"))
candidate = Path(os.environ.get("CANDIDATE_PATH", "/app/candidate.cir"))
logs.mkdir(parents=True, exist_ok=True)
result = grade_submission(candidate, logs / "simulation-artifacts", "mid")
(logs / "details.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
(logs / "reward.json").write_text(json.dumps({
    "reward": float(result["final_reward"]),
    "production_pass": 1.0 if result["production_pass"] else 0.0,
    "artifact_evaluable": 1.0 if result["artifact_evaluable"] else 0.0,
}, indent=2, sort_keys=True) + "\n")
print(json.dumps(result, indent=2, sort_keys=True))
