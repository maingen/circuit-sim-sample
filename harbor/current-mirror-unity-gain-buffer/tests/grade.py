#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from evaluator import grade_submission


def main() -> None:
    logs = Path("/logs/verifier")
    logs.mkdir(parents=True, exist_ok=True)
    result = grade_submission(Path("/app/candidate.cir"), logs / "simulation-artifacts")
    (logs / "details.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (logs / "reward.json").write_text(
        json.dumps(
            {
                "reward": float(result["final_reward"]),
                "production_pass": 1.0 if result["production_pass"] else 0.0,
                "artifact_evaluable": 1.0 if result["artifact_evaluable"] else 0.0,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
