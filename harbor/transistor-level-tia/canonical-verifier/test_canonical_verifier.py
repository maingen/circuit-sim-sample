#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
TASK = HERE.parent
SPEC = importlib.util.spec_from_file_location("tia_canonical_verifier", HERE / "canonical_verifier.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def ledger() -> dict:
    return json.loads((HERE / "section_ledger.json").read_text(encoding="utf-8"))


def static_details(reward: float = 1.0) -> dict:
    criteria = []
    for item in ledger()["criteria"]:
        criteria.append({
            "test": item["test"],
            "name": item["name"],
            "value": 1.0,
            "target": 1.0,
            "unit": "fixture",
            "criterion_type": "central",
            "reward": reward,
        })
    return {
        "outcome": "passed" if reward == 1.0 else "requirements_failed",
        "artifact_evaluable": True,
        "production_pass": reward == 1.0,
        "final_reward": reward,
        "criteria_observed": 28,
        "criteria_expected": 28,
        "criteria": criteria,
    }


def judge(default: str = "pass") -> dict:
    return {
        "sections": {
            section["section_id"]: {"verdict": default, "findings": []}
            for section in ledger()["sections"]
        },
        "summary": "fixture",
    }


def finding() -> dict:
    return {
        "elements": ["Xfixture"],
        "nodes": ["fixture"],
        "public_requirement": "The public fixture requirement.",
        "electrical_reason": "The fixture deliberately lacks the required path.",
    }


class CanonicalVerifierTests(unittest.TestCase):
    def test_ledger_covers_reference_criteria_exactly_once(self) -> None:
        value = ledger()
        MODULE.validate_ledger(value)
        calibration = json.loads((TASK / "tests/reference_calibration.json").read_text(encoding="utf-8"))
        expected = {(item["test"], item["name"]) for item in calibration["criteria"]}
        observed = {(item["test"], item["name"]) for item in value["criteria"]}
        self.assertEqual(expected, observed)
        owned = [criterion for section in value["sections"] for criterion in section["owned_criteria"]]
        self.assertEqual(28, len(owned))
        self.assertEqual(28, len(set(owned)))

    def test_all_pass_preserves_static_reward(self) -> None:
        result = MODULE.combine_results(static_details(), ledger(), judge())
        self.assertEqual(1.0, result["static_final_reward"])
        self.assertEqual(1.0, result["final_reward"])
        self.assertTrue(result["production_pass"])
        self.assertFalse(result["failed_sections"])

    def test_failed_section_zeros_only_owned_criteria(self) -> None:
        review = judge()
        review["sections"]["output_buffer"] = {
            "verdict": "fail",
            "findings": [finding()],
        }
        result = MODULE.combine_results(static_details(), ledger(), review)
        zeroed = {
            item["criterion_id"]
            for item in result["criteria"]
            if item["canonical_reward"] == 0.0
        }
        self.assertEqual({"C16", "C17", "C18"}, zeroed)
        self.assertEqual(25.0 / 28.0, result["final_reward"])
        self.assertFalse(result["production_pass"])

    def test_judge_cannot_raise_a_static_reward(self) -> None:
        result = MODULE.combine_results(static_details(0.5), ledger(), judge())
        self.assertEqual(0.5, result["final_reward"])

    def test_indeterminate_is_infrastructure_failure(self) -> None:
        review = judge()
        review["sections"]["peak_detector"] = {
            "verdict": "indeterminate",
            "findings": [finding()],
        }
        with self.assertRaises(MODULE.JudgeInfrastructureError):
            MODULE.combine_results(static_details(), ledger(), review)

    def test_fail_requires_concrete_evidence(self) -> None:
        review = judge()
        review["sections"]["peak_detector"] = {"verdict": "fail", "findings": []}
        with self.assertRaises(MODULE.JudgeInfrastructureError):
            MODULE.validate_judge_result(review, ledger())

    def test_api_metadata_requires_completed_requested_model(self) -> None:
        MODULE.validate_api_metadata({
            "status": "completed",
            "returned_model": "gpt-5.6-terra",
            "response_id": "resp_fixture",
        }, "gpt-5.6-terra")
        with self.assertRaises(MODULE.JudgeInfrastructureError):
            MODULE.validate_api_metadata({
                "status": "completed",
                "returned_model": "another-model",
                "response_id": "resp_fixture",
            }, "gpt-5.6-terra")
        with self.assertRaises(MODULE.JudgeInfrastructureError):
            MODULE.validate_api_metadata({
                "status": "incomplete",
                "returned_model": "gpt-5.6-terra",
                "response_id": "resp_fixture",
            }, "gpt-5.6-terra")

    def test_packet_contains_no_submitter_identity_or_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            instruction = temp / "instruction.md"
            reference = temp / "reference.cir"
            candidate = temp / "candidate.cir"
            instruction.write_text("public", encoding="utf-8")
            reference.write_text("reference", encoding="utf-8")
            candidate.write_text("candidate", encoding="utf-8")
            packet = MODULE.build_packet(
                instruction, reference, candidate, static_details(), ledger(), "trial"
            )
        self.assertNotIn("trajectory", packet)
        self.assertNotIn("agent", packet)
        self.assertNotIn("model", packet)
        self.assertTrue(packet["judge_must_ignore_submitter_identity_and_reasoning"])

    def test_prompt_protects_equivalent_names_and_topologies(self) -> None:
        prompt = (HERE / "judge_prompt.md").read_text(encoding="utf-8")
        self.assertIn("Different legal topologies", prompt)
        self.assertIn("node names", prompt)
        self.assertIn("not as a circuit that must be copied exactly", prompt)
        self.assertIn("Do not fail a section merely because", prompt)


if __name__ == "__main__":
    unittest.main()
