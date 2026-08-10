from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .common import CandidateError, SimulationError, parse_candidate, validate_task_structure
from .scoring import BLOCKED_TASKS, SCORERS
from .tasks import EVALUATORS, HELPER_TASKS, PORTS


GROSS_FAILURE_GATED_TASKS = {"agc_controller_tl_run_01"}


def aggregate_scores(task: str, scores: dict[str, float]) -> float:
    """Return zero for a gross functional miss, otherwise preserve proximity."""
    if task in GROSS_FAILURE_GATED_TASKS and any(score == 0.0 for score in scores.values()):
        return 0.0
    return sum(scores.values()) / len(scores)


def evaluate_submission(task: str, candidate_path: Path, artifact_root: Path) -> dict[str, object]:
    if task not in EVALUATORS:
        raise ValueError(f"unknown task: {task}")
    try:
        candidate = parse_candidate(
            candidate_path,
            PORTS[task],
            allow_helpers=task in HELPER_TASKS,
        )
        validate_task_structure(task, candidate)
    except (OSError, UnicodeError, CandidateError) as exc:
        return {
            "task": task,
            "outcome": "candidate_invalid",
            "artifact_evaluable": False,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["CANDIDATE_INVALID"],
            "error": str(exc),
            "measurements": {},
            "metric_rewards": {},
        }
    if shutil.which("ngspice") is None:
        return {
            "task": task,
            "outcome": "infrastructure_error",
            "artifact_evaluable": False,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["NGSPICE_MISSING"],
            "error": "Ngspice is unavailable",
            "measurements": {},
            "metric_rewards": {},
        }
    try:
        measurements = EVALUATORS[task](candidate, artifact_root)
    except (OSError, SimulationError) as exc:
        return {
            "task": task,
            "outcome": "simulation_failed",
            "artifact_evaluable": False,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["SIMULATION_FAILED"],
            "error": str(exc),
            "measurements": {},
            "metric_rewards": {},
        }
    if task in BLOCKED_TASKS:
        return {
            "task": task,
            "outcome": "grader_blocked",
            "artifact_evaluable": True,
            "production_pass": False,
            "final_reward": 0.0,
            "failure_codes": ["PUBLIC_CONTRACT_REFERENCE_CONFLICT"],
            "error": BLOCKED_TASKS[task],
            "measurements": measurements,
            "metric_rewards": {},
        }
    scores = SCORERS[task](measurements)
    final_reward = aggregate_scores(task, scores)
    production_pass = all(score == 1.0 for score in scores.values())
    return {
        "task": task,
        "outcome": "passed" if production_pass else "requirements_failed",
        "artifact_evaluable": True,
        "production_pass": production_pass,
        "final_reward": 1.0 if production_pass else final_reward,
        "failure_codes": [name for name, score in scores.items() if score < 1.0],
        "error": None,
        "measurements": measurements,
        "metric_rewards": scores,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=sorted(EVALUATORS))
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate_submission(args.task, args.candidate, args.artifacts)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
