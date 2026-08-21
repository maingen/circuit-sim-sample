#!/usr/bin/env python3
"""Run the private section judge and combine it with frozen Ngspice evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parent
DEFAULT_LEDGER = ROOT / "section_ledger.json"
DEFAULT_PROMPT = ROOT / "judge_prompt.md"
VERIFIER_VERSION = "1.0.1"
OUTPUT_FILES = (
    "review_packet.json",
    "judge.json",
    "canonical_details.json",
    "provenance.json",
    "reward.json",
    "infrastructure_failure.json",
)


class CanonicalVerifierError(RuntimeError):
    """A malformed packet, result, or judge response."""


class JudgeInfrastructureError(CanonicalVerifierError):
    """The judge did not return a trustworthy complete decision."""


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CanonicalVerifierError(f"expected a JSON object in {path}")
    return value


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_ledger(ledger: dict[str, Any]) -> None:
    sections = ledger.get("sections")
    criteria = ledger.get("criteria")
    if not isinstance(sections, list) or not isinstance(criteria, list):
        raise CanonicalVerifierError("ledger must contain section and criterion lists")

    section_ids = [item.get("section_id") for item in sections]
    if len(section_ids) != len(set(section_ids)) or not all(isinstance(item, str) for item in section_ids):
        raise CanonicalVerifierError("section IDs must be unique strings")

    criterion_ids = [item.get("criterion_id") for item in criteria]
    expected_ids = [f"C{index:02d}" for index in range(1, 29)]
    if criterion_ids != expected_ids:
        raise CanonicalVerifierError("criterion IDs must be exactly C01 through C28 in order")

    keys = [(item.get("test"), item.get("name")) for item in criteria]
    if len(keys) != len(set(keys)):
        raise CanonicalVerifierError("criterion test and name pairs must be unique")

    criterion_sections = {item["criterion_id"]: item.get("section_id") for item in criteria}
    if any(section_id not in section_ids for section_id in criterion_sections.values()):
        raise CanonicalVerifierError("every criterion must reference a known section")

    owned: list[str] = []
    for section in sections:
        section_owned = section.get("owned_criteria")
        if not isinstance(section_owned, list):
            raise CanonicalVerifierError(f"section {section['section_id']} has no owned criteria list")
        owned.extend(section_owned)
        for criterion_id in section_owned:
            if criterion_sections.get(criterion_id) != section["section_id"]:
                raise CanonicalVerifierError(
                    f"criterion {criterion_id} disagrees with section {section['section_id']}"
                )
    if sorted(owned) != sorted(expected_ids) or len(owned) != len(set(owned)):
        raise CanonicalVerifierError("every criterion must be owned by exactly one section")


def validate_static_details(details: dict[str, Any], ledger: dict[str, Any]) -> None:
    criteria = details.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 28:
        raise CanonicalVerifierError("static details must contain exactly 28 criteria")
    expected = {(item["test"], item["name"]) for item in ledger["criteria"]}
    observed = {(item.get("test"), item.get("name")) for item in criteria}
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise CanonicalVerifierError(f"static criterion mismatch; missing={missing}, extra={extra}")
    for item in criteria:
        reward = item.get("reward")
        if not isinstance(reward, (int, float)) or not math.isfinite(float(reward)):
            raise CanonicalVerifierError("every static criterion must have a finite reward")
        if float(reward) < 0.0 or float(reward) > 1.0:
            raise CanonicalVerifierError("static criterion rewards must be between zero and one")


def judge_schema(ledger: dict[str, Any]) -> dict[str, Any]:
    finding = {
        "type": "object",
        "additionalProperties": False,
        "required": ["elements", "nodes", "public_requirement", "electrical_reason"],
        "properties": {
            "elements": {"type": "array", "items": {"type": "string"}},
            "nodes": {"type": "array", "items": {"type": "string"}},
            "public_requirement": {"type": "string"},
            "electrical_reason": {"type": "string"},
        },
    }
    section_result = {
        "type": "object",
        "additionalProperties": False,
        "required": ["verdict", "findings"],
        "properties": {
            "verdict": {"type": "string", "enum": ["pass", "fail", "indeterminate"]},
            "findings": {"type": "array", "items": finding},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["sections", "summary"],
        "properties": {
            "sections": {
                "type": "object",
                "additionalProperties": False,
                "required": [item["section_id"] for item in ledger["sections"]],
                "properties": {
                    item["section_id"]: section_result for item in ledger["sections"]
                },
            },
            "summary": {"type": "string"},
        },
    }


def validate_judge_result(result: dict[str, Any], ledger: dict[str, Any]) -> None:
    expected = {item["section_id"] for item in ledger["sections"]}
    sections = result.get("sections")
    if not isinstance(sections, dict) or set(sections) != expected:
        raise JudgeInfrastructureError("judge section IDs do not exactly match the ledger")
    if not isinstance(result.get("summary"), str):
        raise JudgeInfrastructureError("judge summary is missing")
    for section_id, section in sections.items():
        if not isinstance(section, dict) or set(section) != {"verdict", "findings"}:
            raise JudgeInfrastructureError(f"invalid result object for {section_id}")
        verdict = section["verdict"]
        findings = section["findings"]
        if verdict not in {"pass", "fail", "indeterminate"} or not isinstance(findings, list):
            raise JudgeInfrastructureError(f"invalid verdict or findings for {section_id}")
        if verdict in {"fail", "indeterminate"} and not findings:
            raise JudgeInfrastructureError(f"{verdict} section {section_id} requires evidence")
        for finding in findings:
            if not isinstance(finding, dict) or set(finding) != {
                "elements", "nodes", "public_requirement", "electrical_reason"
            }:
                raise JudgeInfrastructureError(f"invalid finding for {section_id}")
            if not isinstance(finding["elements"], list) or not isinstance(finding["nodes"], list):
                raise JudgeInfrastructureError(f"invalid element or node evidence for {section_id}")
            if not finding["public_requirement"].strip() or not finding["electrical_reason"].strip():
                raise JudgeInfrastructureError(f"incomplete finding for {section_id}")


def validate_api_metadata(metadata: dict[str, Any], requested_model: str) -> None:
    if metadata.get("status") != "completed":
        raise JudgeInfrastructureError("judge response did not complete")
    if metadata.get("returned_model") != requested_model:
        raise JudgeInfrastructureError("judge returned an unexpected model")
    if not metadata.get("response_id"):
        raise JudgeInfrastructureError("judge response has no response identifier")


def build_packet(
    instruction: Path,
    reference: Path,
    candidate: Path,
    details: dict[str, Any],
    ledger: dict[str, Any],
    trial_id: str,
) -> dict[str, Any]:
    return {
        "packet_schema_version": "1.0",
        "trial_id": trial_id,
        "public_instructions": instruction.read_text(encoding="utf-8"),
        "frozen_reference_circuit": reference.read_text(encoding="utf-8"),
        "candidate_circuit": candidate.read_text(encoding="utf-8"),
        "deterministic_ngspice_details": details,
        "section_ledger": ledger,
        "judge_must_ignore_submitter_identity_and_reasoning": True,
    }


def call_judge(
    packet: dict[str, Any],
    prompt: str,
    ledger: dict[str, Any],
    model: str,
    reasoning_effort: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise JudgeInfrastructureError("OPENAI_API_KEY is unavailable")
    client = OpenAI(timeout=600.0)
    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": reasoning_effort},
            instructions=prompt,
            input=canonical_json(packet),
            max_output_tokens=12000,
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "tia_section_judge",
                    "strict": True,
                    "schema": judge_schema(ledger),
                }
            },
        )
    except Exception as exc:
        raise JudgeInfrastructureError(
            f"OpenAI Responses request failed with {type(exc).__name__}"
        ) from exc
    try:
        result = json.loads(response.output_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise JudgeInfrastructureError("judge returned invalid JSON") from exc
    metadata = {
        "response_id": response.id,
        "returned_model": response.model,
        "created_at": getattr(response, "created_at", None),
        "status": response.status,
        "usage": response.usage.model_dump(mode="json") if response.usage else None,
    }
    validate_api_metadata(metadata, model)
    return result, metadata


def combine_results(
    details: dict[str, Any],
    ledger: dict[str, Any],
    judge_result: dict[str, Any],
) -> dict[str, Any]:
    validate_ledger(ledger)
    validate_static_details(details, ledger)
    validate_judge_result(judge_result, ledger)

    indeterminate = [
        section_id
        for section_id, section in judge_result["sections"].items()
        if section["verdict"] == "indeterminate"
    ]
    if indeterminate:
        raise JudgeInfrastructureError(
            "indeterminate judge sections: " + ", ".join(sorted(indeterminate))
        )

    criteria_by_key = {(item["test"], item["name"]): item for item in details["criteria"]}
    canonical_criteria: list[dict[str, Any]] = []
    for ledger_item in ledger["criteria"]:
        static = criteria_by_key[(ledger_item["test"], ledger_item["name"])]
        section_id = ledger_item["section_id"]
        verdict = judge_result["sections"][section_id]["verdict"]
        static_reward = float(static["reward"])
        gated_reward = static_reward if verdict == "pass" else 0.0
        canonical_criteria.append({
            "criterion_id": ledger_item["criterion_id"],
            "section_id": section_id,
            "test": static["test"],
            "name": static["name"],
            "value": static.get("value"),
            "target": static.get("target"),
            "unit": static.get("unit"),
            "criterion_type": static.get("criterion_type"),
            "static_reward": static_reward,
            "judge_verdict": verdict,
            "canonical_reward": gated_reward,
        })

    gated_average = sum(item["canonical_reward"] for item in canonical_criteria) / 28.0
    static_final = float(details["final_reward"])
    final_reward = min(static_final, gated_average)
    failed_sections = sorted(
        section_id
        for section_id, section in judge_result["sections"].items()
        if section["verdict"] == "fail"
    )
    production_pass = bool(
        details.get("artifact_evaluable")
        and details.get("production_pass")
        and not failed_sections
        and math.isclose(final_reward, 1.0, abs_tol=1e-12)
    )
    if failed_sections:
        outcome = "judge_sections_failed"
    elif production_pass:
        outcome = "passed"
    else:
        outcome = details.get("outcome", "requirements_failed")
    return {
        "schema_version": "1.0",
        "canonical_verifier_version": VERIFIER_VERSION,
        "outcome": outcome,
        "artifact_evaluable": bool(details.get("artifact_evaluable")),
        "production_pass": production_pass,
        "static_final_reward": static_final,
        "section_gated_average": gated_average,
        "final_reward": final_reward,
        "failed_sections": failed_sections,
        "criteria_observed": len(canonical_criteria),
        "criteria_expected": 28,
        "criteria": canonical_criteria,
        "judge": judge_result,
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--static-details", type=Path, required=True)
    parser.add_argument("--instruction", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--trial-id", default="unknown")
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument("--judge-response", type=Path)
    parser.add_argument("--judge-metadata", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()

    output = arguments.output_dir
    if output.exists() and any(output.iterdir()) and not arguments.overwrite:
        raise CanonicalVerifierError(f"output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    if arguments.overwrite:
        for name in OUTPUT_FILES:
            (output / name).unlink(missing_ok=True)

    ledger = load_json(arguments.ledger)
    details = load_json(arguments.static_details)
    validate_ledger(ledger)
    validate_static_details(details, ledger)
    prompt = arguments.prompt.read_text(encoding="utf-8")
    packet = build_packet(
        arguments.instruction,
        arguments.reference,
        arguments.candidate,
        details,
        ledger,
        arguments.trial_id,
    )
    write_json(output / "review_packet.json", packet)

    started = datetime.now(timezone.utc).isoformat()
    hashes = {
        "candidate_sha256": sha256_file(arguments.candidate),
        "static_details_sha256": sha256_file(arguments.static_details),
        "instruction_sha256": sha256_file(arguments.instruction),
        "reference_sha256": sha256_file(arguments.reference),
        "ledger_sha256": sha256_file(arguments.ledger),
        "judge_prompt_sha256": sha256_file(arguments.prompt),
        "review_packet_sha256": sha256_bytes(canonical_json(packet).encode("utf-8")),
        "canonical_verifier_sha256": sha256_file(Path(__file__)),
    }
    try:
        if arguments.judge_response:
            judge_result = load_json(arguments.judge_response)
            if arguments.judge_metadata:
                metadata_document = load_json(arguments.judge_metadata)
                api_metadata = metadata_document.get("api", metadata_document)
                if not isinstance(api_metadata, dict):
                    raise JudgeInfrastructureError("saved judge metadata is invalid")
                validate_api_metadata(api_metadata, arguments.model)
            else:
                api_metadata = {
                    "response_id": None,
                    "returned_model": "fixture",
                    "created_at": None,
                    "status": "fixture",
                    "usage": None,
                }
        else:
            judge_result, api_metadata = call_judge(
                packet,
                prompt,
                ledger,
                arguments.model,
                arguments.reasoning_effort,
            )
        validate_judge_result(judge_result, ledger)
        write_json(output / "judge.json", judge_result)
        canonical = combine_results(details, ledger, judge_result)
    except JudgeInfrastructureError as exc:
        failure = {
            "schema_version": "1.0",
            "outcome": "judge_infrastructure_failure",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "requested_model": arguments.model,
            "reasoning_effort": arguments.reasoning_effort,
            "hashes": hashes,
        }
        write_json(output / "infrastructure_failure.json", failure)
        print(json.dumps(failure, indent=2), file=sys.stderr)
        return 2

    provenance = {
        "schema_version": "1.0",
        "canonical_verifier_version": VERIFIER_VERSION,
        "trial_id": arguments.trial_id,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "requested_model": arguments.model,
        "reasoning_effort": arguments.reasoning_effort,
        "api": api_metadata,
        "hashes": hashes,
    }
    canonical["provenance"] = provenance
    write_json(output / "canonical_details.json", canonical)
    write_json(output / "provenance.json", provenance)
    write_json(output / "reward.json", {
        "reward": canonical["final_reward"],
        "production_pass": 1.0 if canonical["production_pass"] else 0.0,
        "artifact_evaluable": 1.0 if canonical["artifact_evaluable"] else 0.0,
        "static_reward": canonical["static_final_reward"],
    })
    print(json.dumps({
        "trial_id": arguments.trial_id,
        "static_reward": canonical["static_final_reward"],
        "canonical_reward": canonical["final_reward"],
        "failed_sections": canonical["failed_sections"],
        "production_pass": canonical["production_pass"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
