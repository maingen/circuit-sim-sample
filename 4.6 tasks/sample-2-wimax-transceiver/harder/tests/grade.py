#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/tests/grading")
from run_private_fixtures import grade_submission


def main() -> None:
    logs = Path(os.environ.get("HARBOR_VERIFIER_LOGS", "/logs/verifier"))
    candidate = Path(os.environ.get("CANDIDATE_PATH", "/app/submission"))
    logs.mkdir(parents=True, exist_ok=True)
    result = grade_submission(
        candidate,
        logs,
        "harder",
        Path("/tests/private/fixtures"),
        Path("/tests/private/target_ledger.json"),
        Path("/opt/sky130/sky130_tt_1v8.spice"),
    )
    reward = {
        "reward": float(result["final_score"]),
        "production_pass": 1.0 if result["production_pass"] else 0.0,
        "artifact_evaluable": 1.0 if result["artifact_evaluable"] else 0.0,
    }
    (logs / "reward.json").write_text(json.dumps(reward, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
