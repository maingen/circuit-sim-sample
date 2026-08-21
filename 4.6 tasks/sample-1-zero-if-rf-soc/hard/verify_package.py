#!/usr/bin/env python3
from pathlib import Path
import json
import tomllib

root = Path(__file__).resolve().parent
task = tomllib.loads((root / "task.toml").read_text())
assert task["task"]["name"] == "maingen/sample-1-zero-if-rf-soc-hard"
assert task["verifier"]["environment_mode"] == "separate"
assert task["environment"]["network_mode"] == "public"
assert task["verifier"]["network_mode"] == "no-network"
assert (root / "environment/candidate.cir").is_file()
assert (root / "environment/pdk/sky130_tt.inc").is_file()
assert not (root / "environment/target-ledger.json").exists()
assert not (root / "environment/reference-flat.cir").exists()
assert len(json.loads((root / "tests/target-ledger.json").read_text())["targets"]) == 93
print("sample-1-zero-if-rf-soc-hard package PASS")
