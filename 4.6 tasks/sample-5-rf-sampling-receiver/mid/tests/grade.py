#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, "/tests")
from evaluator import evaluate_submission

def main() -> None:
    difficulty = os.environ.get("BENCHMARK_DIFFICULTY", "mid")
    logs = Path(os.environ.get("HARBOR_VERIFIER_LOGS", "/logs/verifier"))
    logs.mkdir(parents=True, exist_ok=True)
    result = evaluate_submission(
        Path("/app/submission"), difficulty, logs / "grade",
        Path("/tests/fixtures"), Path("/tests/target_ledger.json"),
        Path(os.environ["SKY130_LIB"]), os.environ.get("NGSPICE_BIN", "/usr/bin/ngspice"),
    )
    reward = {
        "reward": float(result["final_deterministic_score"]),
        "production_pass": 1.0 if result["mandatory_gates_pass"] else 0.0,
        "artifact_evaluable": 1.0 if result["lint"]["eligible"] else 0.0,
    }
    (logs / "details.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (logs / "reward.json").write_text(json.dumps(reward, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
