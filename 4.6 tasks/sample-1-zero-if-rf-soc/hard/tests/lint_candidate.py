#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluator import CandidateError, parse_candidate, verify_trusted_pdk


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    architecture = json.loads((Path(__file__).parent / "architecture-map.json").read_text())
    result = {"candidate": str(args.candidate), "pass": False, "failures": []}
    try:
        verify_trusted_pdk()
        _, report = parse_candidate(args.candidate, architecture)
        result["structural_report"] = report
        result["pass"] = True
    except (CandidateError, RuntimeError) as exc:
        result["failures"].append(str(exc))
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    raise SystemExit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
