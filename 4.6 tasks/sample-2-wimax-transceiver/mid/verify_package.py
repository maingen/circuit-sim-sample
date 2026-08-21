#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
task = tomllib.loads((ROOT / "task.toml").read_text(encoding="utf-8"))
assert task["schema_version"] == "1.3"
assert task["artifacts"] == ["/app/submission"]
assert task["metadata"]["simulator"] == "ngspice-46"
assert task["environment"]["network_mode"] == "no-network"
assert task["verifier"]["network_mode"] == "no-network"
assert not list((ROOT / "environment").rglob("*target*ledger*"))
assert not list((ROOT / "environment").rglob("*reference_snapshot*"))
assert not list((ROOT / "environment").rglob("*reference_flat_candidate*"))
assert not list(ROOT.rglob("*.env"))
manifest = json.loads((ROOT / "environment/submission/manifest.json").read_text(encoding="utf-8"))
assert len(manifest["blocks"]) == 38
with tempfile.TemporaryDirectory() as temporary:
    for source in (ROOT / "tests").rglob("*.py"):
        py_compile.compile(str(source), cfile=str(Path(temporary) / (source.name + ".pyc")), doraise=True)
print("task package verified")
